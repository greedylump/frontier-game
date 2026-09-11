"""Small policy/interface checks; no research runs or allocation sweeps."""
from dataclasses import FrozenInstanceError
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from frontier_game import (Config, FixedPolicy, Observation, SafetyGapPolicy,
                            ThresholdInterventionPolicy, run_trials, simulate)

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('safety_gap_entry', ROOT / 'experiments/laptop/safety_gap.py')
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


class RecordingPolicy:
    def __init__(self, allocation):
        self.allocation = allocation
        self.observations = []

    def choose_allocation(self, observation):
        self.observations.append(observation)
        return self.allocation


def test_fixed_policy_exact_prechange_reference():
    reference = json.loads((ROOT / 'tests/fixtures/fixed_policy_reference.json').read_text())
    for case in reference['cases']:
        rng = np.random.default_rng(case['seed'])
        actual = simulate(Config(**case['config']), FixedPolicy(case['a']), FixedPolicy(case['b']), rng, trace=True)
        expected = case['result']
        # Compare every historical column exactly; new diagnostics are additive.
        assert {k: actual[k] for k in expected if k != 'history'} == {k: v for k, v in expected.items() if k != 'history'}
        assert len(actual['history']) == len(expected['history'])
        for new, old in zip(actual['history'], expected['history']):
            assert {k: new[k] for k in old} == old
        assert rng.random() == case['next_random']
    actual = run_trials(Config(), FixedPolicy(.8), FixedPolicy(.4), trials=4, seed=71)
    assert actual[list(reference['trials'][0])].to_dict('records') == reference['trials']


def test_observations_are_immutable_oriented_pretransition_views():
    a, b = RecordingPolicy(.8), RecordingPolicy(.2)
    result = simulate(Config(horizon=3, noise=0, hazard_scale=0), a, b, np.random.default_rng(4), trace=True)
    assert len(a.observations) == len(b.observations) == 3
    assert a.observations[0] == b.observations[0] == Observation(1, 3, 0., 0., 0.)
    assert a.observations[1] == Observation(2, 3, .8, .2, .6)
    assert b.observations[1] == Observation(2, 3, .2, .8, .6)
    with pytest.raises(FrozenInstanceError):
        a.observations[0].shared_safety = 99
    assert not hasattr(a.observations[0], '__dict__')
    for i, row in enumerate(result['history']):
        assert row['pre_capability_a'] == a.observations[i].own_capability
        assert row['pre_capability_b'] == b.observations[i].own_capability
        assert row['allocation_a'] == .8 and row['allocation_b'] == .2
        assert row['post_capability_a'] == row['capability_a']
        assert row['post_safety'] == row['safety']
        if i:
            assert row['pre_capability_a'] == result['history'][i-1]['post_capability_a']
            assert row['pre_safety'] == result['history'][i-1]['post_safety']


def test_both_views_are_built_before_first_policy_evaluation(monkeypatch):
    import frontier_game.model as model
    events = []
    original = model.make_observations
    def observe(*args):
        pair = original(*args)
        events.append('both views built')
        return pair
    class Policy:
        def choose_allocation(self, observation):
            events.append('policy called')
            return .5
    monkeypatch.setattr(model, 'make_observations', observe)
    simulate(Config(horizon=1), Policy(), Policy(), np.random.default_rng(1))
    assert events == ['both views built', 'policy called', 'policy called']


def test_gap_rule_threshold_and_immutability():
    policy = SafetyGapPolicy(gap_threshold=1)
    for own, opponent, safety, expected in [(0, 0, 0, .5), (3, 2, 4, .5), (3, 2, 2, .5), (3, 2, 1.999, .3)]:
        assert policy.choose_allocation(Observation(1, 30, own, opponent, safety)) == expected
    assert SafetyGapPolicy().choose_allocation(Observation(1, 30, .1, 0, 0)) == .3
    with pytest.raises(FrozenInstanceError):
        policy.normal_allocation = .8
    with pytest.raises(FrozenInstanceError):
        FixedPolicy(.5).allocation = .8


def test_identical_gap_rules_equal_actions_and_no_episode_state():
    a, b = SafetyGapPolicy(), SafetyGapPolicy()
    assert a is not b
    config = Config(horizon=4, hazard_scale=0, safety_rate=0)
    result = simulate(config, a, b, np.random.default_rng(5), trace=True)
    assert result['history'][0]['allocation_a'] == .5
    assert result['history'][1]['allocation_a'] == .3
    assert all(row['allocation_a'] == row['allocation_b'] for row in result['history'])
    assert result['capability_a'] != result['capability_b']
    assert a.choose_allocation(Observation(2, 30, 3, 1, 2)) == b.choose_allocation(Observation(2, 30, 1, 3, 2))
    assert simulate(config, a, b, np.random.default_rng(5), trace=True) == result


def test_threshold_intervention_policy_thresholds_and_normal_branch():
    policy = ThresholdInterventionPolicy(base_allocation=.6, deficit_response=.1,
                                         threshold=.05)
    high_gap = Observation(1, 30, own_capability=4.0, opponent_capability=3.0,
                            shared_safety=1.0)
    low_gap = Observation(1, 30, own_capability=1.0, opponent_capability=0.0,
                           shared_safety=2.0)
    assert policy.choose_allocation(high_gap) == 0.0
    assert policy.choose_allocation(low_gap) == pytest.approx(.5)


def test_identical_relative_rules_can_choose_different_actions():
    class RelativePolicy:
        def choose_allocation(self, observation):
            return .5 if observation.own_capability >= observation.opponent_capability else .3
    result = simulate(Config(horizon=2, hazard_scale=0), RelativePolicy(), RelativePolicy(), np.random.default_rng(5), trace=True)
    assert result['history'][0]['allocation_a'] == result['history'][0]['allocation_b']
    assert result['history'][1]['allocation_a'] != result['history'][1]['allocation_b']


def test_delayed_arrivals_are_not_visible_to_current_observations():
    class ProbePolicy:
        def __init__(self):
            self.observations = []
        def choose_allocation(self, observation):
            self.observations.append(observation)
            return .5

    a = ProbePolicy()
    b = ProbePolicy()
    cfg = Config(horizon=2, noise=0, hazard_scale=0, safety_rate=0.2,
                 capability_rate=1.0, capability_delay_a=1,
                 safety_delay_a=1, capability_delay_b=1,
                 safety_delay_b=1)
    result = simulate(cfg, a, b, np.random.default_rng(1), trace=True)
    assert result["capability_a"] == result["capability_b"] == .5
    assert result["safety"] == .2
    assert a.observations[0] == Observation(1, 2, 0.0, 0.0, 0.0)
    assert a.observations[1] == Observation(2, 2, 0.0, 0.0, 0.0)
    assert b.observations[0] == Observation(1, 2, 0.0, 0.0, 0.0)
    assert b.observations[1] == Observation(2, 2, 0.0, 0.0, 0.0)


@pytest.mark.parametrize('bad', [-.1, 1.1, float('nan'), float('inf'), '0.5', None, True, 1j])
@pytest.mark.parametrize('side', ['a', 'b'])
def test_invalid_output_rejected_before_transition_or_random_draw(bad, side):
    a, b = RecordingPolicy(bad if side == 'a' else .5), RecordingPolicy(bad if side == 'b' else .5)
    rng = np.random.default_rng(4)
    before = rng.bit_generator.state
    with pytest.raises(ValueError, match='allocation'):
        simulate(Config(), a, b, rng)
    assert rng.bit_generator.state == before
    assert a.observations == b.observations == [Observation(1, 30, 0., 0., 0.)]


@pytest.mark.parametrize('kwargs', [dict(normal_allocation=-.1), dict(cautious_allocation=1.1),
                                   dict(normal_allocation=float('nan')), dict(gap_threshold=-1),
                                   dict(gap_threshold=float('inf')), dict(gap_threshold='0')])
def test_invalid_gap_parameters(kwargs):
    with pytest.raises(ValueError):
        SafetyGapPolicy(**kwargs)


def test_calls_stop_at_catastrophe():
    a, b = RecordingPolicy(1), RecordingPolicy(1)
    result = simulate(Config(noise=0, hazard_scale=1e6), a, b, np.random.default_rng(2), trace=True)
    assert result['catastrophe'] and result['steps'] == 1
    assert len(a.observations) == len(b.observations) == 1
    assert result['history'][0]['post_catastrophe']


@pytest.mark.parametrize('status,dirty', [('',False), ('?? new.py',True), (' M tracked.py',True)])
def test_git_provenance_includes_untracked_files(monkeypatch,status,dirty):
    calls=[]
    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout='abc123\n' if 'rev-parse' in command else status)
    monkeypatch.setattr(entry.subprocess, 'run', run)
    metadata=entry.code_provenance()
    assert metadata['code_commit'] == 'abc123' and metadata['code_dirty'] is dirty
    assert '--untracked-files=all' in calls[1]
    if dirty:
        assert 'commit alone does not identify' in metadata['source_provenance_note']


def test_entry_point_tiny_run_and_overwrite_refusal(tmp_path, monkeypatch):
    output = tmp_path / 'adaptive'
    original = entry.run_trials
    def checked(config, a, b, **kwargs):
        assert a == b and a is not b
        assert kwargs['trials'] == 2
        return original(config,a,b,**kwargs)
    monkeypatch.setattr(entry, 'run_trials', checked)
    args=['--trials','2','--seed','17','--normal-allocation','.6','--cautious-allocation','.2',
          '--gap-threshold','.1','--category','test','--output',str(output)]
    entry.main(args)
    assert {p.name for p in output.iterdir()} == {'episodes.csv','summary.csv','metadata.json','trajectory.csv'}
    metadata=json.loads((output/'metadata.json').read_text())
    assert metadata['model_id'] == 'FG-M002' and metadata['metadata_schema_version'] == 1
    assert metadata['status'] == 'complete' and metadata['completed_trials'] == metadata['trials'] == 2
    assert metadata['seed'] == 17 and metadata['trajectory_seed'] == 18 and not metadata['trajectory_in_summary']
    assert metadata['started_utc'] <= metadata['ended_utc']
    assert metadata['observation']['exact'] and metadata['observation']['simultaneous']
    assert metadata['initial_state'] == dict(capability_a=0.,capability_b=0.,shared_safety=0.)
    assert metadata['policies']['a']['parameters'] == dict(normal_allocation=.6,cautious_allocation=.2,gap_threshold=.1)
    assert metadata['code_dirty'] is not None and metadata['code_commit']
    assert metadata['versions']['numpy'] and metadata['python']
    episodes=pd.read_csv(output/'episodes.csv')
    assert len(episodes) == 2
    pd.testing.assert_frame_equal(pd.read_csv(output/'summary.csv'), entry.summarize(episodes))
    expected=simulate(Config(),SafetyGapPolicy(.6,.2,.1),SafetyGapPolicy(.6,.2,.1),np.random.default_rng(18),trace=True)
    pd.testing.assert_frame_equal(pd.read_csv(output/'trajectory.csv'),pd.DataFrame(expected['history']))
    before={p.name:p.read_bytes() for p in output.iterdir()}
    def must_not_run(*args,**kwargs):
        pytest.fail('existing output must be refused before simulation')
    monkeypatch.setattr(entry,'run_trials',must_not_run)
    with pytest.raises(FileExistsError):
        entry.main(args)
    assert before == {p.name:p.read_bytes() for p in output.iterdir()}


def test_entry_point_records_failure(tmp_path,monkeypatch):
    def fail(*args,**kwargs):
        raise RuntimeError('injected test failure')
    monkeypatch.setattr(entry,'run_trials',fail)
    output=tmp_path/'failed'
    with pytest.raises(RuntimeError,match='injected'):
        entry.main(['--trials','2','--output',str(output),'--category','test'])
    metadata=json.loads((output/'metadata.json').read_text())
    assert metadata['status'] == 'failed' and metadata['ended_utc']
    assert metadata['completed_trials'] == 0 and 'injected' in metadata['error']
