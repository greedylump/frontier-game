# Research and machine-migration handoff — 2026-09-14

Read this first, then PROJECT_STATE.md, MODEL_REGISTER.md, model.md, and the
relevant source and resolved run metadata. This document preserves discussion
and analysis from the research chat that may not be accessible on the new machine.
It records completed work and proposals separately; it authorizes no new sweeps.

## Current status and conflicts with older documents

Current implementation commit: `ee125620460396d3c9c54bb8fac7025da05a2dff`
(weighted policy). The working tree was clean before this handoff edit.
Threshold intervention, delays, pending observations, pending-aware policy,
decision-gap diagnostics, and weighted policy are implemented. All have progressed
beyond the initial implementation-only stage; completed research is recorded below.

Older PROJECT_STATE/model/register passages saying delay runs are unauthorized or
pending, FG-M006 has no research runs, FG-M007 efficacy is untested, or implementations
remain uncommitted describe earlier task boundaries. They are stale as statements
of current status. Preserve historical metadata; use this dated update and actual
run metadata for the later evidence. Prior user-authorized runs do not authorize
an agent to launch arbitrary future research sweeps.

Current scientific ID for weighted-policy runs is FG-M007; output schema is 4.
Earlier schema-3 descriptions are historical. A different model ID does not imply
different numerical behavior for mathematically equivalent parameter settings.

## Research purpose and collaboration preferences

Long-term question: under what assumptions and amount/type of outside pressure
(regulation, agreements, enforcement) does safer cooperation become individually
worthwhile and stable against unilateral deviations among competing frontier labs?
Current work establishes an understandable unregulated baseline. No equilibrium,
continuous optimum, or real-world predictive calibration has been demonstrated.
Explicitly define cooperation, deviation opportunities, and policy search space
before claiming stability. A's fixed policy matters to every B ranking below.

This is also a learning project in Python, Monte Carlo, game theory, and eventual
compute scaling. Explain science plainly, using concrete time-step examples.
Prefer small extensible changes and scientific discussion before implementation.
The user normally runs research commands manually after committing code; the agent
reviews, analyzes existing outputs, and supplies commands. Tiny implementation
verification runs are different from research sweeps. Do not introduce GPU/RL/cloud
machinery merely because it could be used. Do not delete results without authorization.

The user insists that anticipation is a POLICY choice, not an engine restriction.
Perfect information may legitimately be used with asymmetric horizons or weights.
Do not force a maximum-future-gap rule, equal horizons, or a preferred forecast
into the observation builder. The original pending-aware rule implemented the
agreed equation; weighted credit is a new hypothesis, not a coding-bug fix.

## Equations, names, and timing that repeatedly caused confusion

Effective capability stocks are C_A, C_B (`capability_a/b` in state/output).
There is ONE effective shared safety stock S (`safety`), not separate effective
S_A/S_B. Pending safety retains the producing lab's attribution. Observations use
own/opponent capability and shared safety; inspect Observation for exact field names.

For capability allocation a_i in [0,1], safety effort is 1-a_i:

    produced capability_i = g*a_i*exp(-sigma^2/2 + sigma*Z_i)
    produced shared safety = h*((1-a_A)+(1-a_B))
    physical gap G = max(0, max(C_A,C_B)-S)
    per-period catastrophe probability = 1-exp(-lambda*G_post_update)

Defaults: H=30, g=1, h=.6, sigma=.25, lambda=.01. Catastrophe terminates
the episode with -50 for each lab. Otherwise terminal effective leader gets 10,
loser 0, exact tie 5 each. Thus total expected payoff = 10-110*p_catastrophe.
Shared-gap example: C_A=5,C_B=3,S=4 gives G=1; raising S to 5 gives G=0.
Safety production example: a_A=.6,a_B=.2 produces .6*(.4+.8)=.72 shared safety.

Four delays are independently configurable: capability_delay_a/b and
safety_delay_a/b. Work invested at t with delay d arrives during UPDATE t+d.
Decisions occur BEFORE due-now arrivals, using previous effective stocks and exact
pending schedules. Productivity noise is drawn at investment; pending capability
is already realized, not a forecast draw. Current decisions are absent from the
observation. After decisions/investment, due work arrives, then catastrophe is tested.
Beyond-horizon work stays pending and earns no terminal prize or current protection.
Only effective stocks enter physical risk. One unified production loop handles all
delays; do not restore a separate zero-delay simulation engine. Exact zero-delay
compatibility remains a regression requirement, not a rationale for duplicate loops.

With safety delay 2, decision step 3 sees safety invested at 1 due at 3 and safety
invested at 2 due at 4. Lookahead 1 includes BOTH batches (due-now plus next step).
It excludes investment at 3, which is not chosen yet and will arrive at 5.
The concern was crediting two pending batches, not producing two periods of effort
from one decision. Due-at-4 safety cannot protect against step-3 catastrophe.

Graduated allocation:

    a_i = clip(base + k_D*(C_opponent-C_own) - k_G*decision_gap, 0, 1)

The deficit term uses effective capability even in pending policies. k_G may exceed
1; allocation is clipped, the coefficient is not. B=10 was retained as a strong
sampled reference after earlier zero-delay searches, not as a universal default or
an optimum. The subsequent 1,3,10 comparison explicitly tested that choice.

PendingAwareGraduatedPolicy selects capability/safety arrivals independently:
null ignores a category, 0 includes due-now, k includes t through t+k inclusive.
Anticipated gap = max(0,max(C_i+P_i,C_j+P_j)-(S+P_safety)). No horizon cutoff.
Both null exactly reproduce graduated behavior. This is prescribed accounting,
not a rollout, action optimizer, or estimate of the whole future path.

PendingWeightedGraduatedPolicy retains capability lookahead and replaces the
safety window with weights w[j] indexed by arrival offset:

    S_antic = S_eff + sum_j w[j]*(S_A_due_(t+j)+S_B_due_(t+j))
    G_antic = max(0,max(C_i+P_i,C_j+P_j)-S_antic)

Weights are finite numbers in [0,1], need not sum to 1, and never weight S_eff.
[]/[0,0] ignore pending safety; [1,0] credits due-now; [1,1] full two-batch credit;
[.5,.5] averages batches; [1,.5] discounts only next-step safety. Missing periods
are zero; out-of-vector arrivals ignored. See model.md for validated API details.

## Completed experiments missing from the earlier state narrative

Unless stated otherwise: 1000 trials per seed, seeds 2026–2030, 5000 per setting;
both base=.6,k_D=.1; A k_G=.05 and no pending awareness. Environment as above.
Delay pairs below mean (capability delay, safety delay) for BOTH labs, not lookahead.

### Delay baseline and pending-aware results

Graduated B=10 reference with zero delays: A=8.212, B=.886, catastrophe .82%.
Delayed graduated baselines:

| Delays | A payoff | B payoff | Catastrophe | Sweep under results/ |
|---|---:|---:|---:|---|
| (1,1) | 7.058 | 1.204 | 1.58% | sweep-20260911T204603090479Z |
| (1,2) | 5.396 | .446 | 3.78% | sweep-20260911T204618486225Z |
| (2,1) | 6.938 | 2.006 | .96% | sweep-20260911T204632954197Z |

Pending-aware B=10 at physical delays (1,2):

| B capability/safety lookahead | A | B | Catastrophe | Sweep |
|---|---:|---:|---:|---|
| 0/0 | 6.282 | .704 | 2.74% | sweep-20260912T031613605319Z |
| 1/1 | 1.808 | -2.830 | 10.02% | sweep-20260912T031639902684Z |
| 1/null | 5.990 | 1.634 | 2.16% | sweep-20260912T031704452248Z |

At capability delay 1, all existing pending capability is due-now, so capability
windows 0 and 1 are equivalent here. The comparison differs in safety credit.
Clean pending-aware null/null verification experiment-20260912T031417205638Z
matched the delayed graduated seed-2026 baseline and the earlier dirty duplicate
experiment-20260912T031330545923Z. Duplicates are repeated evidence, not new samples.

Coefficient follow-up (B=1,3,10) reproduced the rankings; lower k_G did not rescue
full future safety credit. Its numerical results also appear as equivalent rows
in the weighted table below. Traced seed2026 sweeps:
0/0 sweep-20260912T190351960947Z; 1/1 sweep-20260912T190501866301Z;
1/null sweep-20260912T190607399121Z. Each has children 0001/2/3 for k_G=1/3/10.
Other-seed k_G=1,3 sweeps: sweep-20260912T190419079621Z,
sweep-20260912T190528363828Z, sweep-20260912T190635716125Z respectively.
These six folders were intentional, not an accidental double execution.

At 1/1 seed2026, physical post-gap was positive in 95.78%,92.35%,86.63% of
executed periods for k_G=1,3,10. Mean decision gaps .0877,.0406,.0288 versus
mean physical post-gaps .5647,.4308,.3579. These are different measures/times,
not automatically forecast errors. Fatal periods count; periods after death do not.

### Safety delay 1 equivalence experiment

Physical delays (1,1), B=10, lookaheads 0/0 and 1/1:
sweep-20260913T030855919711Z and sweep-20260913T030920235999Z.
All matching episode, summary, and illustrative trajectory files were byte-identical.
Both yield A=7.828, B=1.182, 45/5000 catastrophes (.90%). No future pending batch
exists to distinguish those windows. These are 5000 distinct histories repeated
under equivalent settings, not 10000 independent samples. Faster physical safety
also changes the environment; this is not an isolated proof of averaging efficacy.

### Weighted-policy comparison, completed at ee12562

Physical delays restored to (1,2), B capability lookahead=1. All 75 configurations
completed cleanly; 75000 episodes include 45000 repeated equivalent-control histories
and 30000 histories under new fractional settings. Each row has 5000 trials.

| Safety weights | B k_G | A payoff | B payoff | Catastrophes / 5000 |
|---|---:|---:|---:|---:|
| [1,1] | 1 | -1.956 | -5.094 | 775 |
| [1,1] | 3 | .300 | -3.808 | 614 |
| [1,1] | 10 | 1.808 | -2.830 | 501 |
| [.5,.5] | 1 | 5.626 | -.312 | 213 |
| [.5,.5] | 3 | 6.256 | .444 | 150 |
| [.5,.5] | 10 | 6.330 | .546 | 142 |
| [1,.5] | 1 | 2.766 | -2.182 | 428 |
| [1,.5] | 3 | 4.582 | -.896 | 287 |
| [1,.5] | 10 | 5.086 | -.432 | 243 |
| [1,0] | 1 | 5.848 | -.006 | 189 |
| [1,0] | 3 | 6.258 | .574 | 144 |
| [1,0] | 10 | 6.282 | .704 | 137 |
| [0,0] | 1 | 6.726 | .854 | 110 |
| [0,0] | 3 | 6.208 | 1.416 | 108 |
| [0,0] | 10 | 5.990 | 1.634 | 108 |

Source sweeps in table weight order:

- [1,1]: sweep-20260913T032911228087Z
- [.5,.5]: sweep-20260913T033024308323Z
- [1,.5]: sweep-20260913T033134098590Z
- [1,0]: sweep-20260913T033242805370Z
- [0,0]: sweep-20260913T033351530472Z

Each folder: children 0001–0005 are k_G=1/seeds2026–2030; 0006–0010 k_G=3;
0011–0015 k_G=10. All 45 equivalent-control episode files matched older runs
byte-for-byte. No full Monte Carlo trajectories were requested for these sweeps.

Averaging greatly improves on full credit but is not best among tested settings.
Holding due-now weight=1, raising next-step weight 0 -> .5 -> 1 worsens B payoff
and catastrophe rate at all three k_G. Ignoring pending safety ranks best for B.
Paired B differences averaging minus due-now-only: k_G=1: -.306, 95% CI
[-.4243,-.1877]; 3: -.130 [-.2381,-.0219]; 10: -.158 [-.2561,-.0599].
These are exploratory Student-t intervals, not multiplicity-adjusted or validation
on unseen seeds. Rankings do not prove universal policy superiority.

### Matched full-trajectory follow-up (completed, not the next unrun task)

Seed2026, B=10, 1000 trials each, full trajectories enabled:

| Weights | Experiment under results/ | B payoff | Catastrophes | Positive post-gap periods |
|---|---|---:|---:|---:|
| [0,0] | experiment-20260913T034137479803Z | 1.49 | 28 | 12.74% |
| [1,0] | experiment-20260913T034149422910Z | .77 | 31 | 24.03% |
| [.5,.5] | experiment-20260913T034201542207Z | .47 | 32 | 25.46% |

All episodes matched their corresponding sweep child 0011 byte-for-byte. Counts of
executed trace rows: 29242,29210,29202 respectively. This adds diagnostics, not
independent outcome evidence. Pair on (experiment_seed,trial,step), retain only
common executed periods for direct trajectory comparisons, and disclose truncation.

Against [0,0], each alternative reached a first differing B allocation in 972 trials.
Effective pre-stocks matched at that first difference. Every first difference was
more capability effort under pending-safety credit, mean +.6884 ([1,0]) or +.6859
(averaging). Two periods later shared safety was lower by about .413/.412 on average.
Only 4/3 of those 972 comparisons had higher physical gap then; the first effect
was a smaller reserve, not immediate positive risk. Eight periods after first
difference, higher gaps occurred in 11.11%/12.45% of those matched comparisons.

Trial 0: actions agree through step4. At step5 [0,0] decision gap=.7504 and B
capability allocation=0; both alternatives gap=0 and B allocation=.7091. All have
effective safety=2.1779 then. At step7 safety is 3.9879 for [0,0] versus 3.5624
for alternatives: .6*.7091=.4255 less safety from the step5 choice. [0,0] keeps
full safety through step7 and resumes capability at step8. Physical gaps remain
zero for all through step18; at steps19/20 alternatives have gaps .056/.087 while
[0,0] stays zero. This illustrates delayed depletion of a reserve, not an immediate
catastrophe caused by the first differing action.

Interpretation supported here: ignoring pending safety induces longer safety
investment and builds a conservative buffer under delayed delivery. It does not
show that less information is inherently better, nor that pending information
cannot support a better policy. Means pool surviving/executed periods; changing
survivor composition can affect period-average curves.

## Next scientific decision — still unresolved

The last authorized trajectory diagnostic is DONE. No subsequent experiment or
implementation has been agreed. Decide with the user whether to:

1. Test whether an explicit target safety reserve can capture the benefit of
   conservative credit while using due-now information accurately. This is a
   candidate mechanism experiment, not an already agreed new policy.
2. Broaden weights/coefficients or physical delays, using held-out seeds and possibly
   different A policies before generalizing. Avoid endless tuning to seeds2026–2030.
3. Return toward the long-term regulation/deviation question once the baseline is
   sufficiently understood. A best response within five weight vectors is not an
   equilibrium or a demonstration of stable cooperation.

Do not repeat the just-completed three trace runs as if they remain outstanding.
Do not conflate reducing physical safety delay with changing policy valuation.

## Deferred ideas and motivation preserved from the chat

Recoverable incidents versus terminal catastrophe was discussed before delays.
The user questioned whether all harmful failures warrant a hard stop: some serious
incidents cause damage without ending the world/game. A real-world hacking example
was offered as motivation, not verified evidence or calibration. Retain the terminal
catastrophe baseline; a recoverable incident class remains unimplemented.

Possible incident losses of 15/25 versus terminal 50 were floated, NOT selected or
calibrated. Payoff-only incidents may mainly lower means (unevenly by exposure)
without answering how recovery works. Open decisions: incident probability/severity,
terminal versus recoverable outcomes, recovery duration, capability/safety effects,
information revealed, and permitted decisions during recovery. Possible responses:
temporary allocation restrictions, capability suspension, compulsory safety effort,
remediation costs, safety-learning gains, damaged capability, regulatory intervention.
These are alternative mechanisms, not one approved bundle. Avoid assuming that an
incident automatically yields effective safety before investigation/remediation.

Delay motivation was real-world time to deployment versus time to inspect logs,
understand/replicate a failure chain, devise a response, and validate/deploy safety.
Both capability and safety can take time; their relative delay is empirical, not
a built-in moral claim that safety is harder. First scope deliberately chose four
configurable deterministic delays, with work realized at investment and a unified
queue mechanism. Dynamic delays were postponed.

Future incidents/policies/regulation could add delays, replace delays with a fixed
value, make capability delays temporary/permanent, or gate capability release until
safety arrives. Must distinguish changing delay for NEW investments from rescheduling
already queued work. No semantics for those changes are currently agreed.

Observation extensibility: future uncertainty, delayed/missing reports, competitor
cheating/concealment, and regulatory distortion/audit error should act at the
observation boundary. Keep effective truth separate from reported observations.
Own/opponent pending capability and safety can be transformed separately. No
competitor current action, future uninvested shock, or policy internal is exposed.
Unavailable (None) is not known empty (()). Stochastic reporting should use a
separate RNG so adding observation noise does not perturb physical random draws.
Perfect-information schedules today do not commit the project to perfect information
forever. Observation builder supplies information; policy chooses horizons/weights.

Other existing backlog remains relevant: hysteresis (state/reset needed), trends,
short planning rollouts with separate RNG and explicit opponent assumptions,
alternative payoff structure, safety depreciation/imperfect sharing, leader/challenger
initial asymmetry, more labs. None is silently authorized by this handoff.

## Technical navigation, replay, storage, and transfer

- src/frontier_game/model.py: Config, observations/builder, policies, unified simulate.
- src/frontier_game/monte_carlo.py: trials, seeding, summaries/trace plumbing.
- experiments/laptop/run_experiment.py: JSON config, overrides, sweeps, metadata.
- experiments/laptop/configs/pending_weighted_graduated.json: current weighted example.
- tests/test_weighted_policy.py and related override/sweep tests: API/equivalence.
- model.md and MODEL_REGISTER.md: full definitions and history.

`--set` supplies one parameter value; a quoted safety_weights JSON array supplies
one vector, not multiple games. `--sweep "seed=2026,2027"` supplies separate values
and creates separate games; repeated sweep axes form a Cartesian product. The user
calls the comma-separated list 'CSV'; distinguish it from --sweep-csv file input.
Array-valued sweep axes are intentionally unsupported. Separate PowerShell foreach
invocations vary weight vectors. The user dislikes accidental redundant games.

Full `trajectories.csv.gz` are optional. `decision_gap_a/b` occur there only; normal
episodes/summary/illustrative trajectory retain their schemas. Post-gap is physical
risk after arrivals; decision_gap is the policy's pre-decision measure. Cumulative
hazard exposure is sum(lambda*G), not catastrophe count or probability. The separate
illustrative trajectory.csv is not one of the summarized Monte Carlo trials.

Reconstruct full trajectories by rerunning EXACT config, code, seed mapping/trial
count and compatible numerical environment into a NEW folder with --save-trajectories.
Verify episode equality before treating it as a replay. Never edit old result files
to pretend new diagnostics were originally recorded. Clean commit plus metadata
does not guarantee environment equivalence; preserve version information.

Migration: `.venv/`, `results/*` except results/README.md, and `/outputs/` are ignored.
A Git clone alone DOES NOT transfer raw experiments or figures. Copy results/ and
outputs/ separately if their evidence is needed; keep metadata with episode/trace
files. Do not put all bulk outputs into Git just to solve migration. Recreate .venv
on the new machine using README installation steps; do not rely on copying a Windows
virtual environment. It was roughly 550MB in an earlier discussion; result sizes
have grown since the earlier ~130MB audit, so those are not current measurements.

Known ignored local analysis artifacts:
- outputs/safety-delay-comparison/safety-delay-comparison.png
- outputs/safety-delay-comparison/anticipated-vs-actual-gap.png
- outputs/safety-delay-comparison/period-averages.csv
- outputs/lookahead-diagnostic/first-divergence.csv
- outputs/lookahead-diagnostic/trial-0-comparison.csv

Earlier analyses also lived outside this repo at
`C:\Users\ab294\Documents\Codex\2026-09-07\referenced-chatgpt-conversation-this-is-an\outputs`.
PROJECT_STATE identifies those older analyses. They are not guaranteed to exist
on the new machine. This handoff preserves the known conclusions, not every old
external artifact. Use run metadata/episodes when available to independently verify.

The workspace file contains only folders:[{path:'.'}]. Opening the saved workspace
or project folder edits the same checkout; neither transfers files or chat history.
The user is moving machines because the laptop is unreliable and explicitly did
not request diagnosis of chat/project visibility in the other app.

Historical verification reported in repo: weighted implementation 679 tests passed,
then 133 focused tests after array-sweep rejection. These were not rerun for this
documentation handoff; research-result comparisons above were performed in the chat.
No source changes, experiment launches, deletions, commits, or uploads are part of
this handoff task. Commit/push this documentation and separately transfer ignored
evidence to make it available elsewhere.
