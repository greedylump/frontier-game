# Frontier Game

A small Python learning/research project about two-player frontier AI competition.
Ask: **how does allocating effort to capability versus shared safety change expected
payoffs and catastrophe frequency under explicit assumptions?** FG-M001 evaluates
fixed policies; FG-M002 adds per-period rules with exact observations. Neither
solves the dynamic game or predicts real-world events.

## Start in VS Code

Install Python 3.11 or newer and open this folder (or `frontier-game.code-workspace`).
Accept the recommended Python and Jupyter extensions. From a PowerShell terminal:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m frontier_game --trials 1000 --seed 42
```

These commands do not require activating scripts or changing execution policy.
On macOS/Linux use `python3 -m venv .venv`, then `.venv/bin/python` for the remaining commands.
In VS Code run **Python: Select Interpreter** and select `.venv`; select that same
environment as the notebook kernel. F5 runs the baseline under the debugger.
The `frontier-game` command is also available when the environment is activated.

Each run creates a fresh `results/run-...` directory containing episode-level CSV,
summary CSV with uncertainty, metadata JSON, and a payoff chart. An explicit
`--output results/my-run` must name a new directory to protect earlier experiments.
Try `--a 0.4 --b 0.4`, then `--a 0.8 --b 0.8`. See `--help` for all flags.

## Where to read and work

- `src/frontier_game/model.py`: parameters, immutable observations, policies, one episode.
- `src/frontier_game/monte_carlo.py`: independent replications and uncertainty.
- `src/frontier_game/cli.py`: experiment outputs.
- `tests/`: model boundary cases and reproducibility checks.
- `notebooks/01_explore.ipynb`: inspect a trajectory, compare policies, plot convergence.
- `experiments/laptop/`: repeatable experiment entry point.
- `docs/`: [assumptions](docs/model.md), [learning path](docs/learning-path.md),
  [game theory](docs/game-theory.md), [Monte Carlo](docs/monte-carlo.md),
  [compute regimes](docs/compute.md), [portfolio workflow](docs/workflow.md).

Use modules for machinery and notebooks for questions. No GPU, cloud, or RL setup
is needed. Dependencies have lower bounds for installation flexibility; save an
environment snapshot for any result you intend to publish (see workflow).


For the manual adaptive entry point, see [laptop experiments](experiments/laptop/README.md).
The existing CLI and fixed-allocation scripts remain FG-M001 compatibility runs.
