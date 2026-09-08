"""Independent episodes, Monte Carlo errors, and bounded event intervals."""
import numpy as np
import pandas as pd
from scipy.stats import t, norm
from .model import Config, FixedPolicy, simulate


def run_trials(config: Config, policy_a: FixedPolicy, policy_b: FixedPolicy,
               trials: int = 1000, seed: int = 42) -> pd.DataFrame:
    if type(trials) is not int or trials < 2:
        raise ValueError("trials must be an integer >= 2 for uncertainty estimates")
    if type(seed) is not int or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    children = np.random.SeedSequence(seed).spawn(trials)
    return pd.DataFrame([
        dict(trial=i, **simulate(config, policy_a, policy_b, np.random.default_rng(child)))
        for i, child in enumerate(children)
    ])


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
