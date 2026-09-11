"""Run independently configured fixed, safety-gap, graduated, or threshold-intervention policies from strict JSON."""
import argparse
import csv
import gzip
from contextlib import nullcontext
import io
from itertools import product
from copy import deepcopy
import math
from dataclasses import asdict, fields, MISSING
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter, sleep

import numpy as np
import pandas as pd
from frontier_game.model import DIAGNOSTIC_DEFINITIONS, OUTPUT_SCHEMA_VERSION
from frontier_game import (Config, FixedPolicy, GraduatedPolicy, SafetyGapPolicy,
                            ThresholdInterventionPolicy, run_trials, simulate, summarize)

# Support both direct script execution and package imports in tests.
if __package__:
    from .safety_gap import code_provenance, save_metadata, utc_now
else:
    from safety_gap import code_provenance, save_metadata, utc_now

POLICY_TYPES = {'fixed': FixedPolicy,
                'safety_gap': SafetyGapPolicy,
                'graduated': GraduatedPolicy,
                'threshold_intervention': ThresholdInterventionPolicy}


def model_id_for(policy_a, policy_b):
    if any(isinstance(policy, (GraduatedPolicy, ThresholdInterventionPolicy)) for policy in (policy_a, policy_b)):
        return 'FG-M003'
    if any(isinstance(policy, SafetyGapPolicy) for policy in (policy_a, policy_b)):
        return 'FG-M002'
    return 'FG-M001'


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


def apply_overrides(document, specifications):
    """Return a separate input copy and ordered audit records for scalar overrides."""
    effective = deepcopy(document)
    records = []
    seen = set()
    for specification in specifications:
        path, separator, raw_value = specification.partition('=')
        if not separator or not path or any(not part for part in path.split('.')):
            raise ValueError(f'--set {specification!r}: expected a nonempty PATH=VALUE')
        if path in seen:
            raise ValueError(f'--set: duplicate override path: {path}')
        parts = path.split('.')
        original = document
        target = effective
        for part in parts[:-1]:
            if not isinstance(original, dict) or part not in original:
                raise ValueError(f'--set: unknown path: {path}')
            original = original[part]
            target = target[part]
        leaf = parts[-1]
        if not isinstance(original, dict) or leaf not in original:
            raise ValueError(f'--set: unknown path: {path}')
        if isinstance(original[leaf], (dict, list)):
            raise ValueError(f'--set {path}: target must be an existing scalar field')
        try:
            value = json.loads(raw_value, parse_constant=reject_constant)
        except ValueError as error:
            raise ValueError(f'--set {path}: invalid JSON value: {error}') from error
        if isinstance(value, (dict, list)):
            raise ValueError(f'--set {path}: value must be a JSON scalar')
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f'--set {path}: number must be finite')
        target[leaf] = value
        seen.add(path)
        records.append(dict(path=path, value=value, argument=specification))
    return effective, records


def execute_experiment(source, document, input_path, overrides, prepared, output,
                       run_command, provenance, quiet=False, save_trajectories=False):
    """The same execution and output format for single runs and sweep members."""
    config, policy_a, policy_b, resolved = prepared
    seed, trials = resolved['seed'], resolved['trials']
    metadata = dict(model_id=model_id_for(policy_a, policy_b),
                    metadata_schema_version=1, output_schema_version=OUTPUT_SCHEMA_VERSION, run_id=output.name,
                    diagnostics=dict(definitions=DIAGNOSTIC_DEFINITIONS,
                        periods='Executed periods only, including terminal catastrophe.'),
                    full_trajectories=dict(enabled=save_trajectories,
                        filename='trajectories.csv.gz' if save_trajectories else None,
                        status='pending' if save_trajectories else 'disabled',
                        completed_trials=0, rows=0, buffering='one completed episode',
                        seed_column='experiment_seed', trial_column='trial', period_column='step'),
                    experiment_name=resolved['name'], description=resolved['description'], category=resolved['category'],
                    input_config=document, overrides=overrides, input_config_path=str(input_path.resolve()), resolved_config=resolved,
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
                    run_command=run_command, **provenance)
    output.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    save_metadata(output, metadata)
    try:
        (output / 'input_config.json').write_bytes(source)
        trace_info = metadata['full_trajectories']
        stream_context = (gzip.open(output / 'trajectories.csv.gz', 'wt', encoding='utf-8', newline='')
                          if save_trajectories else nullcontext(None))
        with stream_context as stream:
            writer = None

            def save_history(trial, history):
                nonlocal writer
                if writer is None:
                    writer = csv.DictWriter(stream, fieldnames=['experiment_seed', 'trial', *history[0]])
                    writer.writeheader()
                for row in history:
                    writer.writerow(dict(experiment_seed=seed, trial=trial, **row))
                stream.flush()
                trace_info['rows'] += len(history)
                trace_info['completed_trials'] += 1

            if save_trajectories:
                trace_info['status'] = 'writing'
                episodes = run_trials(config, policy_a, policy_b, trials=trials, seed=seed,
                                      trace_sink=save_history)
            else:
                episodes = run_trials(config, policy_a, policy_b, trials=trials, seed=seed)
        if save_trajectories:
            trace_info['status'] = 'complete'

        episodes.to_csv(output / 'episodes.csv', index=False)
        metadata['completed_trials'] = len(episodes)
        summary = summarize(episodes)
        summary.to_csv(output / 'summary.csv', index=False)
        trajectory = simulate(config, policy_a, policy_b, np.random.default_rng(seed+1), trace=True)
        pd.DataFrame(trajectory['history']).to_csv(output / 'trajectory.csv', index=False)
        metadata['status'] = 'complete'
        if not quiet:
            print(summary.to_string(index=False))
            print(metadata['source_provenance_note'])
            print(f'Saved to {output.resolve()}')
        return summary
    except BaseException as error:
        if save_trajectories and metadata['full_trajectories']['status'] != 'complete':
            metadata['full_trajectories']['status'] = 'incomplete'
        metadata['status'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        metadata['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        metadata['ended_utc'] = utc_now()
        metadata['elapsed_seconds'] = perf_counter() - started
        save_metadata(output, metadata)


def sweep_rows(specifications, csv_source=None):
    """Ordered override lists; the last CLI axis varies fastest."""
    if csv_source is not None:
        try:
            rows = list(csv.reader(io.StringIO(csv_source.decode('utf-8-sig'), newline=''), strict=True))
        except csv.Error as error:
            raise ValueError(f'invalid sweep CSV: {error}') from error
        if not rows or not rows[0] or any(not header.strip() for header in rows[0]):
            raise ValueError('sweep CSV needs nonblank path headers')
        headers = rows[0]
        if len(set(headers)) != len(headers):
            raise ValueError('duplicate sweep CSV headers')
        if len(rows) < 2:
            raise ValueError('sweep CSV needs at least one experiment row')
        variations = []
        for index, cells in enumerate(rows[1:], 2):
            if len(cells) != len(headers) or any(not cell.strip() for cell in cells):
                raise ValueError(f'sweep CSV row {index}: wrong column count or blank cell')
            variations.append([f'{path}={cell}' for path, cell in zip(headers, cells)])
        return variations
    axes, seen = [], set()
    for specification in specifications:
        path, separator, values = specification.partition('=')
        if not separator or not path or path in seen:
            raise ValueError(f'invalid or duplicate sweep path: {path!r}')
        seen.add(path)
        axis = []
        for raw in values.split(','):
            try:
                value = json.loads(raw, parse_constant=reject_constant)
            except ValueError as error:
                raise ValueError(f'--sweep {path}: invalid numeric value: {raw!r}') from error
            if type(value) not in (int, float) or (isinstance(value, float) and not math.isfinite(value)):
                raise ValueError(f'--sweep {path}: values must be finite numbers')
            axis.append(f'{path}={raw}')
        axes.append(axis)
    return [list(values) for values in product(*axes)]


def resolve_experiments(document, common, rows):
    """Preflight every variation independently, without output or RNG activity."""
    _, common_records = apply_overrides(document, common)
    fixed_paths = {record['path'] for record in common_records}
    plans = []
    for index, row in enumerate(rows, 1):
        try:
            _, varied = apply_overrides(document, row)
            overlap = fixed_paths & {record['path'] for record in varied}
            if overlap:
                raise ValueError(f'paths specified in both --set and sweep: {sorted(overlap)}')
            effective, overrides = apply_overrides(document, [*common, *row])
            prepared = parse_config(effective)
        except ValueError as error:
            raise ValueError(f'Experiment {index}: {error}') from error
        plans.append(dict(prepared=prepared, overrides=overrides,
                          varied_parameters={record['path']: record['value'] for record in varied}))
    return plans


def save_manifest(output, manifest):
    temporary = output / 'manifest.tmp'
    temporary.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    for attempt in range(10):
        try:
            temporary.replace(output / 'manifest.json')
            return
        except PermissionError:
            if attempt == 9:
                raise
            sleep(.1)


def execute_sweep(source, document, args, plans, csv_source, command, provenance):
    output = args.output or Path('results') / datetime.now(timezone.utc).strftime('sweep-%Y%m%dT%H%M%S%fZ')
    manifest = dict(output_schema_version=OUTPUT_SCHEMA_VERSION, save_trajectories=args.save_trajectories,
                    input_config=document, input_config_path=str(args.config.resolve()),
                    sweep_specification=dict(set=args.overrides, sweep=args.sweep,
                        sweep_csv=str(args.sweep_csv.resolve()) if args.sweep_csv else None,
                        csv_text=csv_source.decode('utf-8-sig') if csv_source is not None else None),
                    run_command=command, started_utc=utc_now(), ended_utc=None, status='running',
                    completed_experiments=0, total_experiments=len(plans),
                    total_histories=sum(plan['prepared'][3]['trials'] for plan in plans),
                    seed_rule='Configured seed retained per variation; trial i uses SeedSequence(seed) child i.',
                    experiments=[dict(experiment_id=i, output_path=f'{i:04d}', status='pending',
                        varied_parameters=plan['varied_parameters'], overrides=plan['overrides'],
                        resolved_config=plan['prepared'][3], seed=plan['prepared'][3]['seed'],
                        model_id=model_id_for(plan['prepared'][1], plan['prepared'][2]))
                        for i, plan in enumerate(plans, 1)], **provenance)
    output.mkdir(parents=True, exist_ok=False)
    save_manifest(output, manifest)
    summaries = []
    active = None
    try:
        (output / 'input_config.json').write_bytes(source)
        if csv_source is not None:
            (output / 'sweep_input.csv').write_bytes(csv_source)
        for plan, entry in zip(plans, manifest['experiments']):
            active = entry
            entry['status'] = 'running'
            save_manifest(output, manifest)
            if not args.quiet:
                values = ', '.join(f'{path}={json.dumps(value)}' for path, value in plan['varied_parameters'].items())
                print(f'Experiment {entry["experiment_id"]}/{len(plans)}: {values}', flush=True)
            summary = execute_experiment(source, document, args.config, plan['overrides'], plan['prepared'],
                                         output / entry['output_path'], command, provenance, args.quiet, args.save_trajectories)
            combined = summary.copy()
            combined.insert(0, 'experiment_id', entry['experiment_id'])
            for path, value in plan['varied_parameters'].items():
                combined[f'parameter.{path}'] = value
            summaries.append(combined)
            pd.concat(summaries, ignore_index=True).to_csv(output / 'summary.csv', index=False)
            entry['status'] = 'complete'
            manifest['completed_experiments'] += 1
            save_manifest(output, manifest)
            active = None
        manifest['status'] = 'complete'
    except BaseException as error:
        manifest['status'] = 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
        manifest['error'] = f'{type(error).__name__}: {error}'
        if active is not None:
            active['status'] = manifest['status']
            active['error'] = manifest['error']
            manifest['failed_experiment_id'] = active['experiment_id']
        raise
    finally:
        manifest['ended_utc'] = utc_now()
        save_manifest(output, manifest)
        print(f'Completed {manifest["completed_experiments"]}/{len(plans)} experiments; sweep output: {output.resolve()}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, help='New directory; refuses to overwrite')
    parser.add_argument('--set', dest='overrides', action='append', default=[], metavar='PATH=VALUE')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--sweep', action='append', default=[], metavar='PATH=V1,V2,...')
    modes.add_argument('--sweep-csv', type=Path)
    parser.add_argument('--dry-run', action='store_true', help='Show resolved settings without simulation or output files')
    parser.add_argument('--quiet', action='store_true', help='Suppress tables and routine progress; retain errors and completion')
    parser.add_argument('--save-trajectories', action='store_true',
                        help='Stream every Monte Carlo history to trajectories.csv.gz')
    args = parser.parse_args(argv)
    try:
        source = args.config.read_bytes()
        document = json.loads(source.decode('utf-8-sig'), object_pairs_hook=unique_object, parse_constant=reject_constant)
        csv_source = args.sweep_csv.read_bytes() if args.sweep_csv else None
        is_sweep = bool(args.sweep) or args.sweep_csv is not None
        rows = sweep_rows(args.sweep, csv_source) if is_sweep else [[]]
        plans = resolve_experiments(document, args.overrides, rows)
    except (OSError, UnicodeError, ValueError) as error:
        parser.error(f'{args.config}: {error}')
    if args.dry_run:
        print(json.dumps(dict(experiment_count=len(plans),
            total_histories=sum(plan['prepared'][3]['trials'] for plan in plans),
            variations=[dict(experiment_id=i, varied_parameters=plan['varied_parameters'],
                             resolved_config=plan['prepared'][3]) for i, plan in enumerate(plans, 1)]), indent=2))
        return
    command = subprocess.list2cmdline([sys.executable, str(Path(__file__)), *(sys.argv[1:] if argv is None else argv)])
    provenance = code_provenance()
    try:
        if is_sweep:
            execute_sweep(source, document, args, plans, csv_source, command, provenance)
        else:
            output = args.output or Path('results') / datetime.now(timezone.utc).strftime('experiment-%Y%m%dT%H%M%S%fZ')
            plan = plans[0]
            execute_experiment(source, document, args.config, plan['overrides'], plan['prepared'], output,
                               command, provenance, args.quiet, args.save_trajectories)
            if args.quiet:
                print(f'Completed 1/1 experiments; output: {output.resolve()}')
    except BaseException as error:
        print(f'Error: {type(error).__name__}: {error}', file=sys.stderr)
        raise


if __name__ == '__main__':
    main()
