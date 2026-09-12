"""Tiny instrumentation checks with independent reconstruction from saved traces."""
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from frontier_game import Config, FixedPolicy, GraduatedPolicy, run_trials, simulate, summarize
from frontier_game.model import DIAGNOSTIC_DEFINITIONS
from experiments.laptop import run_experiment as runner


def check_diagnostics(outcome, history, config):
    for player in ('a','b'):
        allocations=[row[f'allocation_{player}'] for row in history]
        assert outcome[f'mean_allocation_{player}']==pytest.approx(sum(allocations)/len(allocations))
        assert outcome[f'allocation_zero_periods_{player}']==sum(value==0 for value in allocations)
        assert outcome[f'allocation_one_periods_{player}']==sum(value==1 for value in allocations)
    gaps=[max(0,max(row['post_capability_a'],row['post_capability_b'])-row['post_safety']) for row in history]
    assert outcome['max_post_gap']==pytest.approx(max(gaps))
    assert outcome['cumulative_hazard_exposure']==pytest.approx(sum(config.hazard_scale*g for g in gaps))
    assert len(history)==outcome['steps']


@pytest.mark.parametrize('config,a,b', [
    (Config(horizon=4),GraduatedPolicy(),GraduatedPolicy()),
    (Config(horizon=5,noise=0,hazard_scale=1e6,safety_rate=0),FixedPolicy(1),FixedPolicy(0)),
    (Config(horizon=3,noise=0,hazard_scale=0),FixedPolicy(0),FixedPolicy(1)),
])
def test_exact_outcomes_and_rng_state(config,a,b):
    plain_rng=np.random.default_rng(19)
    trace_rng=np.random.default_rng(19)
    plain=simulate(config,a,b,plain_rng)
    traced=simulate(config,a,b,trace_rng,trace=True)
    history=traced.pop('history')
    assert plain==traced and plain_rng.bit_generator.state==trace_rng.bit_generator.state
    check_diagnostics(plain,history,config)
    if config.hazard_scale==1e6:
        assert plain['steps']==1 and plain['catastrophe']
        assert plain['mean_allocation_a']==plain['allocation_one_periods_a']==1
        assert plain['allocation_zero_periods_b']==1
        assert plain['cumulative_hazard_exposure']==1e6


def test_changing_actions_executed_denominator():
    class Varying:
        def choose_allocation(self, observation):
            return (0,.5,1)[observation.period-1]
    config=Config(horizon=3,hazard_scale=0)
    outcome=simulate(config,Varying(),FixedPolicy(.5),np.random.default_rng(1),trace=True)
    check_diagnostics(outcome,outcome['history'],config)
    assert outcome['mean_allocation_a']==.5
    assert outcome['allocation_zero_periods_a']==outcome['allocation_one_periods_a']==1


def test_sink_order_and_rng_mapping(monkeypatch):
    import frontier_game.monte_carlo as monte
    original=monte.simulate
    final_states=[]
    events=[]
    def record(*args,**kwargs):
        events.append('simulate')
        result=original(*args,**kwargs)
        final_states.append(args[3].bit_generator.state)
        return result
    monkeypatch.setattr(monte,'simulate',record)
    config=Config(horizon=3)
    args=(config,GraduatedPolicy(),FixedPolicy(.5))
    plain=run_trials(*args,trials=3,seed=7)
    reference_states=final_states.copy()
    final_states.clear()
    events.clear()
    def sink(trial,history):
        events.append('sink')
        assert trial==events.count('sink')-1 and len(history)<=config.horizon
    traced=run_trials(*args,trials=3,seed=7,trace_sink=sink)
    pd.testing.assert_frame_equal(plain,traced)
    assert final_states==reference_states
    assert events==['simulate','sink']*3


@pytest.fixture
def source(tmp_path):
    path=Path(__file__).resolve().parents[1]/'experiments/laptop/configs/graduated.json'
    doc=json.loads(path.read_text())
    doc.update(trials=2,category='test')
    doc['model']['horizon']=3
    source=tmp_path/'config.json'
    source.write_text(json.dumps(doc))
    return source


def verify_saved(output):
    meta=json.loads((output/'metadata.json').read_text())
    episodes=pd.read_csv(output/'episodes.csv')
    with gzip.open(output/'trajectories.csv.gz','rt') as stream:
        trace=pd.read_csv(stream)
    assert meta['output_schema_version']==4
    assert meta['full_trajectories']['status']=='complete'
    assert meta['full_trajectories']['filename']=='trajectories.csv.gz'
    assert meta['full_trajectories']['completed_trials']==len(episodes)
    assert meta['full_trajectories']['rows']==len(trace)==episodes.steps.sum()
    assert set(meta['diagnostics']['definitions'])==set(DIAGNOSTIC_DEFINITIONS)
    assert set(trace.experiment_seed)=={meta['seed']}
    assert set(trace.trial)==set(episodes.trial)
    assert not meta['trajectory_in_summary'] and (output/'trajectory.csv').exists()
    for row in episodes.to_dict('records'):
        history=trace[trace.trial==row['trial']].to_dict('records')
        assert [r['step'] for r in history]==list(range(1,row['steps']+1))
        assert all(not r['post_catastrophe'] for r in history[:-1])
        assert history[-1]['post_catastrophe']==row['catastrophe']
        check_diagnostics(row,history,Config(**meta['config']))
    return episodes,trace


def test_single_default_and_full_trace_quiet(source,tmp_path,capsys):
    baseline=tmp_path/'baseline'
    runner.main(['--config',str(source),'--output',str(baseline),'--quiet'])
    assert not (baseline/'trajectories.csv.gz').exists()
    meta=json.loads((baseline/'metadata.json').read_text())
    assert not meta['full_trajectories']['enabled'] and meta['full_trajectories']['status']=='disabled'
    capsys.readouterr()
    outputs=[]
    for quiet in (False,True):
        output=tmp_path/str(quiet)
        runner.main(['--config',str(source),'--output',str(output),'--save-trajectories']+(['--quiet'] if quiet else []))
        text=capsys.readouterr().out
        assert ('payoff_a' in text)==(not quiet)
        episodes,trace=verify_saved(output)
        pd.testing.assert_frame_equal(episodes,pd.read_csv(baseline/'episodes.csv'))
        outputs.append(trace)
    pd.testing.assert_frame_equal(*outputs)
    before={p.name:p.read_bytes() for p in output.iterdir()}
    with pytest.raises(FileExistsError):
        runner.main(['--config',str(source),'--output',str(output),'--save-trajectories'])
    assert before=={p.name:p.read_bytes() for p in output.iterdir()}


def test_sweep_traces(source,tmp_path):
    output=tmp_path/'sweep'
    runner.main(['--config',str(source),'--output',str(output),'--sweep','model.safety_rate=0.6,0.75','--save-trajectories','--quiet'])
    manifest=json.loads((output/'manifest.json').read_text())
    assert manifest['save_trajectories'] and manifest['output_schema_version']==4
    for experiment in manifest['experiments']:
        verify_saved(output/experiment['output_path'])


def test_failure_closes_readable_partial_gzip(source,tmp_path,monkeypatch,capsys):
    import frontier_game.monte_carlo as monte
    original=monte.simulate
    calls=0
    def fail_second(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==2:
            raise RuntimeError('injected mid-run failure')
        return original(*args,**kwargs)
    monkeypatch.setattr(monte,'simulate',fail_second)
    output=tmp_path/'failed'
    with pytest.raises(RuntimeError):
        runner.main(['--config',str(source),'--output',str(output),'--save-trajectories','--quiet'])
    assert 'injected mid-run failure' in capsys.readouterr().err
    meta=json.loads((output/'metadata.json').read_text())
    assert meta['status']=='failed' and meta['full_trajectories']['status']=='incomplete'
    assert meta['full_trajectories']['completed_trials']==1
    trace=pd.read_csv(output/'trajectories.csv.gz')
    assert set(trace.trial)=={0} and len(trace)==meta['full_trajectories']['rows']
    # Renaming the file also confirms the writer released its Windows handle.
    (output/'trajectories.csv.gz').rename(output/'partial.csv.gz')


def test_legacy_episode_tables_still_summarize():
    path=Path(__file__).parent/'fixtures/fixed_policy_reference.json'
    legacy=pd.DataFrame(json.loads(path.read_text())['trials'])
    assert len(summarize(legacy))==4
