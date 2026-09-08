"""Exploratory triangular allocation grid; reuse the existing simulation engine."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
from time import perf_counter, sleep

import numpy as np
import pandas as pd
from frontier_game import Config, FixedPolicy, run_trials, summarize

ALLOCATIONS = tuple(i / 20 for i in range(21))
TOL = 1e-12  # Numerical ties, not statistical equivalence.
FIELDS = ('mean', 'standard_error', 'ci_low', 'ci_high', 'interval')


def reconstruct(triangle):
    reverse = triangle[triangle.a < triangle.b].copy()
    reverse[['a', 'b']] = reverse[['b', 'a']].to_numpy()
    for field in FIELDS:
        cols = [f'payoff_a_{field}', f'payoff_b_{field}']
        reverse[cols] = reverse[cols[::-1]].to_numpy()
    # Diagonal observations remain exactly as estimated.
    return pd.concat([triangle, reverse], ignore_index=True).sort_values(
        ['a', 'b']).reset_index(drop=True)


def analyze(grid):
    gains = grid.copy()
    responses = []
    for player, opponent in [('a', 'b'), ('b', 'a')]:
        best = gains.groupby(opponent)[f'payoff_{player}_mean'].transform('max')
        gains[f'deviation_gain_{player}'] = best - gains[f'payoff_{player}_mean']
        for allocation, group in gains.groupby(opponent):
            ties = group[group[f'deviation_gain_{player}'] <= TOL]
            for _, row in ties.iterrows():
                responses.append(dict(player=player.upper(), opponent_allocation=allocation,
                                      best_response=row[player], estimated_payoff=row[f'payoff_{player}_mean'],
                                      tie_count=len(ties)))
    gains['max_deviation_gain'] = gains[['deviation_gain_a', 'deviation_gain_b']].max(axis=1)
    return pd.DataFrame(responses), gains, gains[gains.max_deviation_gain <= TOL]


def validate(triangle, grid, config):
    expected = {(a, b) for a in ALLOCATIONS for b in ALLOCATIONS if a <= b}
    assert len(triangle) == 231 and set(zip(triangle.a, triangle.b)) == expected
    assert len(grid) == 441 and len(grid[['a', 'b']].drop_duplicates()) == 441
    indexed = grid.set_index(['a', 'b'])
    for row in triangle.itertuples():
        direct = indexed.loc[(row.a, row.b)]
        assert direct.payoff_a_mean == row.payoff_a_mean
        assert direct.payoff_b_mean == row.payoff_b_mean
        if row.a < row.b:
            reverse = indexed.loc[(row.b, row.a)]
            for field in FIELDS:
                assert reverse[f'payoff_a_{field}'] == getattr(row, f'payoff_b_{field}')
                assert reverse[f'payoff_b_{field}'] == getattr(row, f'payoff_a_{field}')
            assert reverse.catastrophe_mean == row.catastrophe_mean
            assert reverse.steps_mean == row.steps_mean
    p = grid.catastrophe_mean
    np.testing.assert_allclose(grid.payoff_a_mean + grid.payoff_b_mean,
                               config.first_mover_value * (1-p) - 2*config.catastrophe_cost*p,
                               rtol=1e-12, atol=1e-12)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trials', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=2026)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.trials < 2 or args.seed < 0:
        parser.error('trials must be >= 2 and seed must be nonnegative')
    config = Config()
    pairs = [dict(a=a, b=b, seed=args.seed+i) for i, (a, b) in enumerate(
        (a, b) for a in ALLOCATIONS for b in ALLOCATIONS if a <= b)]
    output = args.output or Path('results') / datetime.now(timezone.utc).strftime(
        'triangular-grid-%Y%m%dT%H%M%S%fZ')
    output.mkdir(parents=True, exist_ok=False)
    metadata = dict(config=asdict(config), allocation_grid=ALLOCATIONS,
                    master_seed=args.seed, seed_rule='master_seed + zero-based pair index',
                    seed_mapping=pairs, trials_per_pair=args.trials, completed_pairs=0,
                    status='running', elapsed_simulation_seconds=0.0,
                    python=platform.python_version(), platform=platform.platform(), processor=platform.processor(),
                    versions={p: version(p) for p in ['frontier-game', 'numpy', 'pandas', 'scipy']},
                    tie_tolerance=TOL,
                    interpretation='Exploratory discrete grid; marginal intervals do not adjust for selection or multiple comparisons.')

    def save_metadata():
        temporary = output / 'metadata.tmp'
        temporary.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        # Windows readers/scanners can briefly lock the destination.
        for attempt in range(10):
            try:
                temporary.replace(output / 'metadata.json')
                break
            except PermissionError:
                if attempt == 9:
                    raise
                sleep(0.1)

    summaries, rows = [], []
    started = perf_counter()
    save_metadata()
    try:
        for index, pair in enumerate(pairs, 1):
            a, b, seed = pair['a'], pair['b'], pair['seed']
            print(f'Pair {index}/231: A={a:.2f}, B={b:.2f}', flush=True)
            tick = perf_counter()
            episodes = run_trials(config, FixedPolicy(a), FixedPolicy(b), trials=args.trials, seed=seed)
            metadata['elapsed_simulation_seconds'] += perf_counter() - tick
            tag = f'a-{a:.2f}-b-{b:.2f}'
            episodes.to_csv(output / f'episodes-{tag}.csv', index=False)
            summary = summarize(episodes)
            for name, value in reversed(list(dict(a=a, b=b, seed=seed, trials=args.trials).items())):
                summary.insert(0, name, value)
            summary.to_csv(output / f'summary-{tag}.csv', index=False)
            summaries.append(summary)
            row = dict(a=a, b=b, seed=seed, trials=args.trials)
            for item in summary.to_dict('records'):
                for field in FIELDS:
                    row[f'{item["metric"]}_{field}'] = item[field]
            rows.append(row)
            metadata['completed_pairs'] = index
            save_metadata()
        triangle = pd.DataFrame(rows)
        triangle.to_csv(output / 'triangular.csv', index=False)
        pd.concat(summaries, ignore_index=True).to_csv(output / 'summary.csv', index=False)
        grid = reconstruct(triangle)
        grid.to_csv(output / 'ordered_grid.csv', index=False)
        validate(triangle, grid, config)
        responses, gains, candidates = analyze(grid)
        responses.to_csv(output / 'best_responses.csv', index=False)
        gains.to_csv(output / 'deviation_gains.csv', index=False)
        candidates.to_csv(output / 'mutual_best_responses.csv', index=False)
        closest = gains.nsmallest(5, 'max_deviation_gain', keep='all')
        closest.to_csv(output / 'smallest_deviation_gains.csv', index=False)
        metadata['validation'] = 'passed: pair counts, reversal, raw diagonal, payoff accounting'
        metadata['status'] = 'complete'
        print('\nExploratory discrete-grid best responses (all numerical ties retained):')
        print(responses.to_string(index=False))
        print(f'\nMutual best-response candidates: {len(candidates)}')
        report = candidates if len(candidates) else closest
        print(report[['a', 'b', 'deviation_gain_a', 'deviation_gain_b', 'max_deviation_gain']].to_string(index=False))
        print('Sample estimates do not establish continuous-action equilibrium or statistical significance.')
    except BaseException:
        metadata['status'] = 'interrupted_or_failed'
        raise
    finally:
        metadata['elapsed_seconds'] = perf_counter() - started
        save_metadata()
        print(f'Saved {metadata["completed_pairs"]}/231 pairs to {output.resolve()}', flush=True)
        print(f'Elapsed: {metadata["elapsed_seconds"]:.2f}s; simulation: {metadata["elapsed_simulation_seconds"]:.2f}s')


if __name__ == '__main__':
    main()
