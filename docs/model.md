# Model and assumptions

Two symmetric abstract competitors represent a leader/challenger pair, not named
labs or countries. The initial state is C_A=C_B=S=0. Capability difference is
C_A-C_B; the safety shortfall is max(0, max(C_A,C_B)-S).
Each actor has one unit of effort per period and simultaneously allocates a fixed
fraction a_i in [0,1] to capability, leaving 1-a_i for shared safety.

For each period, in this order:

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
spillovers in capability, or endogenous entry. The full state is conceptually public,
but fixed policies ignore it. Risk is zero when capability does not exceed safety.
These choices can determine findings: vary them before drawing broad conclusions.
