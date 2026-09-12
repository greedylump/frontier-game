"""Information-boundary tests and exact regression against the delay engine."""
from dataclasses import FrozenInstanceError, asdict, fields
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import reference_pre_observation as reference
from frontier_game import (Config, FixedPolicy, GraduatedPolicy, Observation, PendingArrival,
                           SafetyGapPolicy, ThresholdInterventionPolicy, simulate)
from frontier_game.model import make_observations, observation_metadata
from experiments.laptop import run_experiment as runner
from experiments.laptop import safety_gap


class Recorder:
    def __init__(self, allocation):
        self.allocation = allocation
        self.observations = []

    def choose_allocation(self, observation):
        self.observations.append(observation)
        return self.allocation


def test_perspective_sorting_and_independent_snapshots():
    caps = ({9: 1.25, 2: .75}, {4: 2.5})
    safes = ({5: .125}, {8: .875, 2: .5})
    config = Config(capability_delay_a=1, capability_delay_b=3, safety_delay_a=4, safety_delay_b=6)
    a, b = make_observations(2, 4, 7, 8, 9, pending_capability=caps, pending_safety=safes, config=config)
    assert (a.own_capability, a.opponent_capability, b.own_capability, b.opponent_capability) == (7, 8, 8, 7)
    assert a.shared_safety == b.shared_safety == 9
    assert a.own_pending_capability == b.opponent_pending_capability == (PendingArrival(.75, 2), PendingArrival(1.25, 9))
    assert a.opponent_pending_capability == b.own_pending_capability == (PendingArrival(2.5, 4),)
    assert a.own_pending_safety == b.opponent_pending_safety == (PendingArrival(.125, 5),)
    assert a.opponent_pending_safety == b.own_pending_safety == (PendingArrival(.5, 2), PendingArrival(.875, 8))
    assert (a.own_capability_delay, a.opponent_capability_delay, a.own_safety_delay, a.opponent_safety_delay) == (1, 3, 4, 6)
    assert (b.own_capability_delay, b.opponent_capability_delay, b.own_safety_delay, b.opponent_safety_delay) == (3, 1, 6, 4)
    assert a.own_pending_capability is not b.opponent_pending_capability
    caps[0].clear()
    safes[1][2] = 100
    assert a.own_pending_capability[0] == PendingArrival(.75, 2)
    assert b.own_pending_safety[0] == PendingArrival(.5, 2)
    with pytest.raises(FrozenInstanceError):
        a.own_capability = 100
    with pytest.raises(FrozenInstanceError):
        a.own_pending_capability[0].amount = 100
    with pytest.raises(TypeError):
        a.own_pending_capability[0] = PendingArrival(100, 2)


def test_unknown_defaults_known_empty_and_manual_container_isolation():
    unknown = Observation(1, 3, 0, 0, 0)
    assert unknown == make_observations(1, 3, 0, 0, 0)[0]
    known, _ = make_observations(1, 3, 0, 0, 0, pending_capability=({}, {}),
                                 pending_safety=({}, {}), config=Config(horizon=3))
    for name in ('own_pending_capability', 'opponent_pending_capability', 'own_pending_safety', 'opponent_pending_safety'):
        assert getattr(unknown, name) is None
        assert getattr(known, name) == ()
    for name in ('own_capability_delay', 'opponent_capability_delay', 'own_safety_delay', 'opponent_safety_delay'):
        assert getattr(unknown, name) is None
        assert getattr(known, name) == 0
    schedule = [PendingArrival(.2, 5), PendingArrival(.1, 2)]
    manual = Observation(1, 3, 0, 0, 0, own_pending_safety=schedule)
    schedule.clear()
    assert manual.own_pending_safety == (PendingArrival(.1, 2), PendingArrival(.2, 5))
    assert unknown != known


def test_due_now_timing_beyond_horizon_and_retained_observations():
    a, b = Recorder(.75), Recorder(.25)
    cfg = Config(horizon=3, noise=0, hazard_scale=0, safety_rate=1,
                 capability_delay_a=1, capability_delay_b=4, safety_delay_a=4, safety_delay_b=1)
    result = simulate(cfg, a, b, np.random.default_rng(1), trace=True)
    assert a.observations[0].own_pending_capability == ()
    second = a.observations[1]
    assert second.own_capability == second.opponent_capability == second.shared_safety == 0
    assert second.own_pending_capability == (PendingArrival(.75, 2),)
    assert second.opponent_pending_safety == (PendingArrival(.75, 2),)
    assert second.opponent_pending_capability == (PendingArrival(.25, 5),)
    assert second.own_pending_safety == (PendingArrival(.25, 5),)
    assert result['history'][1]['post_capability_a'] == result['history'][1]['post_safety'] == .75
    assert a.observations[2].own_pending_capability == (PendingArrival(.75, 3),)
    assert a.observations[2].own_pending_safety == (PendingArrival(.25, 5), PendingArrival(.25, 6))
    # Retained snapshots survived queue releases and subsequent investments above.
    assert second.own_pending_capability == (PendingArrival(.75, 2),)
    assert b.observations[1].opponent_pending_capability == second.own_pending_capability


def test_realized_shocks_are_observed_without_future_randomness():
    cfg = Config(horizon=2, hazard_scale=0, capability_delay_a=2, capability_delay_b=3, safety_delay_a=2, safety_delay_b=3)
    expected_rng = np.random.default_rng(5)
    shock = expected_rng.lognormal(-.5*cfg.noise**2, cfg.noise, size=2)
    a, b = Recorder(.7), Recorder(.4)
    simulate(cfg, a, b, np.random.default_rng(5))
    obs = a.observations[1]
    assert obs.own_pending_capability == (PendingArrival(cfg.capability_rate*.7*shock[0], 3),)
    assert obs.opponent_pending_capability == (PendingArrival(cfg.capability_rate*.4*shock[1], 4),)
    assert obs.own_pending_safety == (PendingArrival(cfg.safety_rate*(1-.7), 3),)
    assert obs.opponent_pending_safety == (PendingArrival(cfg.safety_rate*(1-.4), 4),)
    assert set(asdict(obs)) == {f.name for f in fields(Observation)}
    for excluded in ('allocation', 'opponent_action', 'rng', 'shock', 'policy', 'opponent_safety'):
        assert not hasattr(obs, excluded)


def test_current_choices_do_not_change_either_observation():
    class ChangingRecorder(Recorder):
        def choose_allocation(self, observation):
            super().choose_allocation(observation)
            return .5 if observation.period == 1 else self.allocation
    seen = []
    for action_a, action_b in ((0, 1), (1, 0)):
        a, b = ChangingRecorder(action_a), ChangingRecorder(action_b)
        simulate(Config(horizon=2, hazard_scale=0, capability_delay_a=2, safety_delay_b=2),
                 a, b, np.random.default_rng(2))
        seen.append((a.observations, b.observations))
    assert seen[0] == seen[1]


@pytest.mark.parametrize('a,b', [(FixedPolicy(.7), FixedPolicy(.3)),
    (SafetyGapPolicy(), SafetyGapPolicy(.7, .1)),
    (GraduatedPolicy(), GraduatedPolicy(safety_response=10)),
    (ThresholdInterventionPolicy(), GraduatedPolicy(safety_response=.05))])
@pytest.mark.parametrize('delays', [(0, 0, 0, 0), (1, 2, 3, 1), (8, 1, 2, 9)])
@pytest.mark.parametrize('hazard', [0, .01, 1e6])
@pytest.mark.parametrize('seed', [1, 17, 31])
def test_exact_pre_extension_results_traces_and_rng(a, b, delays, hazard, seed):
    config = Config(horizon=5, hazard_scale=hazard, **dict(zip(
        ('capability_delay_a', 'safety_delay_a', 'capability_delay_b', 'safety_delay_b'), delays)))
    old_config = reference.Config(**asdict(config))
    outcomes = []
    for trace in (False, True):
        rng, old_rng = np.random.default_rng(seed), np.random.default_rng(seed)
        actual = simulate(config, a, b, rng, trace=trace)
        expected = reference.simulate(old_config, a, b, old_rng, trace=trace)
        assert actual == expected
        assert rng.bit_generator.state == old_rng.bit_generator.state
        outcomes.append({k:v for k,v in actual.items() if k != 'history'})
    assert outcomes[0] == outcomes[1]


def test_runner_metadata_and_no_schedule_output(tmp_path):
    doc = json.loads(Path('experiments/laptop/configs/graduated.json').read_text())
    doc.update(trials=2, category='test')
    doc['model'].update(horizon=2, capability_delay_a=1, safety_delay_b=4)
    path = tmp_path/'input.json'
    path.write_text(json.dumps(doc))
    output = tmp_path/'single'
    runner.main(['--config', str(path), '--output', str(output), '--quiet'])
    meta = json.loads((output/'metadata.json').read_text())
    assert meta['model_id'] == 'FG-M005' and meta['behavior_model_id'] == 'FG-M004'
    assert meta['observation'] == observation_metadata()
    assert meta['observation']['fields'] == [f.name for f in fields(Observation)]
    assert meta['observation']['pending_work_visible']
    assert meta['output_schema_version'] == 4 and meta['metadata_schema_version'] == 1
    assert not meta['full_trajectories']['enabled']
    for filename in ('episodes.csv', 'trajectory.csv'):
        columns = pd.read_csv(output/filename).columns
        assert 'pending_capability_a' in columns
        assert 'own_pending_capability' not in columns
    output = tmp_path/'safety'
    safety_gap.main(['--trials', '2', '--category', 'test', '--output', str(output)])
    meta = json.loads((output/'metadata.json').read_text())
    assert meta['model_id'] == 'FG-M005' and meta['behavior_model_id'] == 'FG-M002'
    assert meta['observation'] == observation_metadata()
