"""Compare nine constant A allocations against B=0.4 using the existing engine.

From the repository root:
    .\.venv\Scripts\python.exe experiments/laptop/sweep_allocations.py
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform

import pandas as pd

from frontier_game import Config, FixedPolicy, run_trials, summarize


A_ALLOCATIONS = (0.3, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.8)
B_ALLOCATION = 0.4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=1000, help="Episodes per allocation")
    parser.add_argument("--seed", type=int, default=42, help="First scenario seed")
    parser.add_argument("--output", type=Path, help="New results directory")
    args = parser.parse_args()
    if args.trials < 2 or args.seed < 0:
        parser.error("trials must be >= 2 and seed must be nonnegative")

    config = Config()
    output = args.output or Path("results") / datetime.now(timezone.utc).strftime(
        "sweep-%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    summaries = []
    scenario_settings = []
    for index, allocation in enumerate(A_ALLOCATIONS):
        # Separate reproducible seeds avoid deliberately pairing the scenarios.
        seed = args.seed + index
        print(f"Running A={allocation:.2f}, B={B_ALLOCATION:.2f}, seed={seed}", flush=True)
        episodes = run_trials(config, FixedPolicy(allocation), FixedPolicy(B_ALLOCATION),
                              trials=args.trials, seed=seed)
        episodes.to_csv(output / f"episodes-a-{allocation:.2f}.csv", index=False)
        summary = summarize(episodes)
        summary.insert(0, "a", allocation)
        summary.insert(1, "b", B_ALLOCATION)
        summary.insert(2, "seed", seed)
        summaries.append(summary)
        scenario_settings.append(dict(a=allocation, b=B_ALLOCATION, seed=seed))

    combined = pd.concat(summaries, ignore_index=True)
    combined.to_csv(output / "summary.csv", index=False)
    comparison = combined.pivot(index="a", columns="metric", values="mean")
    comparison = comparison[["payoff_a", "payoff_b", "catastrophe", "steps"]]
    comparison.to_csv(output / "comparison.csv")
    metadata = dict(config=asdict(config), trials_per_allocation=args.trials,
                    scenarios=scenario_settings, python=platform.python_version(),
                    versions={p: version(p) for p in ["frontier-game", "numpy", "pandas", "scipy"]})
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print("\nMean outcomes (B fixed at 0.4):")
    print(comparison.to_string(float_format=lambda value: f"{value:.4f}"))
    print("\nExploratory comparisons: see summary.csv for marginal uncertainty intervals.")
    print(f"Saved to {output.resolve()}")


if __name__ == "__main__":
    main()
