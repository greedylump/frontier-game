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

## JSON experiments with independent players

```powershell
.\.venv\Scripts\python.exe experiments/laptop/run_experiment.py --config experiments/laptop/configs/asymmetric_safety_gap.json
```

The example uses 1,000 histories; run it manually when ready. Optional `--output`
must name a new directory; otherwise a fresh `results/experiment-...` is created.
The existing `safety_gap.py` command keeps its behavior.

Required JSON fields are `name`, `description`, `model`, `trials`, `seed`, and
`policies`. Optional `category` is `research` (default), `smoke`, or `test`.
`model` accepts Config's numerical parameters; omitted parameters use current
model defaults, which are always recorded in full. The checked-in example
explicitly lists every parameter, including horizon 30 and noise 0.25.
`trials` must be an integer >= 2 and `seed` a nonnegative integer.

`policies` requires separate lowercase `a` and `b` objects. Each requires `type`
and `parameters`. Supported types are `fixed` (requires `allocation`), `graduated` (see below), and
`safety_gap` (defaults: `normal_allocation=0.50`, `cautious_allocation=0.30`,
`gap_threshold=0.0`). Unknown fields, duplicate keys, unsupported types, and
invalid values are rejected before output creation or simulation.

Edit `policies.a.parameters` for A and `policies.b.parameters` for B independently.
For example, change A's `normal_allocation` from 0.60 to 0.65 while leaving B's
at 0.50. Normal and cautious are alternative **capability** allocations; the
remaining effort `1-allocation` goes to shared safety. In the example, both
players choose 0.30 when the pre-transition shared gap is above zero. At zero,
A chooses 0.60 and B chooses 0.50. These labels impose no extra ordering constraint.

For fixed A against safety-gap B, replace only the `a` object with:

```json
{"type": "fixed", "parameters": {"allocation": 0.50}}
```

Outputs are `episodes.csv`, `summary.csv` with existing uncertainty estimates,
`trajectory.csv` with pre/post state and both chosen allocations, an unchanged
copy `input_config.json`, and `metadata.json`. Metadata includes input and fully
resolved configuration, each player's type and parameters, model ID, observation
assumptions, timestamps/status, versions, and Git commit/dirty-tree provenance.
Episode seeds use `SeedSequence(seed).spawn(trials)`; metadata maps episode indices
to spawn keys. The illustrative trajectory uses `seed+1` and is excluded from the
summary. A dirty commit alone does not identify executed source; no source snapshot
is created. Two fixed policies retain FG-M001; using either safety-gap policy without a graduated policy is
FG-M002; any graduated policy makes the run FG-M003. This runner is experiment infrastructure, not a new scientific model.


## Graduated rule (FG-M003)

```powershell
.\.venv\Scripts\python.exe experiments/laptop/run_experiment.py --config experiments/laptop/configs/graduated.json
```

The example configures both players independently as `graduated`, with
`base_allocation=0.60`, `deficit_response=0.10`, and `safety_response=0.20`.
These are also the policy defaults if parameters are omitted. Edit either
`policies.a.parameters` or `policies.b.parameters` independently; mixing with
`fixed` or `safety_gap` is supported.

Allocation is clipped to [0,1] after adding the deficit response
`deficit_response*(opponent_capability-own_capability)` to the base and
subtracting `safety_response*gap`. The gap is
`max(0,max(own_capability,opponent_capability)-shared_safety)`.
Thus being behind raises capability effort, being ahead lowers it, and a gap
lowers it; remaining effort goes to safety. Identical parameters can produce
different actions for players in different relative positions.

This is a prescribed, immutable, memoryless rule, not online optimization.
The coefficients are illustrative, not optimized. The example requests 1,000
histories for a manual run; it was not executed during implementation.
