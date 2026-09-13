from dataclasses import asdict, replace, FrozenInstanceError
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from frontier_game import (Config, GraduatedPolicy, PendingAwareGraduatedPolicy,
    PendingWeightedGraduatedPolicy as Weighted, Observation, PendingArrival, simulate)
from experiments.laptop import run_experiment as runner

EXAMPLE=Path('experiments/laptop/configs/pending_weighted_graduated.json')


def test_hand_calculation():
    obs=Observation(3,3,8,9,2,own_pending_capability=(PendingArrival(2,3),),
        opponent_pending_capability=(PendingArrival(3,4),),
        own_pending_safety=(PendingArrival(1,3),PendingArrival(2,4),PendingArrival(100,5)),
        opponent_pending_safety=(PendingArrival(3,3),PendingArrival(4,4),PendingArrival(100,5)))
    # Safety = 2 + 1*(1+3) + .5*(2+4) = 9; cap=max(10,12); gap=3.
    p=Weighted(safety_response=.1,capability_lookahead=1,safety_weights=[1,.5])
    before=asdict(obs)
    assert p.decision_gap(obs)==3
    assert p.choose_allocation(obs)==.6+.1*(9-8)-.1*3
    assert replace(p,safety_weights=[.5,.5]).decision_gap(obs)==5
    assert asdict(obs)==before


def test_missing_periods_outside_window_and_effective_safety():
    obs=Observation(3,3,10,0,2,own_pending_safety=(PendingArrival(100,2),PendingArrival(4,4),PendingArrival(100,6)),opponent_pending_safety=())
    assert Weighted(safety_weights=[1,.5]).decision_gap(obs)==6
    assert Weighted(safety_weights=[1,0]).decision_gap(obs)==8
    assert Weighted(safety_weights=[0,0]).decision_gap(obs)==8


@pytest.mark.parametrize('weights',[[],[0],[0,0]])
def test_ignored_safety_needs_no_information(weights):
    obs=Observation(2,2,.75,.5,.125)
    assert Weighted(safety_weights=weights).choose_allocation(obs)==GraduatedPolicy().choose_allocation(obs)


@pytest.mark.parametrize('name',['own_pending_safety','opponent_pending_safety'])
def test_positive_weights_require_both_schedules(name):
    obs=Observation(1,2,1,0,0,own_pending_safety=(),opponent_pending_safety=())
    p=Weighted(safety_weights=[0,.5])
    assert p.decision_gap(obs)==1
    with pytest.raises(ValueError,match=name):
        p.decision_gap(replace(obs,**{name:None}))


@pytest.mark.parametrize('name',['own_pending_capability','opponent_pending_capability'])
def test_capability_information(name):
    obs=Observation(1,2,1,0,0,own_pending_capability=(),opponent_pending_capability=())
    p=Weighted(capability_lookahead=0)
    assert p.decision_gap(obs)==1
    with pytest.raises(ValueError,match=name):p.decision_gap(replace(obs,**{name:None}))


@pytest.mark.parametrize('weights',[True,None,'1',1,{},[True],[False],['.5'],[None],[-.1],[1.1],[float('nan')],[float('inf')],[[.5]]])
def test_invalid_weights(weights):
    with pytest.raises(ValueError,match='safety_weights'):Weighted(safety_weights=weights)


@pytest.mark.parametrize('bad',[True,-1,.5,1.0,'1'])
def test_invalid_capability_window(bad):
    with pytest.raises(ValueError,match='capability_lookahead'):Weighted(capability_lookahead=bad)


def test_immutable_normalization():
    weights=[1,.5,0]
    p=Weighted(safety_weights=weights); weights[0]=0
    assert p.safety_weights==(1.,.5,0.)
    with pytest.raises(FrozenInstanceError):p.safety_weights=()
    with pytest.raises(TypeError):p.safety_weights[0]=0
    with pytest.raises(TypeError):Weighted(safety_lookahead=1)


@pytest.mark.parametrize('weights,window',[([1,1],1),([1],0),([1,0],0),([],None),([0,0],None)])
@pytest.mark.parametrize('cap',[None,0,1])
@pytest.mark.parametrize('noise',[0,.25])
def test_exact_equivalent_simulations(weights,window,cap,noise):
    cfg=Config(horizon=5,noise=noise,capability_delay_a=1,capability_delay_b=2,safety_delay_a=2,safety_delay_b=1)
    p=Weighted(capability_lookahead=cap,safety_weights=weights)
    old=PendingAwareGraduatedPolicy(capability_lookahead=cap,safety_lookahead=window)
    before=asdict(p)
    for diagnostic in (False,True):
        r1,r2=np.random.default_rng(19),np.random.default_rng(19)
        actual=simulate(cfg,p,p,r1,trace=True,trace_decision_gaps=diagnostic)
        expected=simulate(cfg,old,old,r2,trace=True,trace_decision_gaps=diagnostic)
        assert actual==expected
        assert r1.bit_generator.state==r2.bit_generator.state
    r1,r2=np.random.default_rng(19),np.random.default_rng(19)
    assert simulate(cfg,p,p,r1)==simulate(cfg,old,old,r2)
    assert r1.bit_generator.state==r2.bit_generator.state
    assert asdict(p)==before


def test_config_override_and_provenance(tmp_path):
    doc=json.loads(EXAMPLE.read_text()); doc.update(trials=2,category='test');doc['model']['horizon']=3
    original=json.loads(json.dumps(doc))
    effective,records=runner.apply_overrides(doc,['policies.b.parameters.safety_weights=[1,0.5]'])
    cfg,a,b,resolved=runner.parse_config(effective)
    assert doc==original and b.safety_weights==(1.,.5)
    assert 'safety_lookahead' not in resolved['policies']['b']['parameters']
    assert runner.model_id_for(a,b,cfg)==runner.behavior_model_id_for(a,b,cfg)=='FG-M007'
    source=tmp_path/'input.json';source.write_text(json.dumps(doc));out=tmp_path/'out'
    runner.main(['--config',str(source),'--output',str(out),'--set','policies.b.parameters.safety_weights=[1,0.5]',
                 '--save-trajectories','--quiet'])
    m=json.loads((out/'metadata.json').read_text())
    assert m['resolved_config']['policies']['b']['parameters']['safety_weights']==[1.,.5]
    assert m['policies']['b']['parameters']['safety_weights']==[1.,.5]
    assert m['overrides']==records
    assert m['output_schema_version']==4 and m['model_id']=='FG-M007'
    trace=pd.read_csv(out/'trajectories.csv.gz')
    assert 'decision_gap_b' in trace
    for trial,child in enumerate(np.random.SeedSequence(doc['seed']).spawn(2)):
        expected=simulate(cfg,a,b,np.random.default_rng(child),trace=True,trace_decision_gaps=True)
        np.testing.assert_allclose(trace[trace.trial==trial].decision_gap_b,[r['decision_gap_b'] for r in expected['history']],rtol=0,atol=1e-15)
    assert 'decision_gap_b' not in pd.read_csv(out/'trajectory.csv')
    assert 'safety_weights' not in pd.read_csv(out/'episodes.csv')


@pytest.mark.parametrize('raw',['null','1','"bad"','[true]','[null]','[-1]','[2]','["0.5"]','[NaN]','[Infinity]'])
def test_bad_override_preflight(raw,tmp_path):
    doc=json.loads(EXAMPLE.read_text());source=tmp_path/'bad.json';source.write_text(json.dumps(doc))
    output=tmp_path/'absent'
    with pytest.raises(SystemExit):runner.main(['--config',str(source),'--output',str(output),'--set',f'policies.b.parameters.safety_weights={raw}'])
    assert not output.exists()


def test_parser_boundaries():
    doc=json.loads(EXAMPLE.read_text())
    with pytest.raises(ValueError):runner.apply_overrides(doc,['policies.a.parameters.safety_response=[1,0.5]'])
    with pytest.raises(ValueError):runner.sweep_rows(['policies.b.parameters.safety_weights=[1,0.5]'])
    with pytest.raises(ValueError,match='array-valued sweeps'):
        runner.resolve_experiments(doc,[],[['policies.b.parameters.safety_weights=[1,0.5]']])
    # A vector held fixed via --set remains valid while sweeping a scalar.
    plans=runner.resolve_experiments(doc,['policies.b.parameters.safety_weights=[1,0.5]'],
        runner.sweep_rows(['policies.b.parameters.safety_response=1,3']))
    assert all(p['prepared'][2].safety_weights==(1.,.5) for p in plans)
    doc['policies']['b']['parameters']['safety_lookahead']=1
    with pytest.raises(ValueError,match='unknown keys.*safety_lookahead'):runner.parse_config(doc)


def test_behavior_classification_and_example():
    p=Weighted()
    assert runner.model_id_for(p,p)=='FG-M007'
    assert runner.behavior_model_id_for(p,p,Config())=='FG-M003'
    assert runner.behavior_model_id_for(p,p,Config(safety_delay_a=1))=='FG-M004'
    assert runner.behavior_model_id_for(p,PendingAwareGraduatedPolicy(safety_lookahead=0))=='FG-M006'
    assert runner.behavior_model_id_for(replace(p,safety_weights=[1]),p)=='FG-M007'
    cfg,a,b,resolved=runner.parse_config(json.loads(EXAMPLE.read_text()))
    assert a==PendingAwareGraduatedPolicy(safety_response=.05)
    assert b==Weighted(safety_response=10,capability_lookahead=1,safety_weights=[.5,.5])
    assert [cfg.capability_delay_a,cfg.safety_delay_a,cfg.capability_delay_b,cfg.safety_delay_b]==[1,2,1,2]
