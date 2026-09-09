"""Run independently configured fixed or safety-gap policies from strict JSON."""
import argparse
from dataclasses import asdict, fields, MISSING
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

import numpy as np
import pandas as pd
from frontier_game import Config, FixedPolicy, SafetyGapPolicy, run_trials, simulate, summarize

# Support both direct script execution and package imports in tests.
if __package__:
    from .safety_gap import code_provenance, save_metadata, utc_now
else:
    from safety_gap import code_provenance, save_metadata, utc_now

POLICY_TYPES = {'fixed': FixedPolicy, 'safety_gap': SafetyGapPolicy}


def check_keys(value, allowed, required, location):
    if not isinstance(value, dict):
        raise ValueError(f'{location} must be a JSON object')
    unknown = set(value) - set(allowed)
    missing = set(required) - set(value)
    if unknown:
        raise ValueError(f'{location}: unknown keys: {", ".join(sorted(unknown))}')
    if missing:
        raise ValueError(f'{location}: missing required keys: {", ".join(sorted(missing))}')


def construct_parameters(cls, parameters, location):
    definitions = fields(cls)
    required = [f.name for f in definitions if f.default is MISSING and f.default_factory is MISSING]
    check_keys(parameters, [f.name for f in definitions], required, location)
    for name, value in parameters.items():
        if type(value) not in (int, float):
            raise ValueError(f'{location}.{name} must be a number (not a boolean or string)')
    try:
        return cls(**parameters)
    except (ValueError, TypeError, OverflowError) as error:
        raise ValueError(f'{location}: {error}') from error


def construct_policy(specification, location):
    check_keys(specification, ('type', 'parameters'), ('type', 'parameters'), location)
    identifier = specification['type']
    if not isinstance(identifier, str) or identifier not in POLICY_TYPES:
        raise ValueError(f'{location}.type must be one of: {", ".join(POLICY_TYPES)}')
    return construct_parameters(POLICY_TYPES[identifier], specification['parameters'], f'{location}.parameters')


def parse_config(document):
    """Validate everything before I/O or simulation; resolve omitted dataclass defaults."""
    required = ('name', 'description', 'model', 'trials', 'seed', 'policies')
    check_keys(document, (*required, 'category'), required, 'config')
    for name in ('name', 'description'):
        if not isinstance(document[name], str) or not document[name].strip():
            raise ValueError(f'config.{name} must be a nonempty string')
    if type(document['trials']) is not int or document['trials'] < 2:
        raise ValueError('config.trials must be an integer >= 2')
    if type(document['seed']) is not int or document['seed'] < 0:
        raise ValueError('config.seed must be a nonnegative integer')
    category = document.get('category', 'research')
    if category not in ('research', 'smoke', 'test'):
        raise ValueError('config.category must be research, smoke, or test')
    config = construct_parameters(Config, document['model'], 'config.model')
    check_keys(document['policies'], ('a', 'b'), ('a', 'b'), 'config.policies')
    a = construct_policy(document['policies']['a'], 'config.policies.a')
    b = construct_policy(document['policies']['b'], 'config.policies.b')
    resolved = dict(name=document['name'], description=document['description'], category=category,
                    model=asdict(config), trials=document['trials'], seed=document['seed'],
                    policies={side: dict(type=document['policies'][side]['type'], parameters=asdict(policy))
                              for side, policy in [('a', a), ('b', b)]})
    return config, a, b, resolved


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f'invalid JSON numeric constant: {value}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, help='New directory; refuses to overwrite')
    args = parser.parse_args(argv)
    try:
        source = args.config.read_bytes()
        document = json.loads(source.decode('utf-8-sig'), object_pairs_hook=unique_object,
                              parse_constant=reject_constant)
        config, policy_a, policy_b, resolved = parse_config(document)
    except (OSError, UnicodeError, ValueError) as error:
        parser.error(f'{args.config}: {error}')
    seed, trials = resolved['seed'], resolved['trials']
    output = args.output or Path('results') / datetime.now(timezone.utc).strftime('experiment-%Y%m%dT%H%M%S%fZ')
    metadata = dict(model_id='FG-M001' if isinstance(policy_a, FixedPolicy) and isinstance(policy_b, FixedPolicy) else 'FG-M002',
                    metadata_schema_version=1, run_id=output.name,
                    experiment_name=resolved['name'], description=resolved['description'], category=resolved['category'],
                    input_config=document, input_config_path=str(args.config.resolve()), resolved_config=resolved,
                    config=asdict(config), initial_state=dict(capability_a=0.0, capability_b=0.0, shared_safety=0.0),
                    policies={side: dict(type=type(policy).__name__, identifier=resolved['policies'][side]['type'],
                                         parameters=asdict(policy)) for side, policy in [('a', policy_a), ('b', policy_b)]},
                    observation=dict(model_id='exact-pre-transition-v1', exact=True, delay_periods=0,
                                     period_indexing='1 through horizon, inclusive',
                                     fields=['period', 'horizon', 'own_capability', 'opponent_capability', 'shared_safety'],
                                     simultaneous=True, current_opponent_action_visible=False,
                                     fixed_policies_ignore_observations=True),
                    seed=seed, trials=trials, completed_trials=0,
                    trial_seed_rule='numpy SeedSequence(seed).spawn(trials)', trajectory_seed=seed+1,
                    seed_mapping=dict(episodes=dict(entropy=seed, spawn_keys=[[i] for i in range(trials)]),
                                      trajectory=dict(seed=seed+1)), trajectory_in_summary=False,
                    started_utc=utc_now(), ended_utc=None, status='running',
                    python=platform.python_version(), platform=platform.platform(),
                    versions={p: version(p) for p in ['frontier-game', 'numpy', 'pandas', 'scipy']},
                    run_command=subprocess.list2cmdline([sys.executable, str(Path(__file__)),
                                                         *(sys.argv[1:] if argv is None else argv)]),
                    **code_provenance())
    output.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    save_metadata(output, metadata)
    try:
        (output / 'input_config.json').write_bytes(source)
        episodes = run_trials(config, policy_a, policy_b, trials=trials, seed=seed)
        episodes.to_csv(output / 'episodes.csv', index=False)
        metadata['completed_trials'] = len(episodes)
        summary = summarize(episodes)
        summary.to_csv(output / 'summary.csv', index=False)
        trajectory = simulate(config, policy_a, policy_b, np.random.default_rng(seed+1), trace=True)
        pd.DataFrame(trajectory['history']).to_csv(output / 'trajectory.csv', index=False)
        metadata['status'] = 'complete'
        print(summary.to_string(index=False))
        print(metadata['source_provenance_note'])
        print(f'Saved to {output.resolve()}')
    except BaseException as error:
        metadata['status'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        metadata['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        metadata['ended_utc'] = utc_now()
        metadata['elapsed_seconds'] = perf_counter() - started
        save_metadata(output, metadata)


if __name__ == '__main__':
    main()
