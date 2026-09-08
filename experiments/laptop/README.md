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
