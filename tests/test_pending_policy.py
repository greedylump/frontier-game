from dataclasses import asdict, replace
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from frontier_game import (Config, GraduatedPolicy, PendingAwareGraduatedPolicy,
                           Observation, PendingArrival, simulate)
from frontier_game.model import make_observations
from experiments.laptop import run_experiment as runner

EXAMPLE = Path('experiments/laptop/configs/pending_aware_graduated.json')


@pytest.mark.parametrize('stocks', [(0,0,0), (3,5,1), (5,3,10), (.123,.456,.234), (100,0,0)])
def test_ignore_exact_action(stocks):
    obs = Observation(3, 4, *stocks)
    assert PendingAwareGraduatedPolicy().choose_allocation(obs) == GraduatedPolicy().choose_allocation(obs)


@pytest.mark.parametrize('delayed', [False, True])
@pytest.mark.parametrize('hazard', [0, .01, 1e6])
@pytest.mark.parametrize('seed', [1, 5, 19])
def test_ignore_exact_episode_trace_rng(delayed, hazard, seed):
    config = Config(horizon=5, hazard_scale=hazard, capability_delay_a=int(delayed),
                    safety_delay_a=2*delayed, capability_delay_b=3*delayed, safety_delay_b=int(delayed))
    outcomes = []
    for trace in (False, True):
        r1, r2 = np.random.default_rng(seed), np.random.default_rng(seed)
        new = simulate(config, PendingAwareGraduatedPolicy(safety_response=.05),
                       PendingAwareGraduatedPolicy(safety_response=10), r1, trace=trace)
        old = simulate(config, GraduatedPolicy(safety_response=.05), GraduatedPolicy(safety_response=10), r2, trace=trace)
        assert new == old
        assert r1.bit_generator.state == r2.bit_generator.state
        outcomes.append({k:v for k,v in new.items() if k != 'history'})
    assert outcomes[0] == outcomes[1]


def test_inclusive_window_excludes_past_and_does_not_cap_at_horizon():
    obs = Observation(3, 3, 0, 0, 0, own_pending_capability=(PendingArrival(100,2),
                      PendingArrival(1,3), PendingArrival(2,4), PendingArrival(4,5)), opponent_pending_capability=())
    for window, expected in [(0,.5), (1,.3), (2,0)]:
        assert PendingAwareGraduatedPolicy(safety_response=.1, capability_lookahead=window).choose_allocation(obs) == pytest.approx(expected)


def test_independent_windows_both_safety_labs_and_effective_deficit():
    a,b = make_observations(3, 3, 2, 3, 1,
        pending_capability=({3:4,4:100}, {3:1,4:100}),
        pending_safety=({3:1,4:2}, {3:1,4:2}))
    # Effective deficit = +1/-1; anticipated gap = max(6,4)-(1+1+1)=3.
    p = PendingAwareGraduatedPolicy(safety_response=.1, capability_lookahead=0, safety_lookahead=0)
    before = asdict(a)
    assert p.choose_allocation(a) == pytest.approx(.4)
    assert p.choose_allocation(b) == pytest.approx(.2)
    # Later safety can eliminate the gap; no current-gap floor is applied.
    assert replace(p,safety_lookahead=1).choose_allocation(a) == pytest.approx(.7)
    assert replace(p,capability_lookahead=None).choose_allocation(a) == pytest.approx(.7)
    assert replace(p,safety_lookahead=None).choose_allocation(a) == pytest.approx(.2)
    assert asdict(a) == before


@pytest.mark.parametrize('category', ['capability', 'safety'])
@pytest.mark.parametrize('side', ['own','opponent'])
def test_unavailable_and_empty(category, side):
    p = PendingAwareGraduatedPolicy(**{f'{category}_lookahead':0})
    obs = Observation(1,2,0,0,0, **{f'own_pending_{category}':(), f'opponent_pending_{category}':()})
    assert p.choose_allocation(obs) == .6
    with pytest.raises(ValueError, match=f'{side}_pending_{category}.*unavailable'):
        p.choose_allocation(replace(obs, **{f'{side}_pending_{category}':None}))


@pytest.mark.parametrize('name', ['capability_lookahead','safety_lookahead'])
@pytest.mark.parametrize('bad', [True,False,-1,.5,1.0,'0',np.bool_(True)])
def test_invalid_windows(name,bad):
    with pytest.raises(ValueError,match=name):
        PendingAwareGraduatedPolicy(**{name:bad})


@pytest.mark.parametrize('kwargs', [dict(base_allocation=-1),dict(base_allocation=True),
    dict(deficit_response=-.1),dict(safety_response=float('nan')),dict(safety_response='1')])
def test_invalid_coefficients(kwargs):
    with pytest.raises(ValueError):
        PendingAwareGraduatedPolicy(**kwargs)


def test_clipping_and_active_mode_rng_and_physical_risk():
    obs = Observation(1,2,0,10,0,own_pending_safety=(),opponent_pending_safety=())
    assert PendingAwareGraduatedPolicy(safety_response=0,safety_lookahead=0).choose_allocation(obs) == 1
    assert PendingAwareGraduatedPolicy(safety_response=100,safety_lookahead=0).choose_allocation(obs) == 0
    config = Config(horizon=4, noise=0, hazard_scale=.1, capability_delay_a=1, safety_delay_b=2)
    p = PendingAwareGraduatedPolicy(capability_lookahead=0,safety_lookahead=2)
    rng, plain_rng, expected_rng = (np.random.default_rng(2) for _ in range(3))
    traced = simulate(config,p,p,rng,trace=True)
    assert simulate(config,p,p,plain_rng) == {k:v for k,v in traced.items() if k!='history'}
    for row in traced['history']:
        gap = max(0,max(row['post_capability_a'],row['post_capability_b'])-row['post_safety'])
        assert row['post_gap'] == gap
        assert row['post_hazard'] == float(-np.expm1(-config.hazard_scale*gap))
        expected_rng.lognormal(0,0,size=2)
        expected_rng.random()
    assert rng.bit_generator.state == plain_rng.bit_generator.state == expected_rng.bit_generator.state


def test_json_null_zero_sweep_metadata(tmp_path):
    doc = json.loads(EXAMPLE.read_text())
    doc.update(trials=2,category='test')
    doc['model']['horizon']=2
    config,a,b,resolved = runner.parse_config(doc)
    assert isinstance(a,PendingAwareGraduatedPolicy) and a.capability_lookahead is None
    assert runner.model_id_for(a,b,config) == 'FG-M006'
    assert runner.behavior_model_id_for(a,b,config) == 'FG-M004'
    assert runner.behavior_model_id_for(a,b,Config()) == 'FG-M003'
    path = tmp_path/'config.json'
    path.write_text(json.dumps(doc))
    output = tmp_path/'sweep'
    runner.main(['--config',str(path),'--output',str(output),'--quiet',
                 '--set','policies.b.parameters.safety_lookahead=null',
                 '--sweep','policies.a.parameters.capability_lookahead=null,0'])
    manifest = json.loads((output/'manifest.json').read_text())
    assert [e['model_id'] for e in manifest['experiments']] == ['FG-M006']*2
    assert [e['behavior_model_id'] for e in manifest['experiments']] == ['FG-M004','FG-M006']
    for e,lookahead in zip(manifest['experiments'],[None,0]):
        folder=output/e['output_path']
        m=json.loads((folder/'metadata.json').read_text())
        assert m['resolved_config']==e['resolved_config']
        assert m['policies']['a']['parameters']['capability_lookahead'] == lookahead
        assert m['model_id']==e['model_id'] and m['behavior_model_id']==e['behavior_model_id']
        assert not m['full_trajectories']['enabled']
        assert 'own_pending_capability' not in pd.read_csv(folder/'trajectory.csv').columns
    for name in ('capability_lookahead','safety_lookahead'):
        for value in ('null','0','2'):
            effective,_=runner.apply_overrides(doc,[f'policies.b.parameters.{name}={value}'])
            assert getattr(runner.parse_config(effective)[2],name)==json.loads(value)
        plans=runner.resolve_experiments(doc,[],runner.sweep_rows([f'policies.b.parameters.{name}=null,0,2']))
        assert [getattr(p['prepared'][2],name) for p in plans]==[None,0,2]
    csv=b'policies.a.parameters.safety_lookahead\nnull\n0\n'
    assert len(runner.resolve_experiments(doc,[],runner.sweep_rows([],csv)))==2


@pytest.mark.parametrize('value',['true','-1','0.5','1.0','"0"'])
def test_invalid_json_lookahead(value):
    doc=json.loads(EXAMPLE.read_text())
    effective,_=runner.apply_overrides(doc,[f'policies.a.parameters.capability_lookahead={value}'])
    with pytest.raises(ValueError):
        runner.parse_config(effective)
