# Griductive Solver — Logic Agent & Integration

Team repository: https://github.com/kitchauhcmus/griductive-solver

This branch implements the **Logic Agent và tích hợp** role for the five-person
team. The repository was empty when work began. The engine, clue encoder, DPLL,
and GUI are separate teammates' modules; they are not implemented by this branch.

The package layout and public API names follow
[hyt2434/Griductive-Solver](https://github.com/hyt2434/Griductive-Solver/tree/587b04cbd56ab2f2835e9ce905e6c98ff5817187).
The implementation here is original; the reference's application, report, data,
and assets have not been copied into this repository.

## Run locally

Start with the [VS Code run and debug guide](docs/VSCODE_GUIDE.md) for Testing
view, F5, breakpoints, individual tests, and common setup errors. The workspace
also provides **Agent: run all tests** and **Agent: run demo** under Run Task.

Open `griductive-solver.code-workspace` in VS Code. Python 3.10+ is required.
The agent and tests need no third-party packages. A local `.venv` has been
created for this workspace. From the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m examples.agent_demo
```

On another computer, create that environment first with your installed Python:
`python -m venv .venv`. Using the environment's executable directly also works
when the global `python` command points to the Windows Store alias.

The demo uses tiny synthetic clues and an **exhaustive test oracle, not DPLL**.
It demonstrates the agent and reveal workflow while the other modules are being
written. It is not the final game, GUI, or project benchmark.

Once teammates add `griductive/cnf.py`, `griductive/dpll.py`, and the engine:

```python
from griductive.agent import LogicAgent
from griductive.controller import GameController
from griductive.engine import GameEngine  # supplied by the engine teammate

controller = GameController(GameEngine.load("puzzles/your_puzzle.json"), LogicAgent())
controller.auto_solve()
print(controller.last_run_status.value)
```

The [team integration walkthrough](docs/TEAM_INTEGRATION.md) explains the
contracts for all five roles. After those real modules exist, run
`python -m examples.team_integration puzzles/your_puzzle.json` to exercise them
and print the stop reason, metrics, and trace.

## Files and ownership

- `griductive/agent.py`: classifications, public KB, Hint, uniqueness, SAT metrics.
- `griductive/controller.py`: move verification, reveal loop, restart, traces.
- `griductive/models.py` and `contracts.py`: small shared public interfaces.
- `tests/`: behavioral and integration tests with isolated test fixtures.
- `examples/agent_demo.py`: executable agent demonstration.
- `examples/team_integration.py`: entry point for the real team modules.
- `docs/VSCODE_GUIDE.md`: run, test, and debug walkthrough.
- `docs/TEAM_INTEGRATION.md`: step-by-step module connection guide in English.
- `docs/AGENT_HANDOFF.md`: interfaces and the five-person integration agreement.
- `docs/AGENT_REPORT.md`: detailed Vietnamese report source for the agent role.
- `output/pdf/AGENT_REPORT.pdf`: formatted agent-role report.

Controller code lives outside `engine.py` so the engine teammate can work there
independently. No empty implementations of other teammates' modules are provided.
Their normal package locations remain `griductive/cnf.py`, `dpll.py`, `clues.py`,
`regions.py`, `engine.py`, `gui.py`, `cli.py`, and `experiments.py`, with root
`main.py`, `puzzles/`, `assets/`, `experiments/`, and `results/` as needed.

Read the handoff before changing shared types. Work on separate branches and
review changes to `models.py` and `contracts.py` together before merging.
