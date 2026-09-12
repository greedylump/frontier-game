"""Optional full-trace policy measures; no research outputs."""
import csv
from dataclasses import asdict
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from frontier_game import (Config, FixedPolicy, GraduatedPolicy, SafetyGapPolicy,
    ThresholdInterventionPolicy, PendingAwareGraduatedPolicy, Observation, PendingArrival,
    simulate, run_trials)
from experiments.laptop import run_experiment as runner

KEYS = {'decision_gap_a', 'decision_gap_b'}


@pytest.mark.parametrize('policy', [GraduatedPolicy(), SafetyGapPolicy(),
    ThresholdInterventionPolicy(), PendingAwareGraduatedPolicy()])
def test_effective_gap(policy):
    assert policy.decision_gap(Observation(1,3,3,2,1)) == 2
    assert policy.decision_gap(Observation(1,3,2,3,4)) == 0


@pytest.mark.parametrize('cap,safety,expected', [(None,None,2),(0,None,3),(None,0,1),
    (0,0,2),(1,1,0),(1,None,5),(None,1,0)])
def test_pending_windows(cap,safety,expected):
    obs=Observation(2,2,3,2,1,
        own_pending_capability=(PendingArrival(1,2),PendingArrival(2,3)),
        opponent_pending_capability=(), own_pending_safety=(PendingArrival(1,2),),
        opponent_pending_safety=(PendingArrival(10,3),))
    before=asdict(obs)
    policy=PendingAwareGraduatedPolicy(capability_lookahead=cap,safety_lookahead=safety)
    assert policy.decision_gap(obs)==expected
    assert policy.choose_allocation(obs)==float(np.clip(.6+.1*(2-3)-.2*expected,0,1))
    assert asdict(obs)==before


class Custom:
    def choose_allocation(self,observation):
        return .5


@pytest.mark.parametrize('a,b', [(FixedPolicy(.6),Custom()), (GraduatedPolicy(),SafetyGapPolicy()),
    (ThresholdInterventionPolicy(),PendingAwareGraduatedPolicy()),
    (PendingAwareGraduatedPolicy(capability_lookahead=0,safety_lookahead=1),
     PendingAwareGraduatedPolicy(capability_lookahead=1))])
@pytest.mark.parametrize('hazard', [0,.01,1e6])
@pytest.mark.parametrize('delayed',[False,True])
def test_exact_results_original_fields_and_rng(a,b,hazard,delayed):
    cfg=Config(horizon=4,hazard_scale=hazard,capability_delay_a=int(delayed),safety_delay_b=2*delayed)
    plain_rng,trace_rng,diag_rng=(np.random.default_rng(7) for _ in range(3))
    plain=simulate(cfg,a,b,plain_rng)
    trace=simulate(cfg,a,b,trace_rng,trace=True)
    diag=simulate(cfg,a,b,diag_rng,trace=True,trace_decision_gaps=True)
    old_history=trace.pop('history'); new_history=diag.pop('history')
    assert plain==trace==diag
    assert plain_rng.bit_generator.state==trace_rng.bit_generator.state==diag_rng.bit_generator.state
    for old,new in zip(old_history,new_history):
        assert set(new)-set(old)==KEYS
        assert {k:new[k] for k in old}==old
        if isinstance(a,FixedPolicy):
            assert new['decision_gap_a'] is new['decision_gap_b'] is None


def test_single_calls_exact_views_and_no_diagnostics_without_opt_in():
    class Probe:
        def __init__(self):
            self.chosen=[]; self.diagnosed=[]
        def choose_allocation(self,obs):
            self.chosen.append(obs)
            return .75 if obs.own_capability >= obs.opponent_capability else .25
        def decision_gap(self,obs):
            self.diagnosed.append(obs)
            # Custom diagnostic exposes orientation for this interface test.
            return obs.own_capability-obs.opponent_capability
    a,b=Probe(),Probe()
    cfg=Config(horizon=3,noise=0,hazard_scale=0,capability_delay_a=1)
    out=simulate(cfg,a,b,np.random.default_rng(1),trace=True,trace_decision_gaps=True)
    assert len(a.chosen)==len(b.chosen)==len(a.diagnosed)==len(b.diagnosed)==out['steps']
    for i,row in enumerate(out['history']):
        assert a.chosen[i] is a.diagnosed[i] and b.chosen[i] is b.diagnosed[i]
        assert row['decision_gap_a']==row['pre_capability_a']-row['pre_capability_b']
        assert row['decision_gap_b']==-row['decision_gap_a']
    for trace in (False,True):
        a,b=Probe(),Probe()
        simulate(cfg,a,b,np.random.default_rng(1),trace=trace)
        assert not a.diagnosed and not b.diagnosed


def test_no_history_state_and_gap_differs_from_effective():
    p=PendingAwareGraduatedPolicy(safety_lookahead=1)
    before=asdict(p)
    histories=[]
    cfg=Config(horizon=3,noise=0,hazard_scale=0,capability_delay_a=1,safety_delay_b=2)
    run_trials(cfg,p,GraduatedPolicy(),trials=2,seed=2,trace_decision_gaps=True,
               trace_sink=lambda trial,history: histories.append(history))
    assert histories[0]==histories[1] and asdict(p)==before
    for history in histories:
        assert history[0]['decision_gap_a']==0


def test_export_boundaries_and_blanks(tmp_path):
    doc=json.loads(Path('experiments/laptop/configs/pending_aware_graduated.json').read_text())
    doc.update(trials=2,category='test'); doc['model']['horizon']=3
    doc['policies']['a']=dict(type='fixed',parameters=dict(allocation=.7))
    doc['policies']['b']['parameters'].update(capability_lookahead=0,safety_lookahead=1)
    source=tmp_path/'input.json'; source.write_text(json.dumps(doc))
    for full in (False,True):
        runner.main(['--config',str(source),'--output',str(tmp_path/str(full)),'--quiet']+
                    (['--save-trajectories'] if full else []))
    for filename in ('episodes.csv','summary.csv','trajectory.csv'):
        assert (tmp_path/'False'/filename).read_bytes()==(tmp_path/'True'/filename).read_bytes()
        assert not KEYS.intersection(pd.read_csv(tmp_path/'True'/filename).columns)
    cfg,a,b,resolved=runner.parse_config(doc)
    ordinary=[]
    run_trials(cfg,a,b,trials=2,seed=doc['seed'],trace_sink=lambda _,h: ordinary.extend(h))
    with gzip.open(tmp_path/'True'/'trajectories.csv.gz','rt',newline='') as f:
        rows=list(csv.DictReader(f))
    assert set(rows[0])-set(ordinary[0])==KEYS|{'experiment_seed','trial'}
    assert all(r['decision_gap_a']=='' and r['decision_gap_b']!='' for r in rows)
    meta=json.loads((tmp_path/'True'/'metadata.json').read_text())
    assert meta['output_schema_version']==4 and meta['metadata_schema_version']==1
    assert set(meta['full_trajectories']['decision_gap_definitions'])==KEYS
    assert meta['model_id']=='FG-M006'


def test_opt_in_requires_trace():
    with pytest.raises(ValueError,match='trace=True'):
        simulate(Config(),Custom(),Custom(),np.random.default_rng(1),trace_decision_gaps=True)
    with pytest.raises(ValueError,match='trace_sink'):
        run_trials(Config(),Custom(),Custom(),trials=2,trace_decision_gaps=True)
