"""Independent episodes, Monte Carlo errors, and bounded event intervals."""
from typing import Callable
import numpy as np
import pandas as pd
from scipy.stats import t, norm
from .model import Config, Policy, simulate


def run_trials(config: Config, policy_a: Policy, policy_b: Policy,
               trials: int = 1000, seed: int = 42, *,
               trace_sink: Callable[[int, list[dict]], None] | None = None,
               trace_decision_gaps: bool = False) -> pd.DataFrame:
    """Optionally deliver one completed episode trace at a time to trace_sink.

    The sink receives (zero-based trial ID, history). Trace buffering is bounded
    by one episode (at most config.horizon rows), not the trial count.
    trace_decision_gaps opts this sink into policy-gap fields; it defaults off.
    These fields never enter the returned episode DataFrame.
    """
    if type(trials) is not int or trials < 2:
        raise ValueError("trials must be an integer >= 2 for uncertainty estimates")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    if trace_decision_gaps and trace_sink is None:
        raise ValueError('trace_decision_gaps requires a trace_sink')
    children = np.random.SeedSequence(seed).spawn(trials)
    outcomes = []
    for i, child in enumerate(children):
        outcome = simulate(config, policy_a, policy_b, np.random.default_rng(child),
                           trace=trace_sink is not None, trace_decision_gaps=trace_decision_gaps)
        if trace_sink is not None:
            history = outcome.pop('history')
            trace_sink(i, history)
            del history
        outcomes.append(dict(trial=i, **outcome))
    return pd.DataFrame(outcomes)


def summarize(frame: pd.DataFrame) -> pd.DataFrame:
    """Approximate marginal 95% intervals; no multiple-comparison correction."""
    n = len(frame)
    if n < 2:
        raise ValueError("at least two episodes are required")
    rows = []
    for metric in ("payoff_a", "payoff_b", "catastrophe", "steps"):
        values = frame[metric].astype(float)
        mean = float(values.mean())
        se = float(values.std(ddof=1) / np.sqrt(n))
        if metric == "catastrophe":
            z = norm.ppf(0.975)
            denominator = 1 + z*z/n
            center = (mean + z*z/(2*n)) / denominator
            half = z*np.sqrt(mean*(1-mean)/n + z*z/(4*n*n))/denominator
            low, high = max(0.0, center-half), min(1.0, center+half)
            method = "Wilson"
        else:
            half = float(t.ppf(0.975, n-1)) * se
            low, high = mean-half, mean+half
            method = "Student-t approximate"
        rows.append(dict(metric=metric, n=n, mean=mean, standard_error=se,
                         ci_low=low, ci_high=high, interval=method))
    return pd.DataFrame(rows)
