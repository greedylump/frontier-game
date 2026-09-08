# Compute regimes

| Regime | Useful questions | What earns the move |
|---|---|---|
| Laptop CPU, v1 | Fixed-policy comparisons, trajectories, uncertainty, small sensitivity sweeps | Baseline timing and profiling |
| Faster local CPU / vectorization, optional | Larger sweeps and more precise payoff differences | Python loop overhead or CPU throughput measured as limiting |
| Gaming PC GPU, future | Large batches with identical transition structure; later approximate policy learning | Enough parallel work to repay transfers and a validated batch implementation |
| Cloud CPU/GPU, future | Many independent parameter sets, replications, richer policy search | An explicit question, budget, reproducible environment, and local bottleneck |

Current time scales approximately as trials * horizon (early termination reduces
work); episode output memory scales as trials. One trajectory is retained only when
requested. A GPU does not accelerate ordinary NumPy Python loops automatically.
Try profiling, batching, or CPU workers before adding frameworks. Preserve per-episode
seed identities when splitting work and compare against the serial reference.

Distinguish evaluating a fixed policy from solving a game. More players can be cheap
for fixed-policy simulation, while enumerating k actions for n players creates k^n
joint actions. Discretizing d state dimensions into m bins creates m^d states.
That explosion, rather than this small simulator, may eventually justify a GPU.

The CLI records wall time for simulation and episodes/second (excluding file and
chart generation). Benchmark increasing N on your own hardware; do not extrapolate
training speed from episode throughput. Cloud work later needs cost caps, checkpoints,
seed partitioning, and stored results. No cloud resources or GPU dependencies are set up.
