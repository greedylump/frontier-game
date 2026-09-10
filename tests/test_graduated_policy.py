"""Small checks for a prescribed graduated allocation rule."""
from dataclasses import FrozenInstanceError, asdict
import json
from pathlib import Path

import pandas as pd
import pytest
from frontier_game import GraduatedPolicy, FixedPolicy, SafetyGapPolicy, Observation, run_trials
from experiments.laptop import run_experiment as runner

EXAMPLE = Path(__file__).resolve().parents[1] / 'experiments/laptop/configs/graduated.json'


@pytest.mark.parametrize('own,opponent,safety,expected', [
    (0,0,0,.6),                 # Base at the initial state.
    (1,3,3,.8),                 # Behind, with no safety gap.
    (3,1,3,.4),                 # Ahead reduces capability effort.
    (3,3,2,.4),                 # Shared gap alone reduces effort.
    (1,3,2,.6),                 # Deficit and gap responses combine.
    (0,10,10,1.),               # Upper clipping.
    (10,0,10,0.),               # Lower clipping from being ahead.
    (10,10,0,0.),               # Lower clipping from safety gap.
    (1,1,10,.6),                # Excess safety never creates a negative gap.
])
def test_response_formula(own,opponent,safety,expected):
    assert GraduatedPolicy().choose_allocation(Observation(1,30,own,opponent,safety)) == pytest.approx(expected)


def test_immutable_memoryless_and_relative_orientation():
    a,b=GraduatedPolicy(),GraduatedPolicy()
    assert a is not b
    behind=Observation(2,30,1,3,3)
    ahead=Observation(2,30,3,1,3)
    assert a.choose_allocation(behind) == pytest.approx(.8)
    assert b.choose_allocation(ahead) == pytest.approx(.4)
    assert a.choose_allocation(ahead) == b.choose_allocation(ahead)
    assert a.choose_allocation(behind) == pytest.approx(.8)
    with pytest.raises(FrozenInstanceError):
        a.base_allocation=.7
    assert GraduatedPolicy(.6,0,0).choose_allocation(behind)==.6
    assert GraduatedPolicy(0,0,0).choose_allocation(behind)==0
    assert GraduatedPolicy(1,0,0).choose_allocation(behind)==1


@pytest.mark.parametrize('name', ['base_allocation','deficit_response','safety_response'])
@pytest.mark.parametrize('value', [-.1,float('nan'),float('inf'),float('-inf'),True,'0.1',None])
def test_invalid_parameters(name,value):
    with pytest.raises(ValueError):
        GraduatedPolicy(**{name:value})


def test_base_upper_limit_and_unbounded_nonnegative_coefficients():
    with pytest.raises(ValueError):
        GraduatedPolicy(base_allocation=1.01)
    assert GraduatedPolicy(deficit_response=2,safety_response=3)


def test_example_loading_only():
    document=json.loads(EXAMPLE.read_text())
    config,a,b,resolved=runner.parse_config(document)
    assert a == b == GraduatedPolicy(.6,.1,.2) and a is not b
    assert config.horizon==30 and config.noise==.25
    assert resolved['trials']==1000 and resolved['seed']==2026
    assert runner.model_id_for(a,b)=='FG-M003'
    for side in ('a','b'):
        assert resolved['policies'][side] == dict(type='graduated',parameters=asdict(a))
    document['policies']['a']['parameters']={}
    assert runner.parse_config(document)[1]==GraduatedPolicy()


@pytest.mark.parametrize('side',['a','b'])
@pytest.mark.parametrize('other_type,parameters',[('fixed',{'allocation':.4}),('safety_gap',{})])
def test_independent_mixed_configuration(side,other_type,parameters):
    document=json.loads(EXAMPLE.read_text())
    other='b' if side=='a' else 'a'
    document['policies'][other]=dict(type=other_type,parameters=parameters)
    _,a,b,_=runner.parse_config(document)
    assert isinstance(a if side=='a' else b,GraduatedPolicy)
    assert not isinstance(b if side=='a' else a,GraduatedPolicy)
    assert runner.model_id_for(a,b)=='FG-M003'
    assert runner.model_id_for(FixedPolicy(.4),FixedPolicy(.6))=='FG-M001'
    assert runner.model_id_for(SafetyGapPolicy(),FixedPolicy(.4))=='FG-M002'


def test_config_rejects_typo_and_invalid_response():
    document=json.loads(EXAMPLE.read_text())
    document['policies']['a']['parameters']['deficit_respons']=.1
    with pytest.raises(ValueError,match='unknown keys'):
        runner.parse_config(document)
    del document['policies']['a']['parameters']['deficit_respons']
    document['policies']['a']['parameters']['safety_response']=-1
    with pytest.raises(ValueError,match='safety_response'):
        runner.parse_config(document)


def test_tiny_runner_metadata_and_direct_equivalence(tmp_path):
    document=json.loads(EXAMPLE.read_text())
    document.update(trials=2,category='test')
    document['model']['horizon']=3
    source=tmp_path/'config.json'
    source.write_text(json.dumps(document))
    output=tmp_path/'run'
    runner.main(['--config',str(source),'--output',str(output)])
    config,a,b,_=runner.parse_config(document)
    expected=run_trials(config,a,b,trials=2,seed=document['seed'])
    pd.testing.assert_frame_equal(pd.read_csv(output/'episodes.csv'),expected)
    metadata=json.loads((output/'metadata.json').read_text())
    assert metadata['model_id']=='FG-M003' and metadata['status']=='complete'
    assert metadata['policies']['a']['type']=='GraduatedPolicy'
    assert metadata['policies']['b']['parameters']==asdict(b)
    trajectory=pd.read_csv(output/'trajectory.csv')
    for row in trajectory.itertuples():
        observation=Observation(row.step,row.horizon,row.pre_capability_a,row.pre_capability_b,row.pre_safety)
        assert row.allocation_a==pytest.approx(a.choose_allocation(observation))
