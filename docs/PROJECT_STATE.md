# Frontier Game: project state and handoff

Prepared from the research conversation and saved results through run
`sweep-20260911T180613122294Z`, plus verified delay implementation.
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


## Latest completed experiment: five-seed threshold comparison

Saved episode files were checked across seeds 2026?2030, 1,000 histories per seed
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
work. Existing policies cannot see pending amounts; only effective capability
wins the prize and only effective stocks affect risk. Catastrophe stops arrivals.
Zero-delay runs retain policy-based model IDs and exact old fields/RNG consumption;
output schema 3 adds pending diagnostics consistently, so files are not claimed
byte-identical. See model.md and MODEL_REGISTER.md for definitions and provenance.

Verification uses a test-only reference from Git f9774c1796c37a714379270828a8f604da567609,
exact zero-delay comparisons (including final RNG state), deterministic timing and
conservation checks, terminal/fatal cases, and tiny temporary runner outputs.
Final verification: `python -m pytest -q --basetemp .pytest-tmp-delay-final`
passed all 399 tests; `git diff --check` passed. The default temporary directory
initially produced permission errors; repository-local temporary outputs worked.
Two override regressions found during verification were corrected before this
passing full-suite run. Source remains uncommitted for review; no research
experiment was launched.

Unimplemented: incident-driven additive/replacement delays; rescheduling pending
work; temporary/permanent restrictions and release gates; pending-aware policies;
recoverable incidents and remediation; counting pending capability as risk while
withholding credit for pending safety.

Proposed first delay experiment, for discussion only: hold the graduated reference
policies fixed and compare symmetric capability/safety delay pairs (0,0), (1,1),
(1,2), and (2,1). Do not execute without research authorization.
