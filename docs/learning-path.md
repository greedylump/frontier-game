# Learning path

Work in small checkpoints; explain each result before adding machinery.

1. **Python and one episode.** Read the dataclasses and loop. Set noise and hazard
   to zero and calculate three transitions by hand. Match the test and trace.
   Explain arrays, dictionaries, functions, imports, and why the RNG is passed in.
2. **Probability.** Run the notebook with 100, 1,000, then 10,000 episodes.
   Explain a sample mean, sample standard deviation, standard error, and interval.
   Reproduce a run with the same seed, then change the seed.
3. **Game theory.** Compare all four restraint/race policy pairs. Hold the opponent
   fixed and identify profitable deviations, including uncertainty. Explain why
   mutual safety is not automatically a Nash equilibrium.
4. **Sensitivity.** Change V, L, or hazard_scale one at a time using Config.
   Write a short finding with a figure, assumptions, and a counterexample.
5. **Compute.** Record runtime versus trial count. Profile before optimizing.
   Compare speed and numerical agreement before adopting an accelerated version.

Before presenting: explain the transition order, where randomness enters, why the
hazard is bounded, what the prize represents, what a fixed policy cannot do, and
which assumption you would challenge first. Keep an AI-assistance log and rewrite
any code you cannot explain. Each checkpoint should leave a reproducible artifact.
