# Model and assumptions

Two symmetric abstract competitors represent a leader/challenger pair, not named
labs or countries. The initial state is C_A=C_B=S=0. Capability difference is
C_A-C_B; the safety shortfall is max(0, max(C_A,C_B)-S).
Each actor has one unit of effort per period and simultaneously allocates a
fraction a_i in [0,1] to capability, leaving 1-a_i for shared safety. FG-M001
uses fixed allocations; FG-M002 also permits per-period observation-based rules.

At the start of every period (indexed 1 through H), construct both exact,
immutable player observations from the same pre-transition state: own capability,
opponent capability, shared safety, pending schedules and configured delays
(see FG-M005 below), plus period and horizon. Then call both
policies and validate both allocations as finite real numbers in [0,1]. Fixed
policies are called too and simply return their constant. Observation construction
is separate from evaluation; neither choice can observe the other current action.
No random draw or state update precedes validation.

With all delays zero, after the decisions retain these physical transitions in this order:

1. Draw independent Z_i ~ Normal(0,1). Set M_i=exp(-sigma²/2 + sigma Z_i).
   Update C_i <- C_i + capability_rate * a_i * M_i. E[M_i]=1.
2. Update S <- S + safety_rate * ((1-a_A)+(1-a_B)). Safety is deterministic,
   perfectly shared, cumulative, and has no depreciation.
3. Let G=max(0,max(C_A,C_B)-S). Draw catastrophe with probability
   p=1-exp(-hazard_scale*G). The implementation uses expm1 for numerical accuracy.
4. If catastrophe occurs, terminate immediately and give both actors -L.
   Otherwise continue to the finite horizon H.
5. On survival, the actor with greater final capability receives V and the other
   receives zero. Exact equality splits V equally. No per-period reward or discounting.

Defaults: H=30, capability_rate=1, safety_rate=0.6, sigma=0.25,
hazard_scale=0.01, V=10, L=50. All units are arbitrary; these are teaching choices,
not fitted estimates. The terminal prize is a proxy for first-mover value; there
is no deployment threshold or actual first-passage race in v1.

The all-restraint policy even earns a shared prize at zero capability. This is an
intentional simplifying consequence of the terminal relative-rank payoff; consider
a deployment threshold or absolute output benefit in a later experiment.
There are no budgets beyond allocation, private information, enforcement, learning,
spillovers in capability, or endogenous entry. Effective stocks are observed exactly; pending schedules and configured delays are also observed exactly.
Fixed policies ignore observations. Risk is zero when capability does not exceed safety.
These choices can determine findings: vary them before drawing broad conclusions.


The memoryless `SafetyGapPolicy` uses the pre-transition shared gap. It selects
`cautious_allocation` (default 0.30) only when that gap strictly exceeds
`gap_threshold` (default 0); otherwise it selects `normal_allocation` (default
0.50). Identical configurations yield equal actions, but independent productivity
shocks still allow unequal capabilities. This shared-gap rule is one policy;
identical future relative-position rules need not yield identical actions.

Optional traces retain legacy unprefixed post-transition state/outcome columns
and add explicit `pre_*`, `allocation_a/b`, and `post_*` columns. `step` is the
1-based decision period; `horizon` gives the total. For A, `pre_capability_a` is
own capability; for B, `pre_capability_b` is own capability. The shared values
are the same for both. See [the model register](MODEL_REGISTER.md) for scientific
IDs, retained FG-M001 interpretation, and provenance limitations.


## Configurable production delays (FG-M004)

`capability_delay_a`, `safety_delay_a`, `capability_delay_b`, and `safety_delay_b`
default to zero. Each accepts a nonnegative integer, rejecting booleans, fractions,
and negatives. These transition rules were introduced as FG-M004. Current runs
using legacy policies use FG-M005 for the expanded information interface; their `behavior_model_id`
records FG-M004 with delays, or FG-M001/FG-M002/FG-M003 without delays.

Work invested in period t with delay d becomes effective during the update of
period t+d, before its catastrophe check. Both observations and validated decisions
come first, using effective stocks at the end of the previous completed period.
Arrivals due now are visible as pending schedules, but not as effective stocks. For delay 1,
one unit of capability invested each period gives post-update stocks [0,1,2]
in a three-period deterministic episode.

One simulation loop handles all configurations. Capability productivity shocks
are drawn at investment, and realized amounts are scheduled by lab and arrival
period. Safety production is deterministic; pending safety retains its producing
lab until arrival into the shared pool. Zero-delay investments update immediately.
Due queues are drained regardless of delays for new investments. The original
capability arithmetic and immediate shared-safety summation order are retained.
Immutable Config contains no episode state; queues are local to each simulation.

Only effective stocks enter the gap, hazard, and terminal capability ranking.
Beyond-horizon work remains unfinished, with no prize value or protection.
Catastrophe ends processing immediately; no future arrivals are applied.

Output schema 3 retains all historical columns and adds `pending_capability_a`,
`pending_capability_b`, `pending_safety_a`, and `pending_safety_b` to episode results
and optional traces, including zeros in immediate configurations. Trace amounts
are measured after current investment and arrivals, before the catastrophe draw;
episode amounts describe that same measurement in the last executed period,
including a fatal period. These are realized unfinished production amounts,
not effort units. Effective stock columns retain their existing meaning.
Metadata schema remains 1. Full Monte Carlo trajectories remain off by default;
`--save-trajectories` enables them. The separate illustrative trajectory remains.

Exact tests compare every historical result/trace field and final RNG state with
the pre-delay Git implementation for fixed, safety-gap, graduated, and threshold
policies, with and without tracing. This is numerical/behavioral compatibility,
not byte-identical files: new columns and resolved configuration fields are added.

Dynamic incident-driven additive/replacement delays, rescheduling pending work,
temporary/permanent restrictions and release gates,
recoverable incidents/remediation, and counting pending capability as risk while
withholding credit for pending safety are all unimplemented.


## Pending-work observations (FG-M005)

The observation boundary is true engine state -> `make_observations` -> immutable
`Observation` -> policy. The builder copies both views before either decision;
it neither advances queues nor consumes randomness. Legacy fixed, safety-gap, graduated, and threshold policies are unchanged
and ignore the added information. The delay engine and actual gap/hazard calculation
remain unchanged: only effective capability and effective shared safety enter risk.

The public API exports `PendingArrival(amount, arrival_period)`, a frozen record
of realized production and absolute 1-based arrival period. `Observation` retains
`period`, `horizon`, `own_capability`, `opponent_capability`, and `shared_safety`,
and adds:

- `own_pending_capability`, `opponent_pending_capability`;
- `own_pending_safety`, `opponent_pending_safety`;
- `own_capability_delay`, `opponent_capability_delay`;
- `own_safety_delay`, `opponent_safety_delay`.

Schedules are immutable tuples sorted by arrival period, aggregating work by lab,
work type, and arrival period in the engine. Snapshots are independent of mutable
queues. Safety schedules retain the producing lab; no opponent effective safety
stock or historical attribution of effective safety is constructed.

At the start of t, schedules include work due at t and beyond the horizon. Work
created by either current decision is absent. Capability amounts are exact realized
production from earlier investment shocks, an explicit perfect-information assumption.
Neither current opponent actions, future shocks, policy internals, mutable queues,
nor RNG state are exposed. Configured delays describe new investments; arrival
records describe work already scheduled. No anticipated gap, projection, lookahead
horizon, or next-period filter is imposed by the builder.

Five-argument `Observation(...)` and stock-only `make_observations(...)` calls still
work: added fields default to `None`, meaning unavailable. `()` means known empty,
and delay 0 means known immediate production. The simulator always supplies all
exact schedules and delays. Manual schedule lists are copied into immutable tuples.
A known-empty observation therefore differs from an otherwise equal stock-only one.

Future measurement uncertainty, missing data, delayed reports, competitor concealment
or misreporting, and regulatory restrictions/reporting transformations/audit errors
belong at the observation boundary. They are unimplemented. Stochastic observation
rules must use a separate random stream to avoid changing physical productivity
and catastrophe draws. No unused observation RNG, registry, or reporting actions
are introduced. FG-M006 below adds a pending-aware measure; planning rollouts
and optimization of future actions remain unimplemented.

Runner observation metadata uses `exact-pending-pre-decision-v1` and lists fields,
timing, visibility, and exclusions. New JSON run/sweep and safety-gap runner metadata
uses scientific ID FG-M005, plus `behavior_model_id` for the earlier classification
reproduced by existing policies. Metadata schema 1 and output schema 3 are retained:
no episode or trajectory columns change and schedules are not serialized by default.
Existing pending-total diagnostics measure post-update unfinished work, whereas
policy schedules are pre-decision snapshots. Historical outputs/metadata are untouched.


## Pending-aware graduated policy (FG-M006)

`PendingAwareGraduatedPolicy`, JSON identifier `pending_aware_graduated`, retains
`base_allocation=0.6`, `deficit_response=0.1`, and `safety_response=0.2` and adds
`capability_lookahead=None` and `safety_lookahead=None`. Lookaheads accept only None
(JSON `null`) or nonnegative integers; booleans, fractions, negative values, and
strings are rejected. Coefficient validation is inherited from GraduatedPolicy.

For each category independently, None ignores its pending schedules entirely.
Zero includes due-now work. Integer k selects records whose absolute arrival period
satisfies `observation.period <= arrival_period <= observation.period + k`.
The window is applied to both own/opponent schedules of that category. No cutoff
is imposed at the episode horizon: beyond-horizon work counts if within the window.
When a window is enabled, both relevant schedules must be available; None raises
a field-specific error while an empty tuple contributes zero. Ignored categories
need no schedule information. Configured investment delays do not choose the window.

Let P_i/P_j be selected own/opponent pending capability and P_S the sum of selected
own and opponent pending safety contributions. With effective stocks C_i, C_j, S:

```text
anticipated_gap = max(0, max(C_i + P_i, C_j + P_j) - (S + P_S))
deficit = C_j - C_i
allocation = clip(base_allocation + deficit_response * deficit
                  - safety_response * anticipated_gap, 0, 1)
```

The deficit uses effective capability only. Both lookaheads None delegates directly
to GraduatedPolicy for exact behavior, including stock-only observations. The new
policy has no memory, randomness, predictions of investment/actions/shocks, learning,
or rollouts. Pending amounts are exact realized investment-time production under
the perfect-information observation assumption; they are not redrawn or rescaled.

This is one prescribed policy measure, not physical catastrophe risk. It can count
later safety against earlier capability exposure, can fall below the current gap,
and can credit work that earns no terminal prize or protection within the horizon.
It neither takes a maximum over future gaps nor claims simultaneous arrivals or
optimized future actions. Physical transitions, arrival timing, effective-stock
hazard calculation, observations, and existing policies remain unchanged.

Runs containing this policy family use model_id FG-M006 even in ignore mode.
If either policy enables either window (including 0), behavior_model_id is FG-M006,
even if realized queues happen to be empty. If all windows are None, the inherited
graduated behavior is FG-M003 with zero delays or FG-M004 with nonzero delays.
Other policy families retain FG-M005 and their earlier behavior classification.
Metadata schema 1, output schema 3, and observation ID exact-pending-pre-decision-v1
remain unchanged. Resolved policy metadata includes both nullable lookaheads.
No full schedules or new trajectory columns are saved; full traces stay off by default.

The example `experiments/laptop/configs/pending_aware_graduated.json` explicitly
includes both lookaheads for each player so --set and --sweep can address them.
JSON null is accepted in lookahead sweep axes; unrelated numeric axes stay strict.
The example matches the saved symmetric (1,2) delay baseline's coefficients and
starts in ignore mode. A comparison of independently chosen windows against that
baseline is proposed for discussion only, not executed or evidence of superiority.


## Optional full-trace decision gaps (output schema 4)

Only `trajectories.csv.gz`, enabled by `--save-trajectories`, adds `decision_gap_a`
and `decision_gap_b`. `episodes.csv`, `summary.csv`, and the separately seeded
illustrative `trajectory.csv` retain their previous columns and values. Unavailable
values are None in memory and blank in CSV. No schedules, counted pending amounts,
or additional result columns are added. Full tracing remains off by default.

GraduatedPolicy records its effective gap; SafetyGapPolicy and
ThresholdInterventionPolicy record the effective gap compared to their thresholds.
PendingAwareGraduatedPolicy records its anticipated gap using its independent
lookaheads, including null and zero semantics; both null give the effective gap.
FixedPolicy and unsupported custom policies record unavailable, not zero.

The optional pure `decision_gap(observation)` method shares the exact calculation
with each supported policy's allocation rule. The Policy interface still requires
only choose_allocation. A custom diagnostic must be deterministic and read-only;
a custom subclass changing its decision rule must override inherited diagnostics
if they no longer describe its rule. No mutable last-decision state is used.

`simulate(..., trace=True, trace_decision_gaps=True)` and
`run_trials(..., trace_sink=..., trace_decision_gaps=True)` opt into the fields.
The JSON runner opts in only for full Monte Carlo traces. Additional diagnostic
recomputation uses the exact immutable decision observation after allocation
validation and before investment/arrivals, without another choose_allocation call
or random draw. Ordinary traces do not perform diagnostic recomputation.

These are pre-decision policy measures, distinct from post-update physical gap and
catastrophe hazard. They explain a policy calculation, not a risk forecast or proof
that a different action would have prevented catastrophe. In particular, pending
safety credit can make the decision gap zero while the effective gap is positive.

Output schema 4 identifies this optional full-trace addition; metadata schema 1,
scientific model IDs, behavior IDs, and observation IDs stay unchanged. Metadata
places the two definitions under full_trajectories.decision_gap_definitions and
explicitly notes that the other file schemas retain schema-3 columns. Historical
metadata/output files are not rewritten. This is instrumentation, not a new model.


## Pending-weighted graduated policy (FG-M007)

`PendingWeightedGraduatedPolicy`, JSON type `pending_weighted_graduated`, is a
separate policy hypothesis about how to value pending safety. It does not correct
an error in PendingAwareGraduatedPolicy or establish that averaging is better.
All existing policies, observations, transitions, arrival timing, physical gap,
catastrophe calculation, and random-number consumption remain unchanged.

Parameters: base_allocation=.6, deficit_response=.1, safety_response=.2,
capability_lookahead=None, safety_weights=(). The capability window retains the
pending-aware semantics and per-lab summation: None ignores it; integer k >= 0
includes records with t <= arrival_period <= t+k for both labs. Effective capability
alone still determines the deficit. There is no safety_lookahead parameter;
passing it fails validation.

For decision period t and weights w indexed from zero:

```text
S_anticipated = S_effective + sum_j w[j] * (S_A_due_at_t+j + S_B_due_at_t+j)
G_anticipated = max(0, max(C_own_anticipated, C_opponent_anticipated) - S_anticipated)
allocation = clip(base_allocation
                  + deficit_response * (C_opponent_effective - C_own_effective)
                  - safety_response * G_anticipated, 0, 1)
```

Weights apply only to pending safety, never effective safety. Missing periods
contribute zero; past arrivals and arrivals beyond the vector receive no credit.
The window is not capped at the horizon. No future investments or arrivals are
invented. Pending amounts already contain their realized investment-time production.

- [] ignores pending safety; [0,0] does too.
- [1] credits due-now safety; [1,0] is equivalent.
- [1,1] credits due-now and next-period safety fully.
- [.5,.5] averages these two arrival totals.
- [1,.5] credits due-now fully and next-period by half.

Weights need not sum to one. Accept a sequence of finite real numbers in [0,1],
rejecting booleans, strings, null entries, negative/above-one values, NaN, infinity,
and nested containers. Policy construction copies weights to an immutable tuple
of floats. JSON config and --set use arrays; normalized provenance serializes them
as arrays. Empty/all-zero vectors require no safety schedules. Any positive weight
requires both labs' schedules, even if no arrival falls in its window; unavailable
is an error, while known-empty is valid. Capability requirements remain independent.

The inherited graduated allocation method calls this policy's pure decision_gap,
so optional full traces record exactly the weighted gap used for allocation.
No extra allocation calls, diagnostic state, or random draws are introduced.
Per-lab safety sums preserve exact unit-window equivalence to existing pending-aware
settings. Physical safety protects only after arrival; weighted credit is a policy
measure, not hazard prediction, optimization, or proof an action prevents catastrophe.

Any run containing this class is FG-M007. With any positive safety weight or enabled
capability window, behavior_model_id is FG-M007 (including unit-weight special cases).
When it ignores both pending categories, ordinary graduated behavior applies; the
other player's active policy can still determine FG-M006 behavior. Otherwise the
existing FG-M003 zero-delay / FG-M004 delayed classification applies. Existing policy
families keep their IDs. Current output schema remains 4, metadata schema 1, and
observation ID exact-pending-pre-decision-v1. Earlier schema-3 passages above describe
prior additions; only optional full traces contain decision_gap_a/b. Episode,
summary, and illustrative schemas remain unchanged.

Use the pending_weighted_graduated.json example for separate vector invocations:

```powershell
.\.venv\Scripts\python.exe experiments/laptop/run_experiment.py --config experiments/laptop/configs/pending_weighted_graduated.json --set "policies.b.parameters.safety_weights=[1,0.5]"
```

This is a research command for user review, not executed by this implementation.
The --set array exception is limited to the two safety_weights parameter paths;
other overrides remain scalar. Array-valued CLI/CSV sweeps are unsupported.
