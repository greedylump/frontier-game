# Game-theory notes

The underlying object is a finite-horizon stochastic game: state (time,C_A,C_B,S),
joint allocation actions, stochastic transitions, and terminal utilities. V1 only
evaluates constant actions. A dynamic policy could condition on time and state.

For each pair of fixed policies, Monte Carlo estimates E[U_A] and E[U_B]. A 2x2
table over allocations 0.4 (restraint) and 0.8 (race) is a restricted normal-form
game over these two constant policies. The notebook builds this table.
For each B column, A's best response maximizes A's payoff; for each A row, B's
best response maximizes B's payoff. A mutual best response is a pure Nash equilibrium
only within that restricted strategy set, subject to estimation error.

Do not infer dominance from one matchup or call a close numerical maximum a proven
best response. Use fresh replications and uncertainty on payoff differences.
Allowing all allocations or state-dependent deviations can overturn a restricted
equilibrium. Mixed strategies randomize over policies; they are different from a
deterministic intermediate allocation. Markov-perfect equilibrium needs optimal
state-contingent responses, including off-path states; this engine does not solve it.

Next questions: when does higher prize value encourage racing? When does greater
catastrophe cost favor restraint? Later, add one intervention with explicit costs
and information assumptions. More compute cannot establish the validity of those
assumptions or turn a policy comparison into an equilibrium solver.
