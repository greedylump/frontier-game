# Monte Carlo notes

An episode is one sampled history; trials are independent replications for a fixed
configuration and policy pair. Estimate expected payoff with the sample mean.
The standard error is sample standard deviation / sqrt(N), using ddof=1.
Quadrupling N roughly halves standard error under independent finite-variance
sampling. This addresses simulation noise, not model misspecification.

Payoff and duration intervals use mean +/- t_(0.975,N-1)*SE. These are approximate
for discrete/skewed distributions, especially with few trials or rare catastrophes.
Catastrophe frequency uses a Wilson binomial interval, which stays informative
when no events are observed. Zero observed catastrophes does not establish zero risk.
The reported event standard error is a plug-in estimate and can be zero at the boundary.
Intervals are marginal, without adjustment for many comparisons or repeated looks.

SeedSequence(seed).spawn(N) creates a separate random stream per episode. Increasing
N preserves earlier episodes. Reproduce with the same source, configuration, seed,
and package versions; metadata captures versions and settings. RNG algorithms and
floating-point results need not be identical across future environments.

Use independent seeds for policy comparisons by default, as in the notebook.
If deliberately using common random numbers, analyze paired differences and ensure
draws correspond to the same modeled events; stopping times complicate alignment.
The notebook's convergence curve uses nested samples, so plotted points are correlated.
Do not repeatedly stop when a desired result becomes significant. Preselect N for a
confirmatory run; use exploratory results to plan it. Rare-event questions may require
far more samples or carefully validated variance-reduction methods.
