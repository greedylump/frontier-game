"""Manual safety-gap experiment (FG-M005; FG-M002 behavior): two identical, immutable safety-gap rules."""
import argparse
from dataclasses import asdict
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
from frontier_game import Config, SafetyGapPolicy, run_trials, simulate, summarize

from frontier_game.model import observation_metadata

REPOSITORY = Path(__file__).resolve().parents[2]


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def code_provenance():
    """Include tracked changes and all untracked, non-ignored files."""
    def git(*args):
        return subprocess.run(['git', '-C', str(REPOSITORY), *args], check=True,
                              capture_output=True, text=True).stdout.strip()
    try:
        commit = git('rev-parse', 'HEAD')
        dirty = bool(git('status', '--porcelain', '--untracked-files=all'))
        note = ('Working tree is dirty: the commit alone does not identify executed source. '
                'A source snapshot is outside this task scope.' if dirty else
                'Working tree was clean at start; commit identifies repository source.')
        return dict(code_commit=commit, code_dirty=dirty, source_provenance_note=note)
    except (OSError, subprocess.CalledProcessError) as error:
        return dict(code_commit=None, code_dirty=None,
                    source_provenance_note=f'Git provenance unavailable: {error}; executed source is not identified.')


def save_metadata(output, metadata):
    temporary = output / 'metadata.tmp'
    temporary.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    # Windows scanners/readers can briefly hold the destination open.
    for attempt in range(10):
        try:
            temporary.replace(output / 'metadata.json')
            return
        except PermissionError:
            if attempt == 9:
                raise
            sleep(0.1)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trials', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=2026)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--normal-allocation', type=float, default=0.50)
    parser.add_argument('--cautious-allocation', type=float, default=0.30)
    parser.add_argument('--gap-threshold', type=float, default=0.0)
    parser.add_argument('--category', choices=['research', 'smoke', 'test'], default='research')
    args = parser.parse_args(argv)
    if args.trials < 2 or args.seed < 0:
        parser.error('trials must be >= 2 and seed must be nonnegative')
    try:
        config = Config()
        policy_a = SafetyGapPolicy(args.normal_allocation, args.cautious_allocation, args.gap_threshold)
        policy_b = SafetyGapPolicy(args.normal_allocation, args.cautious_allocation, args.gap_threshold)
    except ValueError as error:
        parser.error(str(error))
    output = args.output or Path('results') / datetime.now(timezone.utc).strftime('safety-gap-%Y%m%dT%H%M%S%fZ')
    provenance = code_provenance()
    output.mkdir(parents=True, exist_ok=False)
    metadata = dict(model_id='FG-M005', behavior_model_id='FG-M002', metadata_schema_version=1, run_id=output.name,
                    description='Two identical safety-gap rules with exact pre-transition observations',
                    category=args.category, config=asdict(config),
                    initial_state=dict(capability_a=0.0, capability_b=0.0, shared_safety=0.0),
                    policies={name: dict(type=type(policy).__name__, parameters=asdict(policy))
                              for name, policy in [('a', policy_a), ('b', policy_b)]},
                    observation=observation_metadata(),
                    seed=args.seed, trials=args.trials, completed_trials=0,
                    trial_seed_rule='numpy SeedSequence(seed).spawn(trials)',
                    trajectory_seed=args.seed+1, trajectory_in_summary=False,
                    started_utc=utc_now(), ended_utc=None, status='running',
                    python=platform.python_version(), platform=platform.platform(),
                    versions={p: version(p) for p in ['frontier-game', 'numpy', 'pandas', 'scipy']},
                    run_command=subprocess.list2cmdline([sys.executable, str(Path(__file__)),
                                                         *(sys.argv[1:] if argv is None else argv)]),
                    **provenance)
    started = perf_counter()
    save_metadata(output, metadata)
    try:
        episodes = run_trials(config, policy_a, policy_b, trials=args.trials, seed=args.seed)
        episodes.to_csv(output / 'episodes.csv', index=False)
        metadata['completed_trials'] = len(episodes)
        summary = summarize(episodes)
        summary.to_csv(output / 'summary.csv', index=False)
        illustrative = simulate(config, policy_a, policy_b,
                                np.random.default_rng(metadata['trajectory_seed']), trace=True)
        pd.DataFrame(illustrative['history']).to_csv(output / 'trajectory.csv', index=False)
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
