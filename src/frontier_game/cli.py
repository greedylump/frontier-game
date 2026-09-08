"""Save episode data, uncertainty estimates, metadata, and a small chart."""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import platform
import time
from .model import Config, FixedPolicy
from .monte_carlo import run_trials, summarize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--horizon", type=int, default=30)
    parser.add_argument("--a", type=float, default=0.8, help="A capability allocation")
    parser.add_argument("--b", type=float, default=0.4, help="B capability allocation")
    parser.add_argument("--output", type=Path, help="New directory; refuses to overwrite")
    args = parser.parse_args()
    try:
        config = Config(horizon=args.horizon)
        a, b = FixedPolicy(args.a), FixedPolicy(args.b)
        started = time.perf_counter()
        episodes = run_trials(config, a, b, args.trials, args.seed)
    except ValueError as error:
        parser.error(str(error))
    elapsed = time.perf_counter() - started
    output = args.output or Path("results") / datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S%fZ")
    output.mkdir(parents=True, exist_ok=False)
    summary = summarize(episodes)
    episodes.to_csv(output / "episodes.csv", index=False)
    summary.to_csv(output / "summary.csv", index=False)
    metadata = dict(config=asdict(config), policies=dict(a=asdict(a), b=asdict(b)),
                    seed=args.seed, trials=args.trials, elapsed_seconds=elapsed,
                    episodes_per_second=args.trials/elapsed,
                    python=platform.python_version(), platform=platform.platform(),
                    versions={p: version(p) for p in ["frontier-game", "numpy", "pandas", "scipy", "matplotlib"]})
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    payoffs = summary.set_index("metric").loc[["payoff_a", "payoff_b"]]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(["A", "B"], payoffs["mean"], yerr=payoffs["ci_high"]-payoffs["mean"], capsize=5)
    ax.axhline(0, color="black", linewidth=0.7)
    ax.set(ylabel="Mean payoff (arbitrary units)", title="Fixed policies: approximate 95% intervals")
    fig.tight_layout()
    fig.savefig(output / "payoffs.png", dpi=160)
    plt.close(fig)
    print(summary.to_string(index=False))
    print(f"Saved to {output.resolve()}")


if __name__ == "__main__":
    main()
