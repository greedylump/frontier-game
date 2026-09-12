"""Delay timing, conservation, and exact compatibility with the Git baseline."""
from dataclasses import asdict
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import reference_pre_delay as reference
from frontier_game import Config, FixedPolicy, GraduatedPolicy, SafetyGapPolicy, ThresholdInterventionPolicy, simulate
from experiments.laptop import run_experiment as runner

DELAYS = ('capability_delay_a', 'safety_delay_a', 'capability_delay_b', 'safety_delay_b')
PENDING = ('pending_capability_a', 'pending_capability_b', 'pending_safety_a', 'pending_safety_b')


@pytest.mark.parametrize('a,b', [(FixedPolicy(.63), FixedPolicy(.41)),
    (GraduatedPolicy(), GraduatedPolicy(safety_response=10)),
    (GraduatedPolicy(safety_response=.05), ThresholdInterventionPolicy()),
    (SafetyGapPolicy(), SafetyGapPolicy())])
@pytest.mark.parametrize('seed', range(12))
@pytest.mark.parametrize('hazard', [0, .01, 10])
def test_exact_git_regression(a, b, seed, hazard):
    config = Config(horizon=8, hazard_scale=hazard)
    old_config = reference.Config(**{k:v for k,v in asdict(config).items() if k not in DELAYS})
    outcomes = []
    for trace in (False, True):
        rng, old_rng = np.random.default_rng(seed), np.random.default_rng(seed)
        actual = simulate(config, a, b, rng, trace=trace)
        expected = reference.simulate(old_config, a, b, old_rng, trace=trace)
        assert rng.bit_generator.state == old_rng.bit_generator.state
        for key, value in expected.items():
            if key == 'history':
                assert [{k:r[k] for k in value[0]} for r in actual[key]] == value
                assert all(r[k] == 0 for r in actual[key] for k in PENDING)
            else:
                assert actual[key] == value
        assert all(actual[k] == 0 for k in PENDING)
        outcomes.append({k:v for k,v in actual.items() if k != 'history'})
    assert outcomes[0] == outcomes[1]


@pytest.mark.parametrize('name', DELAYS)
@pytest.mark.parametrize('value', [True, False, -1, .5, 1.0, '1', None])
def test_invalid_delay(name, value):
    with pytest.raises(ValueError, match=name):
        Config(**{name:value})


@pytest.mark.parametrize('delays', [(1, 2, 3, 0), (0, 3, 1, 2), (3, 3, 3, 3), (8, 9, 10, 11)])
def test_independent_arrivals_conservation_and_trace(delays):
    config = Config(horizon=4, noise=0, hazard_scale=0, safety_rate=1, **dict(zip(DELAYS, delays)))
    rng, plain_rng = np.random.default_rng(5), np.random.default_rng(5)
    result = simulate(config, FixedPolicy(.75), FixedPolicy(.25), rng, trace=True)
    plain = simulate(config, FixedPolicy(.75), FixedPolicy(.25), plain_rng)
    assert plain == {k:v for k,v in result.items() if k != 'history'}
    assert rng.bit_generator.state == plain_rng.bit_generator.state
    for row in result['history']:
        t = row['step']
        safety = pre_safety = 0
        for lab, effort, dc, ds in [('a', .75, delays[0], delays[1]), ('b', .25, delays[2], delays[3])]:
            effective = max(0, t-dc)*effort
            assert row[f'post_capability_{lab}'] == effective
            assert row[f'pre_capability_{lab}'] == max(0, t-1-dc)*effort
            assert effective + row[f'pending_capability_{lab}'] == t*effort
            arrived = max(0, t-ds)*(1-effort)
            assert arrived + row[f'pending_safety_{lab}'] == t*(1-effort)
            safety += arrived
            pre_safety += max(0, t-1-ds)*(1-effort)
        assert row['post_safety'] == safety
        assert row['pre_safety'] == pre_safety


def test_one_period_delay_and_terminal_credit():
    result = simulate(Config(horizon=3, noise=0, hazard_scale=0, capability_delay_a=1),
                      FixedPolicy(1), FixedPolicy(0), np.random.default_rng(1), trace=True)
    assert [r['post_capability_a'] for r in result['history']] == [0, 1, 2]
    result = simulate(Config(horizon=3, noise=0, hazard_scale=0, capability_delay_a=4),
                      FixedPolicy(1), FixedPolicy(.1), np.random.default_rng(1))
    assert result['pending_capability_a'] == 3
    assert result['payoff_a'] == 0 and result['payoff_b'] == 10


def test_fatal_period_retains_pending_and_arrivals_affect_risk():
    cfg = Config(horizon=5, noise=0, hazard_scale=1e6, capability_delay_a=1, safety_delay_b=9)
    result = simulate(cfg, FixedPolicy(1), FixedPolicy(0), np.random.default_rng(1), trace=True)
    assert result['steps'] == 2 and result['catastrophe']
    assert result['history'][-1]['pre_capability_a'] == 0
    assert result['capability_a'] == result['pending_capability_a'] == 1
    assert result['pending_safety_b'] == 1.2 and result['safety'] == 0


def test_noisy_production_is_drawn_at_investment():
    cfg = Config(horizon=4, hazard_scale=0, capability_delay_a=2, capability_delay_b=8)
    rng = np.random.default_rng(8)
    produced = []
    for _ in range(4):
        produced.append(cfg.capability_rate*np.array([.7, .4])*rng.lognormal(-.5*cfg.noise**2, cfg.noise, size=2))
        rng.random()
    actual_rng = np.random.default_rng(8)
    result = simulate(cfg, FixedPolicy(.7), FixedPolicy(.4), actual_rng)
    assert actual_rng.bit_generator.state == rng.bit_generator.state
    assert result['capability_a'] == sum(x[0] for x in produced[:2])
    assert result['pending_capability_a'] == sum(x[0] for x in produced[2:])
    assert result['pending_capability_b'] == sum(x[1] for x in produced)


def test_runner_delay_sweep_and_metadata(tmp_path):
    document = json.loads(Path('experiments/laptop/configs/graduated.json').read_text())
    document.update(trials=2, category='test')
    document['model']['horizon'] = 3
    path = tmp_path/'config.json'
    path.write_text(json.dumps(document))
    output = tmp_path/'run'
    runner.main(['--config', str(path), '--output', str(output), '--quiet', '--save-trajectories',
                 '--sweep', 'model.capability_delay_a=0,1',
                 '--set', 'model.safety_delay_a=0', '--set', 'model.capability_delay_b=0', '--set', 'model.safety_delay_b=0'])
    manifest = json.loads((output/'manifest.json').read_text())
    assert manifest['output_schema_version'] == 3
    assert manifest['observation']['pending_work_visible']
    assert all(e['model_id'] == 'FG-M005' for e in manifest['experiments'])
    assert [e['behavior_model_id'] for e in manifest['experiments']] == ['FG-M003', 'FG-M004']
    for entry in manifest['experiments']:
        folder = output/entry['output_path']
        meta = json.loads((folder/'metadata.json').read_text())
        assert meta['model_id'] == entry['model_id'] == 'FG-M005'
        assert meta['observation'] == manifest['observation']
        assert meta['behavior_model_id'] == entry['behavior_model_id']
        assert meta['resolved_config'] == entry['resolved_config']
        assert meta['output_schema_version'] == 3
        assert all(k in meta['diagnostics']['definitions'] for k in PENDING)
        for filename in ('episodes.csv', 'trajectory.csv', 'trajectories.csv.gz'):
            assert set(PENDING) <= set(pd.read_csv(folder/filename).columns)


@pytest.mark.parametrize('a,b,expected', [(FixedPolicy(.5), FixedPolicy(.5), 'FG-M001'),
    (SafetyGapPolicy(), FixedPolicy(.5), 'FG-M002'),
    (ThresholdInterventionPolicy(), FixedPolicy(.5), 'FG-M003')])
def test_classification(a, b, expected):
    assert runner.behavior_model_id_for(a, b, Config()) == expected
    for name in DELAYS:
        assert runner.behavior_model_id_for(a, b, Config(**{name:1})) == 'FG-M004'


@pytest.mark.parametrize('name', DELAYS)
def test_each_delay_json_override_and_sweep(name):
    document = json.loads(Path('experiments/laptop/configs/graduated.json').read_text())
    plans = runner.resolve_experiments(document, [], runner.sweep_rows([f'model.{name}=0,2']))
    assert [getattr(p['prepared'][0], name) for p in plans] == [0, 2]
    assert name not in document['model']
    for invalid in ('true', '-1', '0.5', '1.0'):
        effective, _ = runner.apply_overrides(document, [f'model.{name}={invalid}'])
        with pytest.raises(ValueError):
            runner.parse_config(effective)


def test_due_safety_protects_during_current_update():
    config = Config(horizon=3, noise=0, hazard_scale=1e6, safety_rate=1,
                    capability_delay_a=1, safety_delay_b=1)
    result = simulate(config, FixedPolicy(1), FixedPolicy(0), np.random.default_rng(1), trace=True)
    assert not result['catastrophe']
    assert [r['post_safety'] for r in result['history']] == [0, 1, 2]
    assert all(r['post_hazard'] == 0 for r in result['history'])
