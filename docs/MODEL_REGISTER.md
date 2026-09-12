# Frontier Game — model and experiment register

Created 2026-09-09. Proposed repository location: docs/MODEL_REGISTER.md.
This is a retrospective audit and a lightweight convention for future work.
It does not modify existing run metadata or certify historical source provenance.

## Three identifiers

- **Model ID** describes the scientific rules and allowed information/behavior.
- **Code revision** is the Git commit implementing those rules. Record whether
  uncommitted changes were present; a commit alone cannot identify those changes.
- **Run ID** identifies a particular experiment, configuration, and random sample.

Changing seeds, trial counts, or an allocation grid creates a new run, not a new
model. Changing payoff rules, transitions, observations, or allowed policy behavior
creates a new model ID. A behavior-preserving refactor changes only code revision.
A defect correction that changes outputs needs an explicit correction note and
identification of affected runs, even if the intended scientific model is unchanged.

## Model register

| Model ID | Name | Status | Parent | Defining change |
|---|---|---|---|---|
| FG-M001 | Fixed-allocation, shared-safety baseline | Implemented; existing runs retrospectively classified | None | Two symmetric players, constant allocations, terminal rank prize |
| FG-M002 | Per-period policies with exact observations | Implemented; research runs exist; not limited to small verification | FG-M001 | Immutable player observations and per-period decisions; one shared safety-gap rule |
| FG-M003 | Graduated relative-position and safety response | Implemented; research runs exist; not limited to small verification | FG-M002 | Adds a prescribed continuous allocation rule responding to capability deficit and shared gap |
| FG-M004 | Delayed capability and shared-safety production | Implemented; verification only, no research runs authorized | FG-M003 | Lab-specific investment-to-effect delays and unfinished production |
| FG-M005 | Exact pending-work observations | Implemented; verification only | FG-M004 | Exposes realized pending schedules and configured delays through immutable observations |
| FG-M006 | Pending-aware graduated measure | Implemented; verification only | FG-M005 | Independent capability/safety lookahead windows in a prescribed policy gap |

Allocate the next unused model ID only when a further scientific change is actually implemented.
Do not preassign IDs to a roadmap that may change. For each new model add purpose,
parent, changed assumptions, retained assumptions, limitations, implementation commit,
and associated experiment IDs. Preserve the earlier description.

## FG-M001 assumptions

- Two interchangeable players; initial capabilities and shared safety are zero.
- Each receives one effort unit per period, allocating a fixed fraction a_i to
  capability and 1-a_i to safety for the whole episode. No adaptation or learning.
- Capability update: C_i <- C_i + g*a_i*M_i, with independent multipliers
  M_i=exp(-sigma^2/2 + sigma*Z_i), Z_i standard normal. Mean multiplier is one.
  Capability is cumulative; shocks are independent across players and periods.
- Safety update: S <- S + h*((1-a_A)+(1-a_B)). Safety is deterministic,
  perfectly shared, cumulative, and has no depreciation.
- After both updates, G=max(0,max(C_A,C_B)-S). Catastrophe probability for that
  period is 1-exp(-lambda*G). A catastrophe ends the episode and pays -L to both.
- Otherwise play ends at H. The final capability leader receives V; the other
  receives zero. Exact equality splits V. No absolute-capability benefit,
  intermediate reward, discounting, regulation, or enforcement.
- Policies ignore state. Exact observations and hidden-information behavior are
  not implemented or tested; do not describe these runs as tests of observability.
- Full default configuration: H=30, g=1, h=0.6, sigma=0.25, lambda=0.01,
  V=10, L=50. Units and parameter values are illustrative, not empirical estimates.

Changing configurable parameter values is an experiment within FG-M001; record
the full configuration, not just deviations from defaults.

## Existing production experiment index

Paths below are relative to the working repository's results directory.
All entries use 1,000 episodes per scenario and the FG-M001 defaults above.

| Run directory | Question / role | Scenario count |
|---|---|---:|
| baseline | Distributed example; not a new independent experiment by virtue of copying | 1 |
| run-20260907T221553661956Z | Initial individual-policy experiment; exact allocations in metadata | 1 |
| run-20260908T175500808272Z | Individual-policy experiment; exact allocations in metadata | 1 |
| run-20260908T180206465128Z | Individual-policy experiment; exact allocations in metadata | 1 |
| run-20260908T180225574595Z | Individual-policy experiment; exact allocations in metadata | 1 |
| sweep-20260908T182933631230Z | A allocation sweep against B=0.40 | 9 |
| sweep-b-20260908T185308546900Z | B allocation sweep against A=0.50 | 14 |
| triangular-grid-20260908T192435601413Z | Full 0.05 allocation grid, symmetry reduced | 231 |

Single-run metadata stores policies and seed; sweep metadata stores per-scenario
allocations and seeds. Do not pool repeated configurations blindly: seeds can overlap,
and copied example results are not additional observations.

Exclude these from scientific conclusions:
- triangular-grid-smoke-20260908: two episodes per pair, interrupted_or_failed.
- triangular-grid-smoke-20260908-retry: two episodes per pair, completed smoke check.
- Files under test-temporary directories, including a ten-episode, H=3 CLI baseline.

The no-productivity-noise 42.8% calculation discussed in conversation was an analytic
comparison, not one of these saved production runs. Production metadata records
sigma=0.25, not zero.

## What the audit established and what is missing

Present: numerical configuration, policy allocations, seeds, episode counts,
Python/package versions. Production runs retain summaries and episode data;
the audit inspected metadata, not the integrity of every episode file.
The triangular run also records completion, validation, and timing.

Missing from historical metadata: scientific model ID, source commit, working-tree
state, and a structured purpose/experiment category. Structural assumptions live in
the code and docs/model.md rather than an immutable per-run model reference.
Initial state is hard-coded, not recorded explicitly in those metadata files.
Package version 0.1.0 alone does not establish identical implementation.

Git inspection found commit 6fbdf5d, "Establish fixed-allocation simulation baseline".
This identifies a preserved baseline commit, NOT a verified generating commit for
earlier results. Assign FG-M001 retrospectively with provenance status
"inferred from metadata, project documentation, and experiment history".
Do not backfill a historical code hash as if it had been recorded at execution.

## Minimal future metadata additions

Keep existing fields and add:
- model_id and metadata_schema_version;
- experiment description and category (research, smoke, test);
- code_commit and code_dirty;
- UTC start/end timestamps, status, and run command;
- explicit initial state and policy type/parameters;
- observation model ID/settings once observations exist.

Prefer committed source for reference experiments. If code_dirty is true, preserve
a source snapshot or patch with a hash; recording "dirty" alone is not reproducible.
Preserve runtime results unchanged. Add historical classifications in this register
or a separate sidecar catalog, not by silently rewriting old metadata.

## Findings and limitations of FG-M001

The allocation grid supplies exploratory expected-payoff comparisons and candidate
mutual best responses within the sampled grid. Several asymmetric candidates depend
on sample ties at zero and ten with no observed rare events. They are not established
continuous-action equilibria or evidence of convergence by adaptive players.
Winner-take-all rewards and perfectly shared safety strongly shape these outcomes.

## Storage

Commit this register, model descriptions, scripts, and small curated finding tables.
Bulk results may remain ignored by Git, but then GitHub does not back them up.
Keep a separate backup of the full results directories, including metadata and raw
episodes. A catalog provides traceability; it does not preserve the data it references.
No database, experiment-tracking service, or new dependency is needed at this scale.


## FG-M002: per-period policies with exact observations

Purpose: permit a deterministic rule to choose capability allocation at the start
of every surviving period. Parent: FG-M001. The allowed behavior and the
policy/observation interface change; physical transitions, payoff rules, default
parameters (including productivity noise), and zero initial state do not change.

`Observation` is immutable and exact. Periods are indexed 1 through H. Each player
receives its own capability, the opponent's capability, and shared safety, all
from the same pre-transition state. Both observations are constructed before
policy evaluation. Neither contains the opponent's current action or policy,
mutable state, or future random draws. Both policies are called each period,
including period 1; validated choices are applied simultaneously before the
existing catastrophe draw. No calls occur after catastrophe.

`SafetyGapPolicy` is deterministic and memoryless: compute
G=max(0,max(own_capability,opponent_capability)-shared_safety). Choose 0.30 when
G>0, otherwise 0.50 by default. The two allocations and nonnegative threshold
are configurable. Equality with the threshold selects the normal allocation.
Two separate immutable instances with identical parameters choose the same action
because this rule uses a shared gap, even if capabilities differ. Independent
productivity shocks can still produce different capability growth. Other rules
using relative position can choose different actions with identical parameters.

Limitations: no noisy/delayed observations, learning, optimization, policy memory,
or equilibrium claim. Custom policies must obey the memoryless interface;
`run_trials` reuses instances and does not reset arbitrary user-defined state.
Fixed-policy compatibility runs retain their FG-M001 scientific interpretation.
The FG-M001 assumptions above describe the historical baseline, not a claim that
exact observations remain unimplemented in the current machinery.

Implementation revision: uncommitted working-tree changes at introduction; no
new implementation commit is claimed. Associated entry point:
`experiments/laptop/safety_gap.py`. No research experiment was executed for this
implementation; tiny temporary verification runs are category `test`.
Each future run's output directory name is its run ID.

New metadata schema version 1 records FG-M002, numerical configuration, initial
state, both policy types/parameters, observation assumptions, trial and illustrative
trajectory seeds, UTC timestamps, status, package versions, and Git provenance.
Tracked changes and untracked non-ignored files both make `code_dirty` true.
A dirty commit alone does not identify executed source. A source snapshot is
outside this implementation's scope; such runs have incomplete source provenance.
Historical metadata and historical commit attribution are unchanged.

## JSON experiment infrastructure

`experiments/laptop/run_experiment.py` adds strict JSON configuration and independent
A/B policy construction using the existing `fixed` and `safety_gap` rules. This is
experiment infrastructure support, not a new scientific model version. Two fixed
policies under the baseline rules remain FG-M001, including configurable numerical
parameter changes. Runs using either safety-gap policy without a graduated policy are FG-M002; their policy
parameters need not be identical. The runner records the supplied description,
separate resolved policies, the original JSON, and fully resolved configuration
alongside existing schema-1 provenance and an explicit episode/trajectory seed
mapping. Historical outputs and model descriptions are unchanged. The example
configuration is not evidence of an executed research run.


## FG-M003: prescribed graduated policy

Purpose: explore a deterministic, memoryless allocation rule that responds to
relative capability as well as the shared safety gap. Parent: FG-M002. The added
allowed behavior is `GraduatedPolicy`, selectable as `graduated` for either player.
No physical transition, payoff, initial state, productivity noise, observation,
policy-call timing, or existing policy changes. Earlier descriptions are retained.

Given exact pre-transition observations, define deficit=opponent-own and
G=max(0,max(own,opponent)-shared_safety). The capability allocation is
clip(base_allocation + deficit_response*deficit - safety_response*G, 0, 1).
The base must lie in [0,1]; response coefficients must be finite and nonnegative.
Being behind increases capability effort, being ahead reduces it, and a safety
gap reduces it. Identical rules may choose different actions when relative
positions differ. Remaining effort goes to shared safety.

Defaults and example parameters are base=0.60, deficit_response=0.10, and
safety_response=0.20. These are illustrative, not optimized. This is a prescribed
rule, not online optimization, learning, or an equilibrium claim. Coefficients do
not change during an episode; no policy state carries between episodes.

With zero delays, any run containing a graduated or threshold-intervention policy
is FG-M003, including mixed-policy pairs.
Without graduated policies, the previous FG-M001/FG-M002 assignments remain.
The numerical configuration and chosen policy parameters are recorded per run;
metadata schema remains 1. Implementation revision: current uncommitted changes;
no new commit or historical provenance is claimed. Associated example:
`experiments/laptop/configs/graduated.json`, run through `run_experiment.py`.
Only small verification tests were run at introduction, not a research experiment.

## Instrumentation: output schema 2

Behavioral diagnostics and optional full Monte Carlo tracing are instrumentation,
not changes to transitions, policies, payoffs, observation timing, or RNG consumption.
FG-M001/FG-M002/FG-M003 assignments remain as above. New episode outputs add mean
allocations, exact endpoint counts, maximum post-update gap, and cumulative hazard
exposure, over executed periods including a fatal period. Exposure sums
`hazard_scale * post_gap`; it is not a count or a probability.

The JSON runner records output schema 2 separately from metadata schema 1, with
diagnostic definitions and enabled/disabled full-trace status and filename.
`--save-trajectories` writes the actual Monte Carlo histories incrementally to
`trajectories.csv.gz`; the separately seeded `trajectory.csv` remains illustrative
and excluded from the summary. Historical output schema/metadata is not rewritten.
Older tables without diagnostics remain valid for their existing analyses; recovering
missing states requires matching-source/config/seed regeneration into a new run.
Only tiny verification experiments were executed when adding this instrumentation.


## FG-M004: delayed production

Purpose: test how investment-to-effect timing changes reactive safety and competition.
Parent: FG-M003; all existing policy families remain available. Any of the four
nonzero production delays selects FG-M004 for both individual metadata and sweep
manifest entries. All-zero configurations retain the previous policy-based IDs.

Changed assumption: capability and safety can take independent nonnegative integer
numbers of periods by lab to become effective. Investment in t arrives during
update t+d, after both decisions and before risk. Realized capability productivity
is drawn at investment. Safety remains deterministic and shared upon arrival.
Pending work is hidden from policies, contributes neither risk nor protection,
and has no terminal prize value. Beyond-horizon work is retained as unfinished;
catastrophe terminates immediately without processing later arrivals.

Retained: zero initial stocks, simultaneous decisions, existing policy rules,
noise distribution and draw order, gap/hazard function, and terminal rank payoffs.
See [model.md](model.md) for precise timing and unimplemented future mechanisms.

Implementation revision: uncommitted working-tree changes; no new commit claimed.
Associated research run IDs: none. Only temporary test cases have been run;
research delay experiments require separate authorization. The unfinished local
implementation incorrectly used t+d+1 and released arrivals before observations;
this correction replaces its two production loops with one. No historical saved
research output or metadata has been changed or attributed to the corrected code.

Output schema 3 adds four lab-attributed pending amounts to episodes and traces,
including zeros with zero delays. Measurements follow investment and arrivals in
each executed period; episode values are terminal unfinished amounts. Existing
fields are preserved exactly for zero delays, including RNG state, as checked
against Git revision f9774c1796c37a714379270828a8f604da567609 in test infrastructure.
Metadata schema stays 1; full Monte Carlo trajectories remain optional and disabled
by default. Historical schema-2 documentation above describes earlier outputs.


## FG-M005: exact pending-work observations

Purpose: expose already-scheduled capability and safety production to policies,
through an observation boundary separate from transitions. Parent: FG-M004.
Changed assumption: the allowed information now includes both labs' exact realized
pending schedules and configured capability/safety delays, oriented as own/opponent.
This warrants a new scientific ID even though every existing policy ignores the
new fields and retains identical results and random-number consumption.

Observations are constructed simultaneously before decisions, investment, and
arrivals. Work due this period is pending, not effective; beyond-horizon work is
included. Frozen `PendingArrival(amount, arrival_period)` records form sorted tuple
snapshots. Manual omitted fields mean unavailable (`None`); known-empty schedules
are `()`. The simulator supplies exact schedules and known delays, including zero.
No separate opponent effective safety stock exists. See [model.md](model.md) for
all field names, exclusions, and the boundary for future imperfect information.

Retained: all FG-M004 physical transitions, investment-time productivity shocks,
effective-stock risk and terminal payoff rules, original policy implementations,
trace fields, and pending-total diagnostics. Pending-aware policies, uncertainty,
cheating/concealment, regulatory reporting, and observation noise remain unimplemented.
No research experiment is authorized or executed for this extension.

Current JSON individual runs and sweep entries, and the safety-gap runner, record
`model_id=FG-M005` with `observation.model_id=exact-pending-pre-decision-v1`.
`behavior_model_id` preserves the earlier interpretation for existing rules:
FG-M004 for nonzero delays; otherwise FG-M003 for graduated/threshold, FG-M002 for
safety-gap, or FG-M001 for fixed policies. This comparison label is not a claim
that the expanded information existed historically. Earlier sections describe
historical classifications; historical outputs and metadata are not rewritten.
The richer observation interface is present even in zero-delay runs.

Metadata schema remains 1 (additive description fields); output schema remains 3.
Policy schedules are not automatically serialized into episode or trajectory files.
Post-update pending totals remain diagnostics, distinct from pre-decision information.

Implementation revision: current uncommitted extension, based on delay-engine Git
673f6d21dec32ba2d85cfcc00049ceaa537072c9. No new commit claimed.
Associated research run IDs: none; only temporary verification outputs. Test-only
frozen source from that revision provides exact comparisons of complete episode
results, traces, and final RNG states with zero and nonzero delays for all four
existing policy families, including trace-on/off and catastrophe cases.


## FG-M006: configurable pending-aware graduated policy

Purpose: compare prescribed responses to effective stocks plus selected pending
work. Parent: FG-M005. Adds PendingAwareGraduatedPolicy (pending_aware_graduated)
with capability_lookahead and safety_lookahead, independently None/null or integer
k >= 0. None ignores the category; 0 selects due-now records. Include arrivals
from current period through period+k inclusive, even beyond the horizon.

The anticipated gap is max(0,max(C_i+P_i,C_j+P_j)-(S+P_S)); P_S includes both
labs' selected safety contributions. Allocation clips base + deficit_response *
(C_j-C_i) - safety_response * anticipated_gap. The deficit stays effective-stock
based. Both None explicitly reuses GraduatedPolicy. Enabled windows require both
schedules; unavailable information is an error, never assumed zero.

Changed allowed behavior warrants FG-M006 for any run containing the new class,
including mixed pairs and ignore mode. behavior_model_id is FG-M006 when at least
one window is enabled, including zero, irrespective of whether current queues are
empty. In all-ignore mode it retains graduated FG-M003 behavior with zero delays,
or FG-M004 behavior with delays. Earlier families retain their FG-M005 model ID.
Historical model classifications, outputs, and metadata are preserved.

Retained: FG-M005 exact immutable observations, engine transitions and arrival timing,
investment-time productivity shocks, effective-stock physical risk, terminal ranking,
and all legacy policies. Metadata schema 1/output schema 3 stay unchanged; resolved
policy parameters record nulls and integers. No full schedule output is added.

Limitations: the measure can offset earlier exposure with later safety, includes
beyond-horizon work within its window, and does not optimize actions or reconstruct
the path of future gaps. No learning, memory, rollouts, dynamic delays, or extra
random draws. See model.md for formula, validation, and information boundaries.

Implementation revision: uncommitted changes based on b61541837613775e3ed3d9b564b78e406f8b4c15;
no new commit claimed. Associated FG-M006 research run IDs: none. Only focused
verification and tiny temporary runner checks are authorized here. Proposed future
comparison: saved graduated (1,2) baseline results/sweep-20260911T204618486225Z,
seeds 2026-2030, A safety_response=.05 and B=10, versus independently chosen windows.
The saved baseline is prior evidence, not a new run or a pending-aware experiment.
