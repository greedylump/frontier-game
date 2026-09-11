# Model and assumptions

Two symmetric abstract competitors represent a leader/challenger pair, not named
labs or countries. The initial state is C_A=C_B=S=0. Capability difference is
C_A-C_B; the safety shortfall is max(0, max(C_A,C_B)-S).
Each actor has one unit of effort per period and simultaneously allocates a
fraction a_i in [0,1] to capability, leaving 1-a_i for shared safety. FG-M001
uses fixed allocations; FG-M002 also permits per-period observation-based rules.

At the start of every period (indexed 1 through H), construct both exact,
immutable player observations from the same pre-transition state: own capability,
opponent capability, and shared safety, plus period and horizon. Then call both
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
spillovers in capability, or endogenous entry. Effective stocks are observed exactly; pending work is excluded from policy observations.
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
and negatives. A nonzero value classifies the run as FG-M004; all-zero runs retain
their policy-based FG-M001/FG-M002/FG-M003 classification.

Work invested in period t with delay d becomes effective during the update of
period t+d, before its catastrophe check. Both observations and validated decisions
come first, using effective stocks at the end of the previous completed period.
Arrivals due now are therefore invisible to current decisions. For delay 1,
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
temporary/permanent restrictions and release gates, pending-aware policies,
recoverable incidents/remediation, and counting pending capability as risk while
withholding credit for pending safety are all unimplemented.
