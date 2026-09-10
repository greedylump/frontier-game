"""Tiny sequential sweep checks; no research experiments."""
from copy import deepcopy
import csv
import io
import json
from pathlib import Path

import pandas as pd
import pytest
from experiments.laptop import run_experiment as runner
from frontier_game import run_trials

PATH='policies.a.parameters.safety_response'
OTHER='policies.b.parameters.safety_response'


def document():
    path=Path(__file__).resolve().parents[1]/'experiments/laptop/configs/graduated.json'
    data=json.loads(path.read_text())
    data.update(trials=2,category='test')
    data['model']['horizon']=2
    return data


@pytest.fixture
def source(tmp_path):
    path=tmp_path/'config.json'
    path.write_text(json.dumps(document()))
    return path


def test_cartesian_order_independent_resolution():
    data=document()
    before=deepcopy(data)
    rows=runner.sweep_rows([f'{PATH}=0.05,0.15',f'{OTHER}=0.2,0.4'])
    plans=runner.resolve_experiments(data,['model.safety_rate=0.75'],rows)
    assert [(p['prepared'][1].safety_response,p['prepared'][2].safety_response) for p in plans]==[(.05,.2),(.05,.4),(.15,.2),(.15,.4)]
    assert all(p['prepared'][0].safety_rate==.75 for p in plans)
    assert all(p['prepared'][3]['seed']==2026 for p in plans)
    assert len({id(p['prepared'][1]) for p in plans})==4
    plans[0]['prepared'][3]['model']['noise']=99
    assert plans[1]['prepared'][3]['model']['noise']==.25 and data==before


def test_csv_scalars_and_order():
    stream=io.StringIO()
    writer=csv.writer(stream)
    writer.writerow(['name','seed',PATH])
    writer.writerow([json.dumps('first, row'), '17', '0.1'])
    writer.writerow([json.dumps('second'), '18', '0.2'])
    plans=runner.resolve_experiments(document(),[],runner.sweep_rows([],stream.getvalue().encode()))
    assert [p['prepared'][3]['name'] for p in plans]==['first, row','second']
    assert [p['prepared'][3]['seed'] for p in plans]==[17,18]


@pytest.mark.parametrize('spec', ['seed=', 'seed=1,', 'seed=true', 'seed=null', 'seed="a"',
                                 'seed=NaN', 'seed=1e400', 'seed', 'seed=1,garbage'])
def test_bad_numeric_sweep(spec):
    with pytest.raises(ValueError):
        runner.sweep_rows([spec])


@pytest.mark.parametrize('content', ['', 'seed\n', 'seed,seed\n1,2\n', ',seed\n1,2\n',
    'seed,trials\n1\n', 'seed\n1,2\n', 'seed\n\n', 'seed,trials\n1, \n', 'seed\n"unterminated'])
def test_bad_csv(content):
    with pytest.raises(ValueError):
        runner.sweep_rows([],content.encode())


@pytest.mark.parametrize('options', [
    ['--sweep',f'{PATH}=0.1,-1'], ['--sweep','missing=1,2'],
    ['--sweep',f'{PATH}=0.1','--sweep',f'{PATH}=0.2'],
    ['--set',f'{PATH}=0.2','--sweep',f'{PATH}=0.1,0.3'],
])
def test_all_preflight_before_execution(source,tmp_path,monkeypatch,capsys,options):
    def forbidden(*args,**kwargs):
        pytest.fail('preflight must precede provenance and simulation')
    monkeypatch.setattr(runner,'run_trials',forbidden)
    monkeypatch.setattr(runner,'code_provenance',forbidden)
    output=tmp_path/'absent'
    with pytest.raises(SystemExit):
        runner.main(['--config',str(source),'--output',str(output),'--quiet',*options])
    assert not output.exists() and 'error:' in capsys.readouterr().err


def test_csv_conflicts_and_late_invalid_row(source,tmp_path,monkeypatch,capsys):
    path=tmp_path/'rows.csv'
    path.write_text(f'{PATH}\n0.1\n-1\n')
    def forbidden(*args,**kwargs):
        pytest.fail('invalid second row must prevent all simulations')
    monkeypatch.setattr(runner,'run_trials',forbidden)
    for extra in ([],['--set',f'{PATH}=0.2'],['--sweep','seed=1,2']):
        with pytest.raises(SystemExit):
            runner.main(['--config',str(source),'--sweep-csv',str(path),'--output',str(tmp_path/'absent'),*extra])
        assert not (tmp_path/'absent').exists()
    assert 'error:' in capsys.readouterr().err


def test_dry_run_no_output_or_provenance(source,tmp_path,monkeypatch,capsys):
    def forbidden(*args,**kwargs):
        pytest.fail('dry-run must not execute')
    monkeypatch.setattr(runner,'code_provenance',forbidden)
    monkeypatch.setattr(runner,'run_trials',forbidden)
    output=tmp_path/'absent'
    runner.main(['--config',str(source),'--output',str(output),'--sweep','trials=2,3','--sweep',f'{PATH}=0.05,0.15','--dry-run'])
    report=json.loads(capsys.readouterr().out)
    assert report['experiment_count']==4 and report['total_histories']==10
    assert report['variations'][0]['resolved_config']['trials']==2
    assert not output.exists()


def test_sweep_outputs_and_quiet_equivalence(source,tmp_path,capsys):
    before=source.read_bytes()
    results=[]
    for quiet in (False,True):
        output=tmp_path/('quiet' if quiet else 'normal')
        args=['--config',str(source),'--output',str(output),'--sweep',f'{PATH}=0.05,0.15']
        runner.main(args+(['--quiet'] if quiet else []))
        printed=capsys.readouterr()
        assert not printed.err and 'Completed 2/2' in printed.out
        if quiet:
            assert len(printed.out.strip().splitlines())==1
            assert 'payoff_a' not in printed.out and 'Experiment 1/2' not in printed.out
        else:
            assert printed.out.count('payoff_a')==2
            assert printed.out.index('Experiment 1/2')<printed.out.index('payoff_a')<printed.out.index('Experiment 2/2')
        manifest=json.loads((output/'manifest.json').read_text())
        assert manifest['input_config']==document() and manifest['completed_experiments']==2
        assert manifest['status']=='complete' and manifest['total_histories']==4
        assert manifest['code_commit'] and manifest['code_dirty'] is not None
        assert manifest['sweep_specification']['sweep']==[f'{PATH}=0.05,0.15']
        combined=pd.read_csv(output/'summary.csv')
        assert len(combined)==8 and set(combined.experiment_id)=={1,2}
        assert f'parameter.{PATH}' in combined
        for i,entry in enumerate(manifest['experiments'],1):
            assert entry['status']=='complete' and entry['output_path']==f'{i:04d}' and entry['seed']==2026
            sub=output/entry['output_path']
            meta=json.loads((sub/'metadata.json').read_text())
            assert meta['input_config']==document() and meta['model_id']=='FG-M003'
            effective,_=runner.apply_overrides(document(),[f'{PATH}={entry["varied_parameters"][PATH]}'])
            config,a,b,_=runner.parse_config(effective)
            pd.testing.assert_frame_equal(pd.read_csv(sub/'episodes.csv'),run_trials(config,a,b,trials=2,seed=2026))
        results.append(output)
    # Quiet changes presentation only; timing, invocation, and paths naturally vary in metadata.
    for relative in ['summary.csv','input_config.json',*[f'{i:04d}/{name}' for i in (1,2) for name in ('episodes.csv','summary.csv','trajectory.csv','input_config.json')]]:
        assert (results[0]/relative).read_bytes()==(results[1]/relative).read_bytes()
    assert source.read_bytes()==before
    snapshot={str(p.relative_to(results[0])):p.read_bytes() for p in results[0].rglob('*') if p.is_file()}
    with pytest.raises(FileExistsError):
        runner.main(['--config',str(source),'--output',str(results[0]),'--sweep',f'{PATH}=0.1'])
    assert snapshot=={str(p.relative_to(results[0])):p.read_bytes() for p in results[0].rglob('*') if p.is_file()}


def test_csv_execution_preserves_input(source,tmp_path,capsys):
    csv_path=tmp_path/'rows.csv'
    raw=f'{PATH},seed\r\n0.1,17\r\n0.2,18\r\n'.encode()
    csv_path.write_bytes(raw)
    output=tmp_path/'csv-run'
    runner.main(['--config',str(source),'--sweep-csv',str(csv_path),'--output',str(output),'--quiet'])
    assert (output/'sweep_input.csv').read_bytes()==csv_path.read_bytes()==raw
    manifest=json.loads((output/'manifest.json').read_text())
    assert [row['seed'] for row in manifest['experiments']]==[17,18]
    assert manifest['sweep_specification']['csv_text']==raw.decode()


def test_failure_stops_and_preserves_completed(source,tmp_path,monkeypatch,capsys):
    calls=[]
    def fail_second(*args,**kwargs):
        calls.append(1)
        if len(calls)==2:
            raise RuntimeError('injected execution failure')
        return run_trials(*args,**kwargs)
    monkeypatch.setattr(runner,'run_trials',fail_second)
    output=tmp_path/'failed'
    with pytest.raises(RuntimeError):
        runner.main(['--config',str(source),'--output',str(output),'--sweep',f'{PATH}=0.05,0.15,0.25','--quiet'])
    text=capsys.readouterr()
    assert 'injected execution failure' in text.err and 'Completed 1/3' in text.out
    assert 'payoff_a' not in text.out and len(calls)==2
    manifest=json.loads((output/'manifest.json').read_text())
    assert manifest['failed_experiment_id']==2
    assert [entry['status'] for entry in manifest['experiments']]==['complete','failed','pending']
    assert (output/'0001/episodes.csv').exists() and not (output/'0003').exists()
    assert json.loads((output/'0002/metadata.json').read_text())['status']=='failed'
    assert len(pd.read_csv(output/'summary.csv'))==4


def test_single_quiet_and_errors(source,tmp_path,monkeypatch,capsys):
    runner.main(['--config',str(source),'--output',str(tmp_path/'single'),'--quiet'])
    text=capsys.readouterr()
    assert 'Completed 1/1' in text.out and 'payoff_a' not in text.out
    def fail(*args,**kwargs):
        raise RuntimeError('single failure')
    monkeypatch.setattr(runner,'run_trials',fail)
    with pytest.raises(RuntimeError):
        runner.main(['--config',str(source),'--output',str(tmp_path/'single-failure'),'--quiet'])
    assert 'single failure' in capsys.readouterr().err
