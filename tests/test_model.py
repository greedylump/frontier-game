import numpy as np
import pandas as pd
import pytest
from frontier_game import Config, FixedPolicy, simulate, run_trials, summarize


def test_no_risk_deterministic_winner_and_trace():
    result = simulate(Config(horizon=3, noise=0, hazard_scale=0),
                      FixedPolicy(1), FixedPolicy(0), np.random.default_rng(1), trace=True)
    assert result["capability_a"] == 3
    assert result["capability_b"] == 0
    assert result["safety"] == pytest.approx(1.8)
    assert result["payoff_a"] == 10
    assert result["payoff_b"] == 0
    assert len(result["history"]) == 3


def test_restraint_has_no_gap_or_catastrophe_and_splits_prize():
    result = simulate(Config(), FixedPolicy(0), FixedPolicy(0), np.random.default_rng(1))
    assert not result["catastrophe"]
    assert result["steps"] == 30
    assert result["payoff_a"] == result["payoff_b"] == 5


def test_catastrophe_is_absorbing_and_replaces_prize():
    result = simulate(Config(noise=0, hazard_scale=1e6), FixedPolicy(1), FixedPolicy(1),
                      np.random.default_rng(2), trace=True)
    assert result["catastrophe"]
    assert result["steps"] == len(result["history"]) == 1
    assert result["payoff_a"] == result["payoff_b"] == -50


def test_seed_reproduces_and_preserves_episode_prefix():
    args = (Config(), FixedPolicy(0.8), FixedPolicy(0.4))
    small = run_trials(*args, trials=12, seed=7)
    pd.testing.assert_frame_equal(small, run_trials(*args, trials=12, seed=7))
    pd.testing.assert_frame_equal(small, run_trials(*args, trials=20, seed=7).iloc[:12])
    assert not small.equals(run_trials(*args, trials=12, seed=8))


def test_summary_known_mean_and_nonzero_zero_event_upper_bound():
    frame = pd.DataFrame(dict(payoff_a=[0, 2], payoff_b=[2, 0], catastrophe=[False, False], steps=[1, 1]))
    summary = summarize(frame).set_index("metric")
    assert summary.loc["payoff_a", "mean"] == 1
    assert summary.loc["payoff_a", "standard_error"] == pytest.approx(1)
    assert 0 < summary.loc["catastrophe", "ci_high"] < 1


@pytest.mark.parametrize("allocation", [-0.1, 1.1, float("nan")])
def test_invalid_policy(allocation):
    with pytest.raises(ValueError):
        FixedPolicy(allocation)


@pytest.mark.parametrize("kwargs", [{"horizon":0}, {"horizon":2.5}, {"noise":-1}, {"hazard_scale":float("nan")}])
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)


def test_invalid_trials_and_seed():
    for kwargs in ({"trials":1}, {"seed":-1}):
        with pytest.raises(ValueError):
            run_trials(Config(), FixedPolicy(0), FixedPolicy(0), **kwargs)
