# First laptop experiment

From the project root, use your virtual environment's Python:

```powershell
.\.venv\Scripts\python.exe experiments/laptop/baseline.py --trials 1000 --seed 42 --a 0.8 --b 0.4
```

The script is a thin entry point to the same CLI as `python -m frontier_game`.
Keep experiment logic in the package. To change parameters beyond CLI flags:

```python
from frontier_game import Config, FixedPolicy, run_trials, summarize

config = Config(catastrophe_cost=100, horizon=30)
episodes = run_trials(config, FixedPolicy(0.8), FixedPolicy(0.4), trials=1000, seed=42)
print(summarize(episodes))
```

Start with a hypothesis and a fixed trial count. Compare all four policy pairs in
the notebook, then change one parameter. For timing, run the CLI with 1,000 and
10,000 trials and compare `elapsed_seconds` in the metadata. Repeat timings before
concluding that a speed difference is meaningful. Always report the hardware used.

## Triangular fixed-allocation grid

Run all 231 pairs with A <= B on the 0.05 grid, keeping model defaults:

```powershell
.\.venv\Scripts\python.exe experiments/laptop/triangular_grid.py --trials 1000 --seed 2026
```

For a smoke check, use `--trials 2`. `--output` accepts a new directory and refuses
an existing one. Each pair gets seed `master_seed + pair_index` (zero-based),
recorded in metadata. Episodes and uncertainty CSVs are saved after each pair;
completed files survive interruption. The default output is a fresh
`results/triangular-grid-...` directory. Metadata records defaults, versions,
completion status, and simulation and total elapsed time.

The analysis reconstructs 441 ordered pairs by swapping player estimates off
the diagonal, retaining raw diagonal estimates. It saves best responses with
all numerical ties, deviation gains, mutual best-response candidates, and the
five smallest maximum gains (including ties at the cutoff). Reconstructed
cells reuse data; they are not additional independent simulations. Findings
are exploratory within this discrete grid. Existing marginal 95% intervals
do not correct for multiple comparisons or selecting the largest sample mean,
and these results do not establish a continuous-action equilibrium.


## Manual safety-gap experiment (FG-M002)

Run from the repository root when you choose to run this experiment:

```powershell
.\.venv\Scripts\python.exe experiments/laptop/safety_gap.py --trials 1000 --seed 2026 --normal-allocation 0.50 --cautious-allocation 0.30 --gap-threshold 0.0
```

Both players use separate immutable instances of the same memoryless rule. Each
is called every surviving period using exact pre-transition information. The
shared gap exceeds the threshold only for cautious choices; equality selects
normal. This particular symmetric shared-gap rule gives equal actions even when
capabilities differ. Productivity shocks remain independent and all model defaults
are preserved. This is an illustrative policy comparison, not an optimized rule.

The default creates a fresh `results/safety-gap-...` directory. `--output` must
name a new directory. Files are `episodes.csv`, `summary.csv` with existing
uncertainty intervals, `metadata.json`, and `trajectory.csv`. The illustrative
trajectory uses `seed + 1` separately and is excluded from the trial summary.
Trace columns distinguish pre-transition state, allocations, and post-transition
outcomes; legacy unprefixed state fields are post-transition aliases.

Metadata records FG-M002/schema 1, defaults and zero initial state, policy types
and parameters, exact-observation assumptions, seeds, timestamps, status, versions,
and Git commit/dirty state (including untracked non-ignored files). A dirty commit
alone does not identify executed source; no source snapshot is created here.
`--category test --trials 2` is for a tiny verification run, not research evidence.
No full adaptive experiment was run as part of implementing this entry point.
