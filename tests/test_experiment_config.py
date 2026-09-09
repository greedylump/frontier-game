"""Strict config and tiny runner checks; the research example is parsed only."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
from frontier_game import Config, FixedPolicy, SafetyGapPolicy, run_trials, simulate, summarize
from experiments.laptop import run_experiment as runner

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'experiments/laptop/configs/asymmetric_safety_gap.json'


def tiny_config():
    config = json.loads(EXAMPLE.read_text(encoding='utf-8-sig'))
    config.update(trials=2, category='test')
    config['model']['horizon'] = 3
    return config


def write_config(tmp_path, config):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    return path


def test_example_and_default_resolution_without_simulation():
    example = json.loads(EXAMPLE.read_text(encoding='utf-8-sig'))
    config, a, b, resolved = runner.parse_config(example)
    assert asdict(config) == asdict(Config())
    assert set(example['model']) == set(asdict(Config()))
    assert resolved['trials'] == 1000 and resolved['seed'] == 2026
    assert a == SafetyGapPolicy(.6,.3,0) and b == SafetyGapPolicy(.5,.3,0) and a is not b
    minimal = deepcopy(example)
    minimal['model'] = {}
    minimal['policies']['a']['parameters'] = {}
    _, a, _, resolved = runner.parse_config(minimal)
    assert a == SafetyGapPolicy()
    assert resolved['model'] == asdict(Config())
    assert resolved['policies']['a']['parameters'] == asdict(SafetyGapPolicy())


@pytest.mark.parametrize('path,value,message', [
    (('typo',),0,'unknown keys'),
    (('model','noize'),.25,'config.model: unknown'),
    (('policies','c'),{},'config.policies: unknown'),
    (('policies','a','paramters'),{},'config.policies.a: unknown'),
    (('policies','b','parameters','normal_alocation'),.5,'config.policies.b.parameters: unknown'),
    (('policies','a','type'),'arbitrary.module','must be one of'),
    (('policies','a','type'),[],'must be one of'),
    (('policies','a','parameters'),[],'must be a JSON object'),
    (('policies',),[],'must be a JSON object'),
    (('model',),None,'must be a JSON object'),
    (('name',),'','nonempty string'),
    (('description',),3,'nonempty string'),
    (('trials',),1,'integer >= 2'),
    (('trials',),2.5,'integer >= 2'),
    (('trials',),True,'integer >= 2'),
    (('seed',),-1,'nonnegative integer'),
    (('seed',),1.5,'nonnegative integer'),
    (('seed',),False,'nonnegative integer'),
    (('category',),'typo','category must be'),
    (('model','horizon'),0,'horizon must'),
    (('model','horizon'),1.5,'horizon must'),
    (('model','noise'),-.1,'noise must'),
    (('model','noise'),'0.25','must be a number'),
    (('model','noise'),True,'must be a number'),
    (('policies','a','parameters','normal_allocation'),1.1,'allocation must'),
    (('policies','b','parameters','cautious_allocation'),-.1,'allocation must'),
    (('policies','b','parameters','gap_threshold'),-1,'gap_threshold must'),
])
def test_invalid_config_before_output_or_simulation(tmp_path,monkeypatch,capsys,path,value,message):
    document = tiny_config()
    target = document
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    source = write_config(tmp_path,document)
    output = tmp_path/'must-not-exist'
    def forbidden(*args,**kwargs):
        pytest.fail('invalid input must not run simulations or collect provenance')
    monkeypatch.setattr(runner,'run_trials',forbidden)
    monkeypatch.setattr(runner,'code_provenance',forbidden)
    with pytest.raises(SystemExit) as error:
        runner.main(['--config',str(source),'--output',str(output)])
    assert error.value.code == 2 and not output.exists()
    assert message in capsys.readouterr().err


@pytest.mark.parametrize('path', [('name',),('description',),('model',),('trials',),('seed',),('policies',),
                                  ('policies','a'),('policies','b'),('policies','a','type'),('policies','b','parameters')])
def test_missing_fields(path):
    document=tiny_config()
    target=document
    for key in path[:-1]:
        target=target[key]
    del target[path[-1]]
    with pytest.raises(ValueError,match='missing required keys'):
        runner.parse_config(document)
    document=tiny_config()
    document['policies']['a']={'type':'fixed','parameters':{}}
    with pytest.raises(ValueError,match='allocation'):
        runner.parse_config(document)


@pytest.mark.parametrize('text,match', [('{','Expecting'), ('[]','must be a JSON object'),
                                       ('{"name":"a","name":"b"}','duplicate JSON key'),
                                       ('{"noise":NaN}','invalid JSON numeric constant'),
                                       ('{"noise":Infinity}','invalid JSON numeric constant')])
def test_bad_json_before_output(tmp_path,capsys,text,match):
    source=tmp_path/'bad.json'
    source.write_text(text)
    output=tmp_path/'absent'
    with pytest.raises(SystemExit):
        runner.main(['--config',str(source),'--output',str(output)])
    assert not output.exists() and match in capsys.readouterr().err


@pytest.mark.parametrize('a_type,b_type,model_id', [('safety_gap','safety_gap','FG-M002'),
                                                   ('fixed','safety_gap','FG-M002'),
                                                   ('safety_gap','fixed','FG-M002'),
                                                   ('fixed','fixed','FG-M001')])
def test_tiny_runner_matches_direct_calls(tmp_path,monkeypatch,a_type,b_type,model_id):
    document=tiny_config()
    for side,kind,allocation in [('a',a_type,.6),('b',b_type,.4)]:
        if kind=='fixed':
            document['policies'][side]={'type':'fixed','parameters':{'allocation':allocation}}
    source=write_config(tmp_path,document)
    output=tmp_path/'run'
    captured={}
    def checked(config,a,b,**kwargs):
        assert kwargs['trials']==2 and config.horizon==3 and a is not b
        captured.update(config=config,a=a,b=b,kwargs=kwargs)
        return run_trials(config,a,b,**kwargs)
    monkeypatch.setattr(runner,'run_trials',checked)
    runner.main(['--config',str(source),'--output',str(output)])
    assert {p.name for p in output.iterdir()} == {'episodes.csv','summary.csv','trajectory.csv','metadata.json','input_config.json'}
    assert (output/'input_config.json').read_bytes()==source.read_bytes()
    expected=run_trials(captured['config'],captured['a'],captured['b'],**captured['kwargs'])
    pd.testing.assert_frame_equal(pd.read_csv(output/'episodes.csv'),expected)
    pd.testing.assert_frame_equal(pd.read_csv(output/'summary.csv'),summarize(expected))
    trajectory=simulate(captured['config'],captured['a'],captured['b'],np.random.default_rng(document['seed']+1),trace=True)
    saved=pd.read_csv(output/'trajectory.csv')
    pd.testing.assert_frame_equal(saved,pd.DataFrame(trajectory['history']))
    assert {'pre_capability_a','post_capability_a','allocation_a','allocation_b'} <= set(saved)
    metadata=json.loads((output/'metadata.json').read_text())
    assert metadata['model_id']==model_id and metadata['metadata_schema_version']==1
    assert metadata['input_config']==document and metadata['resolved_config']==runner.parse_config(document)[3]
    assert metadata['description']==document['description']
    assert metadata['experiment_name']==document['name']
    for side in ('a','b'):
        assert metadata['policies'][side]['parameters']==asdict(captured[side])
        assert metadata['policies'][side]['type']==type(captured[side]).__name__
    assert metadata['policies']['a'] != metadata['policies']['b']
    assert metadata['seed_mapping']=={'episodes':{'entropy':2026,'spawn_keys':[[0],[1]]},'trajectory':{'seed':2027}}
    assert metadata['status']=='complete' and metadata['completed_trials']==2
    assert metadata['observation']['exact'] and not metadata['trajectory_in_summary']
    assert metadata['started_utc']<=metadata['ended_utc']
    assert metadata['versions']['numpy'] and metadata['code_commit'] and metadata['code_dirty'] is not None
    before={p.name:p.read_bytes() for p in output.iterdir()}
    def forbidden(*args,**kwargs):
        pytest.fail('existing output must be refused before simulation')
    monkeypatch.setattr(runner,'run_trials',forbidden)
    with pytest.raises(FileExistsError):
        runner.main(['--config',str(source),'--output',str(output)])
    assert before=={p.name:p.read_bytes() for p in output.iterdir()}


def test_failure_metadata_and_input_copy(tmp_path,monkeypatch):
    source=write_config(tmp_path,tiny_config())
    output=tmp_path/'failed'
    def fail(*args,**kwargs):
        raise RuntimeError('test failure')
    monkeypatch.setattr(runner,'run_trials',fail)
    with pytest.raises(RuntimeError,match='test failure'):
        runner.main(['--config',str(source),'--output',str(output)])
    metadata=json.loads((output/'metadata.json').read_text())
    assert metadata['status']=='failed' and metadata['completed_trials']==0 and metadata['ended_utc']
    assert (output/'input_config.json').read_bytes()==source.read_bytes()


def test_direct_script_cli_tiny_run(tmp_path):
    source=write_config(tmp_path,tiny_config())
    output=tmp_path/'cli'
    command=[sys.executable,str(ROOT/'experiments/laptop/run_experiment.py'),'--config',str(source),'--output',str(output)]
    result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode==0, result.stderr
    assert len(pd.read_csv(output/'episodes.csv'))==2
