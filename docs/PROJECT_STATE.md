# Frontier Game: project state and handoff

> **Current resumption update (2026-09-14):** Read
> [RESEARCH_HANDOFF_2026-09-14.md](RESEARCH_HANDOFF_2026-09-14.md) first.
> It records completed delay, pending-aware, weighted-policy, and matched-trajectory
> experiments, unresolved scientific decisions, and machine-transfer requirements.
> Below, statements that those experiments are pending or implementations remain
> uncommitted are historical task snapshots, not current status. FG-M007 research
> completed at commit ee12562. The dated handoff explicitly identifies the conflicts;
> it does not authorize additional research runs.

Prepared from the research conversation and saved results through run
`sweep-20260911T180613122294Z`, plus the delay and pending-work observation implementations.
Read this first when resuming, then consult `MODEL_REGISTER.md`, source, and run
metadata. Update this file after meaningful decisions or completed experiment batches.

## Current plan and decision discipline

- Planned next experiment is recorded here for discussion and review only.
- Delay implementation, integration, documentation, and verification are authorized.
- Research delay runs are not authorized; the proposed experiment remains discussion only.
- This file is the repository-forward source of truth for pending research decisions,
  and it should be updated after meaningful decisions or completed experiment batches.
- The model register is aligned with the evidence in the
  repository runs: FG-M002 and FG-M003 are no longer described as "small
  verification only" when the run history now includes research sweeps and broader
  experiment batches.

## Goal and working style

Research question: under what modeled conditions and amount of outside pressure
(regulation, agreements, enforcement) does safer cooperation become individually
worthwhile and stable against unilateral deviations between competing AI labs?
Eventually consider leader versus challenger, then more competitors if useful.
Define cooperation and the allowed deviations explicitly before claiming stability.

This is also a learning project: Python, Monte Carlo, game theory, and compute
scaling from laptop CPU to local GPU to cloud. Establish an understandable
unregulated adaptive baseline before introducing regulation. Do not optimize this
toy model indefinitely or confuse simulator findings with empirical predictions.

The user prefers scientific discussion before implementation, small extensible
changes, and explicit manual commands for research runs. Do not launch research
sweeps merely because they appear in this roadmap. Tiny verification runs are fine
when implementing requested changes. Avoid unnecessary frameworks or GPU/RL stacks.
The user prefers VS Code to terminal-heavy workflows.

## Repository and context

- Repository: `C:\Dev\Repos\frontier-game`.
- Package: `src/frontier_game`; experiments: `experiments/laptop`.
- Main configurable runner: `experiments/laptop/run_experiment.py`.
- Default adaptive config: `experiments/laptop/configs/graduated.json`.
- Scientific model history: `docs/MODEL_REGISTER.md`.
- The discussion session could read the repo but wrote analysis artifacts into
  `C:\Users\ab294\Documents\Codex\2026-09-07\referenced-chatgpt-conversation-this-is-an\outputs`.
  Those artifacts are NOT automatically part of the repository. Raw runs below
  are in the repo's local `results` directory. Ignored results are not necessarily
  backed up to GitHub.

## Research reference: FG-M003 (zero delays)

Two symmetric players start with C_A=C_B=S=0. Each period each allocates a fraction
a_i in [0,1] to capability, and 1-a_i to safety. Decisions are simultaneous from
exact pre-update observations. Policies cannot observe the opponent's current
action, future noise, or policy internals.

    C_i' = C_i + g*a_i*M_i
    M_i = exp(-sigma^2/2 + sigma*Z_i), Z_i ~ Normal(0,1), E[M_i]=1
    S' = S + h*(2-a_A-a_B)
    G' = max(0, max(C_A',C_B')-S')
    catastrophe probability = 1-exp(-lambda*G')

Independent productivity shocks across players and periods. Safety is immediate,
deterministic, perfectly shared, permanent, and linear in effort. Capability is
permanent too. Catastrophe is checked AFTER updates and terminates the history.

Defaults: H=30, g=1, h=0.6, sigma=0.25, lambda=0.01, prize V=10,
catastrophe loss L=50 per player. If no catastrophe, terminal leader gets 10 and
loser 0; exact tie splits prize. No intermediate reward, discounting, exit option,
private safety, regulation, or absolute-capability payoff. Parameters are
illustrative, not calibrated. Horizon is a prize deadline, not just a runtime cap.

Graduated policy:

    a_i = clip(base_allocation + deficit_response*(C_j-C_i)
               - safety_response*G, 0, 1)

Here G is the pre-update shared gap. Each player has its own three fixed
coefficients. Default coefficients are 0.6, 0.1, 0.2. The deficit term both boosts
the laggard AND slows the leader. Coefficients do not change within a history.
The policy is memoryless and does not optimize or plan. Its stock inputs reflect
past events, but it cannot distinguish histories ending in the same state.

Other implemented policies include FixedPolicy and SafetyGapPolicy (normal versus
cautious allocation based on a gap threshold). The latter can use cautious=0 but
does not include the graduated policy's deficit term. Verify exact APIs in source.

Useful identities:
- Total expected payoff = 10 - 110*p_catastrophe.
- Under symmetry, expected payoff per player = 5 - 55*p_catastrophe.
  Zero payoff occurs at p=1/11, NOT at a universal safety_rate value.
- If A leads and B allocates zero to capability, signed gap D=C_A-S changes by
  g*a_A*M_A - h*(2-a_A). Expected signed gap shrinks when a_A < 2h/(g+h)=0.75.
  This is not a guarantee of positive-gap closure under noise.
- B chooses zero when k_G*G >= 0.6 + 0.1*(C_A-C_B).
  k_G is a coefficient, not an allocation; it may exceed 1.

## Infrastructure and statistical conventions

- Single-run overrides: `--set path=value`.
- Sweeps: repeatable `--sweep "path=v1,v2,..."`; multiple paths form a Cartesian
  product. Also CSV input, dry-run, quiet mode. Inspect runner help for details.
- Quote comma-separated arguments in PowerShell, especially through Run-Game.
- Full history tracing: `--save-trajectories`, producing `trajectories.csv.gz`.
- Each experiment saves resolved config/metadata, episodes.csv, summary.csv,
  and a separate illustrative trajectory.csv. The illustrative trajectory is NOT
  included in Monte Carlo summary statistics; its seed is separately recorded.
- Recent instrumentation saves mean allocations, counts of zero/one allocations,
  maximum post-update gap, and cumulative hazard exposure per history. Exposure
  is sum(lambda*post_gap), not a probability. Earlier runs lack these diagnostics.
- Trace instrumentation was requested to preserve outcomes and RNG consumption;
  consult implementation/test results before modifying it.
- SeedSequence(seed).spawn(trials) supplies per-history RNGs. Pair comparisons by
  (seed, trial ID), never trial ID alone when combining seed batches.
- Means use Student-t approximate intervals; catastrophe summaries use Wilson.
  Paired analyses use per-history differences and their sample SE. Individual
  intervals are not adjusted for multiple comparisons or sequential selection.
- Same seed and trial count repeats evidence, not an independent sample. We used
  seeds 2026-2030, 1000 trials each, yielding 5000 histories per setting.
- Commit tested source before research runs. Metadata marks dirty source; a clean
  commit identifies repository code, not necessarily the entire execution environment.

PowerShell convenience function (lost when the terminal session closes):

```powershell
function Run-Game {
    & .\.venv\Scripts\python.exe experiments/laptop/run_experiment.py --config experiments/laptop/configs/graduated.json @args
}
```

## Findings and experiment trail

Earlier phases: fixed-allocation grid, then threshold and graduated adaptive
policies. Removing both players' safety response greatly increased catastrophe
risk. Removing deficit response had little effect with safety response present,
but worsened average payoff when safety response was absent. Safety productivity
sweeps h=0.3,0.45,0.6,0.75,0.9 reduced risk strongly with other settings fixed.
See external outputs/steps-1-2 and paired_differences.csv for those analyses.

We next searched one player's safety coefficient while holding the other fixed.
All results below keep a0=0.6 and k_D=0.1 for both players and default environment.

### A sweep against B safety_response=0.20

| A k_G | A pooled payoff | B pooled payoff | Catastrophe |
|---:|---:|---:|---:|
| 0 | 0.676 | -6.516 | 14.40% |
| 0.05 | 1.500 | -4.172 | 11.52% |
| 0.10 | 1.188 | -2.342 | 10.14% |
| 0.15 | 1.044 | -0.570 | 8.66% |

A=0.05 was best sampled in each of five batches. Pooled paired advantage over
A=0,0.10,0.15 was respectively +0.824,+0.312,+0.456; each individual 95% CI excluded
zero. This did not locate the continuous optimum.

Sources: individual experiment directories `experiment-20260910T205333836580Z`
(A=0) and `experiment-20260910T205411396062Z` (A=0.1), plus sweeps
`sweep-20260910T213758806794Z`, `sweep-20260910T215611553259Z`, and
`sweep-20260910T220034015004Z`. Filter resolved configs/seeds; not every child is
part of this comparison. External analysis: outputs/five-seed-comparison/sources.csv.

### B sweep against A safety_response=0.05

| B k_G | A payoff | B payoff | Catastrophe |
|---:|---:|---:|---:|
| 0 | -15.172 | -9.830 | 31.82% |
| 0.05 | -7.872 | -7.780 | 23.32% |
| 0.10 | -3.044 | -6.294 | 17.58% |
| 0.15 | -0.284 | -5.116 | 14.00% |
| 0.20 | 1.500 | -4.172 | 11.52% |
| 0.25 | 2.536 | -3.514 | 9.98% |
| 0.30 | 3.426 | -2.908 | 8.62% |
| 0.40 | 4.470 | -2.148 | 6.98% |
| 0.50 | 5.136 | -1.714 | 5.98% |
| 0.70 | 6.200 | -0.908 | 4.28% |
| 1 | 7.008 | -0.264 | 2.96% |
| 1.5 | 7.546 | 0.166 | 2.08% |
| 2 | 7.738 | 0.348 | 1.74% |
| 3 | 7.954 | 0.550 | 1.36% |
| 4 | 8.110 | 0.658 | 1.12% |
| 5 | 8.068 | 0.722 | 1.10% |
| 10 | 8.212 | 0.886 | 0.82% |

B benefits from stronger safety even though A captures most payoff. B=10 is
best sampled, not a demonstrated optimum. Paired B gains: 3->4 +0.108
CI[-0.008,0.224]; 4->5 +0.064 CI[-0.059,0.187]; 5->10 +0.164
CI[0.030,0.298]; 3->10 +0.336 CI[0.184,0.488].

Diagnostics: from B=3 to 10, mean B capability allocation changes only
0.5312->0.5296, while zero-capability periods rise 7.23%->15.32% of executed
periods. Mean per-history maximum gap falls 0.363->0.322. This suggests timing
matters, but does NOT isolate the causal contribution of all-safety bursts.

Sweep directories (under results):
- `sweep-20260910T220808781259Z`: B=0,0.05,0.10,0.15.
- `sweep-20260910T221425929076Z`: B=0.25,0.30,0.40.
- `sweep-20260910T221959372654Z`: B=0.50,0.70,1.
- `sweep-20260911T023414945806Z`: B=1.5,2,3; new diagnostics/full traces.
- `sweep-20260911T030850898132Z`: B=4,5,10.
- B=0.20 reused from the previous A sweep.

External outputs: b-response-five-seeds, b-response-extended,
b-response-through-1, b-response-above-1, b-response-through-10.

### A response against B safety_response=10

| A k_G | A payoff | B payoff | Catastrophe |
|---:|---:|---:|---:|
| 0 | 8.152 | 0.792 | 0.96% |
| 0.025 | 8.170 | 0.774 | 0.96% |
| 0.05 | 8.212 | 0.886 | 0.82% |
| 0.10 | 8.068 | 0.744 | 1.08% |
| 0.20 | 7.902 | 0.844 | 1.14% |

Paired A changes versus 0.05:
- 0: -0.060, CI[-0.196,0.076].
- 0.025: -0.042, CI[-0.160,0.076].
- 0.10: -0.144, CI[-0.282,-0.006] (weak given multiple comparisons).
- 0.20: -0.310, CI[-0.471,-0.149].

Source: `sweep-20260911T031630014001Z`; reuse A=0.05,B=10 from prior sweep.
External analysis: outputs/a-response-to-b10.
No demonstrated equilibrium: search covers selected coefficients only, B optimum
not bracketed, other policy families incompletely explored. Symmetry permits swapping roles;
the search selected an asymmetric configuration, not spontaneous role emergence.

## Recent threshold-intervention update

The proposed threshold intervention rule was implemented in the repository as a
small pluggable policy object, exported from the package, and recognized by the
JSON runner as a new policy type: `threshold_intervention`. The implementation
retains the graduated deficit term in the normal branch while enforcing
all-safety intervention above a threshold.

Source and runner changes:

- `src/frontier_game/model.py`: added `ThresholdInterventionPolicy` with the
  thresholded all-safety branch and the retained deficit-term fallback.
- `src/frontier_game/__init__.py`: exported `ThresholdInterventionPolicy`.
- `experiments/laptop/run_experiment.py`: extended `POLICY_TYPES` and the
  `model_id_for()` mapping so the new policy type is routeable through the JSON/
  sweep runner as FG-M003-style graduated-threshold experiment infrastructure.
- `experiments/laptop/configs/threshold_intervention.json`: example config for
  a threshold sweep with A as graduated and B as threshold_intervention.

The canonical retained sweep evidence is `results/sweep-20260911T050226158766Z`.
The earlier `results/sweep-20260911T050147286477Z` was an uncommitted duplicate
pre-commit rerun of the same four-configuration threshold-intervention sweep.
The duplicate child folders `0001` through `0004` were byte-identical across
corresponding episodes, input configs, summaries, and trajectories; only
per-run metadata provenance fields such as timestamps differed. That duplicate
run was removed after verification, so no duplicate independent evidence remains
in the repository. The retained canonical run is therefore the sole seed-2026 evidence
source for this sweep; subsequent new-seed comparisons are recorded below.

The canonical retained run command was:

    .\.venv\Scripts\python.exe experiments\laptop\run_experiment.py
      --config experiments\laptop\configs\threshold_intervention.json
      --sweep policies.b.parameters.threshold=0.05,0.10,0.20,0.40

It produced the following summary evidence:

| Threshold | Payoff A | Payoff B | Catastrophe |
|---:|---:|---:|---:|
| 0.05 | 7.72 | 0.63 | 1.5% |
| 0.10 | 7.58 | 0.66 | 1.6% |
| 0.20 | 6.51 | -0.25 | 3.4% |
| 0.40 | 3.97 | -2.00 | 7.3% |

These numbers show a sharp deterioration in B payoff and an increase in
catastrophe frequency as the threshold grows. The first low-threshold sweep
does not establish a superior intervention timing policy; it only records a
policy object and an experiment grid that is now implemented for comparison.

The project should continue by adding a second approximately effort-matched
comparison before claiming any timing advantage from the intervention policy.
The new threshold policy is therefore evidence-bearing infrastructure, not a
proven superior burst mechanism yet.

## Policy ideas backlog and longer-term roadmap

1. Threshold intervention: memoryless all-safety mode above a gap threshold.
2. Hysteresis: enter above a high threshold; exit below a lower one. Requires
   per-player policy state and explicit reset between histories.
3. Trend-aware: respond to gap growth, requiring observation history.
4. Short-horizon planning: simulate candidate actions internally each period.
   Requires separate planning RNG, restricted information, and explicit opponent
   assumptions; modest versions can be laptop-feasible.
5. Policy search/learning: distinguish offline coefficient optimization from
   online action selection. Use unseen seeds and alternative model assumptions
   for evaluation. Do not assume an optimizer's simulator success is realism.
6. Challenge instant shared safety: delays, depreciation, limited productivity,
   or imperfect sharing may weaken reactive bursts. Delays are now implemented; the other mechanisms remain proposals.
7. Challenge terminal winner-take-all payoff: second-place value and/or absolute
   capability returns. Preserve original model as a selectable baseline.
8. Initial leader/challenger asymmetry and noisy/delayed observations.
9. Regulation/agreement/enforcement dial with zero reproducing the unregulated
   baseline. Evaluate unilateral deviation gains as well as catastrophe rates.
10. More agents, GPU/cloud only when the scientific question warrants the cost.

## Maintenance and resumption checklist

- Read this file, model register, current source/config, and relevant run metadata.
- Verify actual working directory and read/write permissions; UI panel position
  is not evidence of repo access.
- Preserve source provenance and raw results. Analysis artifacts outside the repo
  may need copying/recreation; do not assume they are committed.
- Update this file after decisions and completed experiments; label proposals,
  implementations, and completed runs distinctly.
- Link this file from root README. Keep model definitions in MODEL_REGISTER and
  exact experimental details in metadata; this file is the navigation/handoff.


## Completed five-seed threshold comparison

Saved episode files were checked across seeds 2026-2030, 1,000 histories per seed
and 5,000 per policy. New threshold seeds are in
`results/sweep-20260911T180613122294Z`; seed 2026 is reused from
`results/sweep-20260911T050226158766Z`. The graduated B=10 reference is in
`results/sweep-20260911T030850898132Z` (filter B safety_response=10).

| Policy for B | A payoff | B payoff | Catastrophes / 5,000 |
|---|---:|---:|---:|
| Graduated B=10 | 8.212 | 0.886 | 41 |
| Threshold 0.05 | 8.060 | 0.818 | 51 |
| Threshold 0.10 | 7.974 | 0.772 | 57 |

The comparison is completed, not merely proposed. B-payoff differences remain
uncertain; neither threshold superiority nor equilibrium was established.
An effort-matched timing comparison remains a separate possible future study.
The duplicate-removal note above remains applicable; reused seed-2026 histories
are counted once, not as fresh evidence.

## Finished delay implementation and next discussion

FG-M004 adds four independent capability/safety delays by lab, default zero.
One production loop constructs decisions from previous effective stocks, invests
and releases work due at t+d, then checks catastrophe. Pending queues retain
realized amounts, arrival periods, and lab attribution, including beyond-horizon
work. FG-M004 originally hid pending amounts; FG-M005 now exposes their schedules.
Only effective capability
wins the prize and only effective stocks affect risk. Catastrophe stops arrivals.
At FG-M004 introduction, zero-delay runs retained policy-based model IDs.
FG-M005 now records those as behavior_model_id, preserving old fields/RNG consumption;
output schema 3 adds pending diagnostics consistently, so files are not claimed
byte-identical. See model.md and MODEL_REGISTER.md for definitions and provenance.

Verification uses a test-only reference from Git f9774c1796c37a714379270828a8f604da567609,
exact zero-delay comparisons (including final RNG state), deterministic timing and
conservation checks, terminal/fatal cases, and tiny temporary runner outputs.
Final verification: `python -m pytest -q --basetemp .pytest-tmp-delay-final`
passed all 399 tests; `git diff --check` passed. The default temporary directory
initially produced permission errors; repository-local temporary outputs worked.
Two override regressions found during verification were corrected before this
passing full-suite run. The delay implementation was subsequently committed as
673f6d21dec32ba2d85cfcc00049ceaa537072c9; no delay research experiment was launched.

Unimplemented: incident-driven additive/replacement delays; rescheduling pending
work; temporary/permanent restrictions and release gates;
recoverable incidents and remediation; counting pending capability as risk while
withholding credit for pending safety.

Proposed first delay experiment, for discussion only: hold the graduated reference
policies fixed and compare symmetric capability/safety delay pairs (0,0), (1,1),
(1,2), and (2,1). Do not execute without research authorization.


## Pending-work observation extension (FG-M005 history)

FG-M005 adds `own_pending_capability`, `opponent_pending_capability`,
`own_pending_safety`, `opponent_pending_safety`, `own_capability_delay`,
`opponent_capability_delay`, `own_safety_delay`, and `opponent_safety_delay` to
immutable observations. Existing effective stock, period, and horizon fields remain.
Schedules contain frozen `PendingArrival(amount, arrival_period)` records, sorted
by absolute arrival period and copied independently from engine queues.

Both observations precede either decision. Due-now work is pending until the update;
beyond-horizon work remains visible. Earlier investment shocks have already realized
the observed capability amounts. Current decisions/investment, future shocks, policy
internals, mutable queues, and RNG state remain excluded. Empty tuples mean known
empty schedules; omitted manual fields are None (unavailable), not zero. The simulator
always supplies exact schedules and configured delays. There is only shared effective
safety; pending safety retains its producing lab.

The true engine state -> observation builder -> immutable observation -> policy
boundary permits future measurement uncertainty, missing/delayed reports, strategic
concealment/misreporting, and regulatory disclosure transformations or audit errors.
These mechanisms remain unimplemented. Future observation randomness needs a separate
stream; none is added now. No projection or anticipated-gap rule is imposed.

Existing policies and all physical transitions/risk calculations are unchanged.
New runner metadata describes exact visibility using exact-pending-pre-decision-v1;
scientific model_id is FG-M005 and behavior_model_id records the earlier classification
reproduced by current policies. Output schema remains 3, metadata schema remains 1.
No full schedules are added to episode/trajectory files; existing pending totals are
post-update diagnostics, distinct from policy observations. Historical files and the
duplicate threshold-run removal note above are preserved.

Implementation and verification are authorized; research runs are not. Changes remain
uncommitted for review at the observation-extension handoff. The pending-aware
policy is now implemented as described in the FG-M006 update below. Uncertain observations, cheating, regulatory
reporting, dynamic delays/rescheduling, restrictions/release
gates, and remediation remain unimplemented. The proposed delay comparison above
remains for discussion only.


Observation-extension verification: the full suite passed 513 tests with
`python -m pytest -q --basetemp .pytest-tmp-observation-full`. After relaxing arrival
record validation to preserve engine numerical values without extra transition
rules, all 114 observation tests passed again with
`python -m pytest tests/test_pending_observations.py -q --basetemp .pytest-tmp-observation-final-focused`.
`git diff --check` passed. Exact reference checks include complete episode results,
traces, and final RNG states for fixed, safety-gap, graduated, and threshold policies
with zero/nonzero delays, survival/catastrophe, and tracing on/off. Timing, perspective,
immutability, retained snapshots, known-empty/unavailable information, current-action
exclusions, and both runners' metadata were also checked. Only temporary test outputs
were created; no research experiments or historical output changes were made.


## Pending-aware graduated policy implemented (FG-M006)

PendingAwareGraduatedPolicy is exported and selectable as pending_aware_graduated.
It retains base_allocation=.6, deficit_response=.1, safety_response=.2 and adds
capability_lookahead and safety_lookahead, both default None (JSON null). None
ignores a category; zero counts due-now work; k includes current period through
period+k inclusive, with no horizon cap. Both labs use the same window per category.
Enabled windows require both schedules; known-empty is valid, unavailable is an error.

With selected own/opponent pending capability P_i/P_j and combined pending safety P_S,
anticipated_gap=max(0,max(C_i+P_i,C_j+P_j)-(S+P_S)). Allocation is
clip(base_allocation + deficit_response*(C_j-C_i) - safety_response*anticipated_gap,0,1).
The deficit remains effective-stock based. Both None delegates to GraduatedPolicy.
Exact realized pending amounts are used without new shocks or rescaling.

This is a policy measure under perfect information, not physical risk or a forecast.
It can count later safety against earlier exposure and does not optimize future
choices. No current-gap floor or maximum-over-future-gaps correction is imposed.
Transitions, observations, arrival timing, and actual catastrophe risk are unchanged.
No learning, memory, rollouts, or dynamic delays were added.

The new family is FG-M006. Active windows (including zero) give behavior_model_id
FG-M006. Both None preserves FG-M003 behavior with zero delays or FG-M004 with delays.
Old policy families remain FG-M005. Resolved metadata records nullable lookaheads;
output schema 3 and metadata schema 1 remain, with no full schedules added to rows
and full tracing still optional/off. The example config explicitly includes both
lookaheads for --set/--sweep, including null and zero.

Saved (1,2) delay baseline: results/sweep-20260911T204618486225Z, children 0001-0005,
seeds 2026-2030, 1,000 histories each. Saved metadata confirms symmetric capability
delay 1/safety delay 2, graduated A safety_response=.05 and B=10, base=.6 and
deficit_response=.1 for both, all complete. This supersedes the old note treating
all delay runs as merely proposed; no baseline outputs were changed or regenerated.

Proposed comparison, discussion only: hold baseline environment and coefficients
fixed, retain both-None as the exact control, and choose capability/safety windows
independently before running a paired comparison against the saved baseline.
The example config matches the baseline and starts with both windows null for both
players. No pending-aware research experiment is authorized or launched, and no
superiority or equilibrium claim is made. Implementation remains uncommitted for review.


Verification: 568 tests passed with `python -m pytest -q --basetemp
.pytest-tmp-pending-policy-full`. After the final metadata wording update,
169 policy/observation tests passed with `python -m pytest tests/test_pending_policy.py
tests/test_pending_observations.py -q --basetemp .pytest-tmp-pending-policy-final`.
`git diff --check` passed. Checks cover exact ignore-mode actions, episodes, traces,
and RNG states; inclusive independent windows, due-now versus future/past arrivals,
both safety producers, effective deficit, unavailable/empty information, clipping,
validation, beyond-horizon inclusion, unchanged physical risk, and null/zero JSON
construction/overrides/sweeps/metadata. No research runs or result changes occurred.


## Decision-gap diagnostics implemented; research comparison pending

Output schema 4 adds decision_gap_a/b only to full Monte Carlo trajectories.csv.gz
when --save-trajectories is enabled. Episode, summary, and illustrative trajectory
files remain unchanged. Supported policies report their exact pre-decision gap
calculation: effective gap for graduated/threshold/safety-gap, anticipated gap for
pending-aware graduated. Both-null windows give the effective gap. Fixed and
unsupported custom policies report unavailable (None/blank), never assumed zero.

A pure optional decision_gap(observation) calculation is shared with allocation
logic. Diagnostics use the exact immutable decision observation, do not repeat
allocation calls or draw randomness, and keep no per-policy diagnostic state.
Ordinary traces do not request diagnostic recomputation. Scientific/behavior model
IDs and metadata schema 1 remain unchanged; no historical results are rewritten.
These fields explain the policy calculation, not whether a different decision
would have prevented catastrophe. No storage-overhead measurement was performed.

Planned comparison, for discussion only: B safety_response coefficients 1, 3, 10
across (capability_lookahead, safety_lookahead) pairs (0,0), (1,1), (1,null), with
physical capability delay 1 and safety delay 2. Research execution remains a
separate user action. No research experiment is launched by this implementation;
changes remain uncommitted for review.

Verification: `python -m pytest -q --basetemp .pytest-tmp-decision-gap-full`
passed all 607 tests. `git diff --check` passed. Focused checks cover supported
policy measures, pending-safety credit reducing a positive effective gap to zero,
null/zero and independent lookaheads, exact observations and one allocation call,
fixed/custom blanks, unchanged outcomes/original trace fields/RNG state, no history
state leakage, and file boundaries. Matched temporary runs produced byte-identical
episode, summary, and illustrative CSVs with full tracing on/off. No compression
or storage-overhead measurement was performed. Changes remain uncommitted.


## PendingWeightedGraduatedPolicy implemented (FG-M007)

Separate policy pending_weighted_graduated adds safety_weights instead of
safety_lookahead. Weight j credits both labs' pending safety arriving at t+j;
effective safety stays fully counted. The anticipated safety is S + sum_j w[j]
*(S_A_due_t+j+S_B_due_t+j). The anticipated capability and effective-capability
deficit follow the existing pending-aware/graduated rules. Allocation clips
base + deficit_response*(C_opponent-C_own) - safety_response*anticipated_gap.

Weights default empty, are copied to immutable floats, and must be finite numeric
values in [0,1], excluding booleans/strings/null entries. They need not sum to one.
[1] and [1,0] equal safety lookahead 0; [1,1] equals lookahead 1; [] and all-zero
vectors ignore safety and need no schedules. [.5,.5] averages due-now/next totals.
Positive weights require both safety schedules; unavailable is not known-empty.
Capability requirements remain controlled by capability_lookahead. Missing/past/
out-of-window arrivals get no credit; beyond-horizon arrivals within the vector do.
Physical protection still starts only at arrival. No other policy or engine changed.

The example uses physical delays (1,2) for both labs; A remains pending-aware with
base .6, deficit .1, safety .05, both windows null. B is weighted with base .6,
deficit .1, safety 10, capability window 1, safety_weights [.5,.5]. Other settings,
trials, and seed match the existing pending-aware example. JSON config and quoted
--set accept arrays only for safety_weights. No array sweeps are introduced; compare
vectors with separate invocations. Resolved config/provenance include normalized
weights, and optional full-trace decision gaps use the allocation's pure calculation.

FG-M007 identifies the new family. Its active pending behavior is FG-M007, while
ignore mode retains previous compatible pair-level behavior IDs. Existing policy
IDs are unchanged. Schema 4 remains current; earlier schema-3 passages in the
historical notes refer to prior additions, not the current full-trace contract.
The earlier discussion plans are proposals, not authorization for this task.

This is a new scientific hypothesis, not evidence of improvement or a coding-error
fix. Research runs remain a separate user action. No research command was executed,
no results changed, and source remains uncommitted for review.


Weighted-policy verification: all 679 tests passed with `python -m pytest -q
--basetemp .pytest-tmp-weighted-full`. After the explicit array-sweep rejection,
133 weighted-policy/override/sweep tests passed with `python -m pytest
tests/test_weighted_policy.py tests/test_experiment_overrides.py
tests/test_experiment_sweeps.py -q --basetemp .pytest-tmp-weighted-final`.
`git diff --check` passed. Exact unit-window equivalence covers deterministic and
noisy small episodes, complete traces (including optional decision gaps), outcomes,
and final RNG state. Hand-calculated credit, information requirements, immutability,
invalid settings/preflight, normalized provenance, and scalar-parser boundaries
also passed. No unresolved implementation issue was found; research efficacy is
untested. Only tiny temporary verification outputs were generated.
