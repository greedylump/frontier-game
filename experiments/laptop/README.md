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

Metadata records FG-M005 with FG-M002 behavior/schema 1, defaults and zero initial state, policy types
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

## Repeatable command-line overrides

Keep a baseline JSON file and repeat `--set PATH=VALUE` to change existing scalar
fields for one run. Values use JSON syntax: numeric values stay numeric; strings
must contain JSON double quotes. Overrides apply to a separate copy before normal
configuration validation. Paths must exist in the input file, even when the model
could otherwise supply a default. Unknown or duplicate paths, object/array targets
or values, malformed JSON, and non-finite numbers are rejected before execution.

Change safety productivity and disable only A's deficit response:

```powershell
.\.venv\Scripts\python.exe experiments/laptop/run_experiment.py --config experiments/laptop/configs/graduated.json --set model.safety_rate=0.75 --set policies.a.parameters.deficit_response=0
```

Change both players' safety responses independently:

```powershell
.\.venv\Scripts\python.exe experiments/laptop/run_experiment.py --config experiments/laptop/configs/graduated.json --set policies.a.parameters.safety_response=0.30 --set policies.b.parameters.safety_response=0.40
```

For a tiny check, append `--set trials=2 --set model.horizon=3 --set seed=17`.
The commands above otherwise retain the baseline trial count. `--output` still
requires a fresh directory. The source JSON and saved `input_config.json` remain
unchanged. Metadata retains the original `input_config`, ordered `overrides`
records (path, parsed value, and original argument), and final `resolved_config`.
Without `--set`, overrides are an empty list and numerical behavior is unchanged.
This is experiment infrastructure; model-ID rules and scientific behavior are unchanged.

## Sequential parameter sweeps

A one-parameter sweep of A's graduated safety response (B and other settings
remain as specified in the baseline):

```powershell
.\.venv\Scripts\python.exe experiments/laptop/run_experiment.py --config experiments/laptop/configs/graduated.json --sweep policies.a.parameters.safety_response=0.05,0.15,0.25
```

Repeat `--sweep` for a Cartesian grid. Arguments and values keep their supplied
order; the last axis varies fastest. CLI sweep values must be finite JSON numbers.
Common `--set` overrides apply to every variation, but a path cannot appear in
both fixed overrides and a sweep:

```powershell
.\.venv\Scripts\python.exe experiments/laptop/run_experiment.py --config experiments/laptop/configs/graduated.json --set model.safety_rate=0.75 --sweep policies.a.parameters.safety_response=0.05,0.15,0.25 --sweep policies.b.parameters.safety_response=0.10,0.20
```

Alternatively, create a CSV whose headers are existing scalar configuration paths,
with one experiment per row. Cells contain JSON scalars; JSON strings must also be
quoted/escaped according to CSV rules. Blank cells, duplicate headers, malformed
rows, and invalid settings are rejected. Example `variations.csv`:

```csv
policies.a.parameters.safety_response,policies.b.parameters.safety_response
0.05,0.10
0.15,0.20
```

```powershell
.\.venv\Scripts\python.exe experiments/laptop/run_experiment.py --config experiments/laptop/configs/graduated.json --sweep-csv variations.csv
```

`--sweep-csv` and `--sweep` are mutually exclusive. CSV row order is retained;
rows are explicit variations, not a Cartesian product. Paths must exist in the
original JSON, including any field that otherwise has a default.

Inspect resolved variations and total Monte Carlo histories without simulation or
creating output files:

```powershell
.\.venv\Scripts\python.exe experiments/laptop/run_experiment.py --config experiments/laptop/configs/graduated.json --sweep policies.a.parameters.safety_response=0.05,0.15,0.25 --dry-run
```

`--dry-run` also works for a single run. All configurations are validated before
any simulation starts. Runs execute sequentially. Seeds are preserved by default,
so corresponding trial IDs use the same spawned random streams for paired analysis.
Changing a seed explicitly changes that pairing; different trajectories can consume
those streams differently. Illustrative trajectories remain excluded from summary
history counts. No inference of statistical significance follows from a sweep alone.

A fresh `results/sweep-...` directory (or new `--output` path) holds `0001`, `0002`,
etc., each with the existing single-run files. `manifest.json` records the original
input, exact sweep specification, ordered resolved variations, seeds, model IDs,
source provenance, statuses, and relative output paths. CSV bytes are copied to
`sweep_input.csv` when used. Root `summary.csv` combines completed runs with
`experiment_id`, varied values in `parameter.<path>` columns, and all existing
uncertainty columns. It is updated after each experiment. Execution stops on a
failure; completed outputs remain, and the manifest identifies the failed experiment
and leaves later experiments pending. Existing output directories are refused.

By default, every experiment prints its index/count and varied values followed by
its summary table. Add `--quiet` to suppress tables and routine progress, retaining
errors and a final completed/total count and output directory. Single runs also
support `--quiet`; their default output remains unchanged. Quiet mode uses the same
calculations and saved data/schema; recorded invocation, timestamps, and output paths
naturally reflect the actual run. Dry-run output remains visible even with `--quiet`.

This is experiment infrastructure and does not increment the mathematical model ID.
Only tiny verification experiments were executed during implementation.

## Behavioral diagnostics and full Monte Carlo trajectories

New `episodes.csv` files preserve all earlier columns and add diagnostics by
default, even without tracing:

- `mean_allocation_a`, `mean_allocation_b`: arithmetic mean capability allocation.
- `allocation_zero_periods_a/b`, `allocation_one_periods_a/b`: counts of exact
  endpoint choices (0 or 1, not an approximate tolerance).
- `max_post_gap`: maximum post-update shared safety gap.
- `cumulative_hazard_exposure`: sum of `hazard_scale * post_gap`.

All diagnostics use executed periods only, including the terminal catastrophe
period. Means divide by executed steps, not the configured horizon. Cumulative
hazard exposure is neither a catastrophe count nor a probability; it can exceed 1.
The existing uncertainty summary retains its payoff, catastrophe, and duration
metrics, and can still summarize older episode CSVs without these extra columns.

The default remains no full-history file. Add `--save-trajectories` when intermediate
states are needed, including for our current research sweeps. A small manual check:

```powershell
.\.venv\Scripts\python.exe experiments/laptop/run_experiment.py --config experiments/laptop/configs/graduated.json --set trials=2 --set model.horizon=3 --save-trajectories
```

The next research sweep can be run manually with:

```powershell
.\.venv\Scripts\python.exe experiments/laptop/run_experiment.py --config experiments/laptop/configs/graduated.json --sweep policies.a.parameters.safety_response=0.05,0.15,0.25 --save-trajectories
```

Each experiment directory then contains `trajectories.csv.gz`, with every executed
period of every Monte Carlo trial. It adds `experiment_seed` and zero-based `trial`
to the existing trace fields: 1-based `step`, `horizon`, `pre_*` observations/state,
`allocation_a/b`, and `post_*` state, gap, hazard probability (`post_hazard`), and
catastrophe. Legacy unprefixed post-state aliases are retained. A observes its own
`pre_capability_a`; B observes its own `pre_capability_b`. Both see the same shared
safety and pre-transition state. Trials stop at catastrophe; there are no padded rows.

```python
import pandas as pd
trace = pd.read_csv("results/YOUR-SWEEP/0001/trajectories.csv.gz")
# For large files, use bounded chunks:
for chunk in pd.read_csv("results/YOUR-SWEEP/0001/trajectories.csv.gz", chunksize=100_000):
    pass  # Analyze or aggregate each chunk.
```

The existing `trajectory.csv` is still one separately seeded illustration; it is
NOT one of the histories in the Monte Carlo summary. `trajectories.csv.gz` contains
those actual histories with the unchanged experiment-seed/trial mapping for pairing.
Only one episode's trace is buffered at a time, then written before the next trial.
`--quiet` changes terminal output only, and `--dry-run` writes no trajectories.

Runner metadata keeps metadata schema 1 and records additive output schema 3,
diagnostic definitions, whether full tracing is enabled, filename, file status,
completed traced trials, and row counts. Exceptions close gzip output and mark an
unfinished trace incomplete; successfully written earlier histories are retained.
Such partial files must not be treated as completed datasets. Abrupt process or
machine termination may leave stale status or truncated output, unlike a handled
exception. Overwrite protection remains in force.

Older histories remain usable for their saved outcomes. Missing intermediate
states cannot be recovered from aggregate outcomes: regenerate with the matching
source, configuration, policies, and seeds in a fresh directory if those traces
are needed. No historical results were regenerated for this implementation.
This is instrumentation, not a new mathematical model; model IDs are unchanged.


Production delays are configured through `model.capability_delay_a`,
`model.safety_delay_a`, `model.capability_delay_b`, and `model.safety_delay_b`.
They default to zero and can be set or swept even when omitted from input JSON.
Current runs use FG-M005 for exact pending-work observations. `behavior_model_id`
records FG-M004 with nonzero delays, or the earlier policy-based ID with zero delays.
Output schema 3 adds pending capability/safety amounts by lab to episodes and
traces. See ../../docs/model.md for t+d update timing and terminal meaning.

Example for review only (dry-run resolves settings without simulation or output):

```powershell
.\.venv\Scripts\python.exe experiments/laptop/run_experiment.py --config experiments/laptop/configs/graduated.json --set model.capability_delay_a=1 --set model.capability_delay_b=1 --set model.safety_delay_a=2 --set model.safety_delay_b=2 --dry-run
```


The observation builder exposes immutable own/opponent pending schedules and
configured delays before decisions, including arrivals due now and beyond the
horizon. Observation metadata describes this as `exact-pending-pre-decision-v1`.
Existing policies ignore the added fields. Schedules are not serialized into every
output row; pending-total columns remain post-update diagnostics. See
[the model description](../../docs/model.md) for the full API and exclusions.


### Pending-aware graduated policy

`pending_aware_graduated` adds independent `capability_lookahead` and
`safety_lookahead` to graduated coefficients. JSON `null` ignores that category;
0 counts due-now work; k counts arrivals from the current period through period+k,
including beyond-horizon records within the window. Enabled categories require
known own/opponent schedules. The effective-capability deficit term stays unchanged.
This anticipated gap is a policy measure, not actual catastrophe risk; it can credit
later safety against earlier exposure. See [model.md](../../docs/model.md).

The example has symmetric production delays (1,2), A safety response .05 and B=10,
and both lookaheads explicitly null for each player. Runs use FG-M006; behavior ID
is FG-M006 with any enabled window, otherwise FG-M004 for this delayed example.
Overrides and sweeps accept null and zero for either lookahead. Default trace/output
sizes are unchanged. Example for review only (resolves without running simulation):

```powershell
.\.venv\Scripts\python.exe experiments/laptop/run_experiment.py --config experiments/laptop/configs/pending_aware_graduated.json --set policies.b.parameters.capability_lookahead=0 --set policies.b.parameters.safety_lookahead=1 --dry-run
```


Full Monte Carlo traces now use output schema 4: --save-trajectories adds exactly
`decision_gap_a` and `decision_gap_b` to `trajectories.csv.gz`. They describe the
pre-decision effective or pending-aware gap used by each policy, not physical risk
or a counterfactual outcome. Fixed/unsupported policies export blank values.
`episodes.csv`, `summary.csv`, and illustrative `trajectory.csv` are unchanged.
Full tracing remains optional/off. See [model.md](../../docs/model.md) for semantics
and the pure optional diagnostic interface. Model IDs and metadata schema are unchanged.
