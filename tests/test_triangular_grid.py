"""Checks for the experiment's symmetry reconstruction and response analysis."""
import importlib.util
from pathlib import Path

import pandas as pd

spec = importlib.util.spec_from_file_location('triangular_grid', Path(__file__).resolve().parents[1] / 'experiments/laptop/triangular_grid.py')
grid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grid)


def test_reversal_keeps_raw_diagonal_and_swaps_uncertainty():
    rows = []
    for a, b, pa, pb in [(0, 0, 4, 6), (0, 1, 2, 8), (1, 1, 7, 3)]:
        row = dict(a=a, b=b, catastrophe_mean=0, steps_mean=30)
        for field in grid.FIELDS:
            row[f'payoff_a_{field}'] = pa if field != 'interval' else 'A'
            row[f'payoff_b_{field}'] = pb if field != 'interval' else 'B'
        rows.append(row)
    result = grid.reconstruct(pd.DataFrame(rows)).set_index(['a', 'b'])
    assert len(result) == 4
    assert result.loc[(0, 0), 'payoff_a_mean'] == 4
    assert result.loc[(0, 0), 'payoff_b_mean'] == 6
    assert result.loc[(1, 0), 'payoff_a_mean'] == 8
    assert result.loc[(1, 0), 'payoff_b_mean'] == 2
    assert result.loc[(1, 0), 'payoff_a_interval'] == 'B'
    assert result.loc[(1, 0), 'steps_mean'] == 30


def test_ties_are_all_reported():
    frame = pd.DataFrame([dict(a=a, b=b, payoff_a_mean=5, payoff_b_mean=5)
                          for a in (0, 1) for b in (0, 1)])
    responses, gains, candidates = grid.analyze(frame)
    assert len(responses) == 8 and (responses.tie_count == 2).all()
    assert len(candidates) == 4 and (gains.max_deviation_gain == 0).all()


def test_no_mutual_response_and_unilateral_gain():
    frame = pd.DataFrame([dict(a=a, b=b, payoff_a_mean=int(a == b), payoff_b_mean=int(a != b))
                          for a in (0, 1) for b in (0, 1)])
    responses, gains, candidates = grid.analyze(frame)
    assert candidates.empty
    assert (gains.max_deviation_gain == 1).all()
    assert (responses.tie_count == 1).all()
    row = gains[(gains.a == 0) & (gains.b == 0)].iloc[0]
    assert row.deviation_gain_a == 0 and row.deviation_gain_b == 1
