"""Scalar override validation and tiny end-to-end checks."""
from copy import deepcopy
import json
from pathlib import Path

import pandas as pd
import pytest
from frontier_game import run_trials
from experiments.laptop import run_experiment as runner

EXAMPLE=Path(__file__).resolve().parents[1]/'experiments/laptop/configs/graduated.json'


def baseline():
    return json.loads(EXAMPLE.read_text())


def test_single_override_and_separate_copy():
    original=baseline()
    before=deepcopy(original)
    effective,records=runner.apply_overrides(original,['model.safety_rate=0.75'])
    assert original==before and effective is not original
    assert effective['model']['safety_rate']==.75
    assert records==[dict(path='model.safety_rate',value=.75,argument='model.safety_rate=0.75')]
    effective['policies']['a']['parameters']['base_allocation']=.9
    assert original==before


def test_multiple_player_settings_and_integer_types():
    effective,_=runner.apply_overrides(baseline(),['policies.a.parameters.deficit_response=0',
        'policies.a.parameters.safety_response=0.3','policies.b.parameters.safety_response=0.4',
        'trials=2','seed=17'])
    _,a,b,resolved=runner.parse_config(effective)
    assert a.deficit_response==0 and b.deficit_response==.1
    assert a.safety_response==.3 and b.safety_response==.4
    assert type(resolved['trials']) is type(resolved['seed']) is int


def test_json_string_with_equals_and_no_overrides():
    original=baseline()
    effective,records=runner.apply_overrides(original,[])
    assert effective==original and effective is not original and records==[]
    effective,_=runner.apply_overrides(original,['description="x=y"'])
    assert effective['description']=='x=y'


@pytest.mark.parametrize('specifications,match',[
    (['model.safety_rate'],'PATH=VALUE'), (['=1'],'PATH=VALUE'),
    (['model..safety_rate=1'],'PATH=VALUE'), (['model.safety_rate.=1'],'PATH=VALUE'),
    (['model.typo=1'],'unknown path'), (['policies.c.parameters.base_allocation=1'],'unknown path'),
    (['trials.value=2'],'unknown path'), (['model=0'],'existing scalar'),
    (['policies.a.parameters={}'],'existing scalar'), (['seed=[]'],'JSON scalar'),
    (['seed={}'],'JSON scalar'), (['seed=NaN'],'invalid JSON'),
    (['seed=Infinity'],'invalid JSON'), (['seed=-Infinity'],'invalid JSON'),
    (['model.noise=1e400'],'finite'), (['model.noise=-1e400'],'finite'),
    (['seed='],'invalid JSON'), (['seed=not-json'],'invalid JSON'), (['seed=01'],'invalid JSON'),
    (['seed=1','seed=2'],'duplicate override path'),
    (['trials=2.0'],'integer >= 2'), (['trials=true'],'integer >= 2'),
    (['seed=-1'],'nonnegative integer'), (['seed="17"'],'nonnegative integer'),
    (['model.noise=null'],'must be a number'), (['model.safety_rate=-1'],'finite and nonnegative'),
])
def test_invalid_overrides_before_output(tmp_path,monkeypatch,capsys,specifications,match):
    source=tmp_path/'source.json'
    source.write_text(json.dumps(baseline()))
    before=source.read_bytes()
    output=tmp_path/'absent'
    def forbidden(*args,**kwargs):
        pytest.fail('invalid overrides must fail before provenance or simulation')
    monkeypatch.setattr(runner,'code_provenance',forbidden)
    monkeypatch.setattr(runner,'run_trials',forbidden)
    args=['--config',str(source),'--output',str(output)]
    for specification in specifications:
        args.extend(['--set',specification])
    with pytest.raises(SystemExit) as error:
        runner.main(args)
    assert error.value.code==2 and match in capsys.readouterr().err
    assert not output.exists() and source.read_bytes()==before


def test_missing_default_and_array_paths_are_not_created():
    original=baseline()
    del original['model']['noise']
    with pytest.raises(ValueError,match='unknown path'):
        runner.apply_overrides(original,['model.noise=0.2'])
    original['extra']=[1,2]
    for expression,match in [('extra=0','existing scalar'),('extra.0=3','unknown path')]:
        with pytest.raises(ValueError,match=match):
            runner.apply_overrides(original,[expression])


def test_tiny_override_run_preserves_source_and_metadata(tmp_path):
    original=baseline()
    source=tmp_path/'source.json'
    source.write_text(json.dumps(original,indent=2))
    before=source.read_bytes()
    specifications=['model.safety_rate=0.75','policies.a.parameters.deficit_response=0',
                    'policies.b.parameters.safety_response=0.4','trials=2','seed=17',
                    'model.horizon=3','category="test"']
    output=tmp_path/'run'
    args=['--config',str(source),'--output',str(output)]
    for specification in specifications:
        args.extend(['--set',specification])
    runner.main(args)
    effective,records=runner.apply_overrides(original,specifications)
    config,a,b,resolved=runner.parse_config(effective)
    expected=run_trials(config,a,b,trials=2,seed=17)
    pd.testing.assert_frame_equal(pd.read_csv(output/'episodes.csv'),expected)
    metadata=json.loads((output/'metadata.json').read_text())
    assert metadata['input_config']==original and metadata['overrides']==records
    assert metadata['resolved_config']==resolved
    assert metadata['model_id']=='FG-M003' and metadata['status']=='complete'
    assert metadata['seed']==17 and metadata['trials']==2 and metadata['trajectory_seed']==18
    assert metadata['seed_mapping']['episodes']==dict(entropy=17,spawn_keys=[[0],[1]])
    assert metadata['policies']['a']['parameters']['deficit_response']==0
    assert metadata['policies']['b']['parameters']['safety_response']==.4
    assert source.read_bytes()==(output/'input_config.json').read_bytes()==before
    # An equivalent explicit tiny config gives identical numerical outputs without --set.
    explicit=tmp_path/'explicit.json'
    explicit.write_text(json.dumps(effective))
    plain=tmp_path/'plain'
    runner.main(['--config',str(explicit),'--output',str(plain)])
    for name in ('episodes.csv','summary.csv','trajectory.csv'):
        assert (plain/name).read_bytes()==(output/name).read_bytes()
    assert json.loads((plain/'metadata.json').read_text())['overrides']==[]
