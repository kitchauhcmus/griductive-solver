# Run, test, and debug in VS Code

The local repository is `E:\FAI 2\griductive-solver`. Use the existing Python
3.13.5 environment at `.venv\Scripts\python.exe`. The checkout now contains
the team's full application from `main`, which is the integration contract.
The game uses its production Engine, CNF encoder and DPLL. The separate Agent
demo uses synthetic fixtures and an exhaustive test oracle.

## 1. Open the workspace and select Python

1. In VS Code choose **File > Open Workspace from File...**.
2. Open `E:\FAI 2\griductive-solver\griductive-solver.code-workspace`.
3. In Explorer confirm that `main.py`, `griductive`, `puzzles`, `tests` and
   `examples` are directly under the project folder.
4. Install Microsoft's **Python** and **Python Debugger** extensions if missing.
5. Press `Ctrl+Shift+P`, run **Python: Select Interpreter**, and select
   `E:\FAI 2\griductive-solver\.venv\Scripts\python.exe`.
6. If it is not listed, choose **Enter interpreter path...** and browse to it.

Tasks and debug configurations use this interpreter explicitly. The commands
below also avoid activation, so PowerShell execution-policy changes are unnecessary.

## 2. Install the test dependency and run the complete suite

Choose **Terminal > New Terminal** and use PowerShell:

```powershell
Set-Location -LiteralPath 'E:\FAI 2\griductive-solver'
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

If pip is unavailable, bootstrap it before the installation:

```powershell
.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The full suite uses pytest. It includes main's function tests and fixtures,
plus the Agent's unittest classes. Running only `unittest discover` does not
execute the full production suite. See [VALIDATION.md](VALIDATION.md) for the
latest verified pass count; counts may change as the team adds tests.

Run only the Agent classification module:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent.py -q
```

Run one test method:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agent.py::ClassificationTests::test_forced_criminal_innocent_and_unknown -v
```

The focused unittest command remains valid for that class-based test:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_agent.ClassificationTests.test_forced_criminal_innocent_and_unknown -v
```

Tests cover classifications, unknown/inconsistent KBs, proof-gated reveals,
Engine/Solver result validation, uniqueness, real puzzle sequences, CLI and web
API behavior. Two truth-table methods contain thousands of small checks; their
internal case count is different from the displayed number of collected tests.

## 3. Run the application and real integration example

```powershell
.\.venv\Scripts\python.exe main.py
```

Keep that terminal running while using the local browser UI. Ctrl+C stops the
server. To run real-module integration without opening the GUI:

```powershell
.\.venv\Scripts\python.exe -m examples.team_integration puzzles\3x3_binary_chain.json
.\.venv\Scripts\python.exe -m examples.team_integration puzzles\3x3_binary_chain.json --max-steps 1
.\.venv\Scripts\python.exe main.py validate puzzles
```

The integration example uses the existing production Encoder, DPLL and Engine.
It prints JSON with the stop reason, accepted moves, metrics and trace.

## 4. Run the isolated Agent demonstration

```powershell
.\.venv\Scripts\python.exe -m examples.agent_demo
```

The expected result is nine accepted verdicts, SOLVED and 36 SAT calls, followed
by the first trace. This fixture enables
`check_revealed_consistency=True`, adding an immediate KB check after each
accepted reveal. Production-compatible construction defaults to False and keeps
main's initial three-call auto-step contract. Do not compare query counts across
these modes without accounting for the extra checks.

The synthetic demo is useful for stepping through code; it is not the team's
DPLL benchmark. The real application already exists and uses main's modules.

Under **Terminal > Run Task...**, **Agent: run all tests** runs full pytest and
**Agent: run demo** runs the fixture demonstration. Tasks set the working folder
and interpreter automatically. The test task is also available through
**Tasks: Run Test Task** in the Command Palette.

## 5. Use the Testing view

1. Select the flask-shaped **Testing** icon in the Activity Bar.
2. Refresh discovery if the list is empty.
3. Expand a test module or class and run the selection with its play button.
4. Use **Run All Tests** for the complete suite.
5. Select a failed test to inspect its traceback and source location.

The workspace uses **pytest** discovery in `tests`. If VS Code asks you to
configure tests, choose pytest and the tests directory. Ensure pytest is installed
in the selected `.venv`, then run the terminal command if discovery fails.
Official workflow: [VS Code Python testing](https://code.visualstudio.com/docs/python/testing).

## 6. Debug with F5

1. Open `griductive/agent.py` and put a breakpoint on the first executable line
   inside `_classify`. It tests the two opposite verdict assumptions.
2. Open `griductive/controller.py` and put another breakpoint inside
   `_accept_proved`, where a proved verdict is handed to Engine.
3. Open **Run and Debug** (`Ctrl+Shift+D`).
4. Select **Agent demo (test oracle)** and press F5.

Useful Watch expressions depend on the selected stack frame:

- `_classify`: `cell_id`, `variable`, `formula.clauses`, `formula.primary_variables`.
- `_solve`: `assumptions`, `purpose`, `result.satisfiable`, `result.assignment`,
  `self.stats.sat_calls`. Some locals only exist after their assignment executes.
- `_accept_proved`: `classification.status`, `classification.queries`,
  `state.proved`, `state.revealed_clues`.
- After the `updated` assignment: `updated.proved`, `updated.revealed_clues`,
  `self.check_revealed_consistency`.

The Call Stack shows who called the current method. `self` is the object for
that frame: Agent in agent.py, Controller in controller.py, Solver in dpll.py.
Use F10 to step over, F11 to enter a call, Shift+F11 to return, F5 to continue,
and Shift+F5 to stop.

**Agent tests (all)** debugs full pytest. **Agent test (forced verdicts)**
debugs the single class-based test from the terminal example. For another test,
use its debug action in Testing. Details:
[VS Code Python debugging](https://code.visualstudio.com/docs/python/debugging).

## 7. Connect teammates' changes through main's contract

Read [TEAM_INTEGRATION.md](TEAM_INTEGRATION.md) and the Vietnamese
[AGENT_HANDOFF.md](AGENT_HANDOFF.md). Shared models remain those from main,
including concrete Clue/RegionSpec/Puzzle and football player metadata.
`from griductive.engine import GameController, GameEngine` still works;
engine.py re-exports the single implementation from controller.py.

`LogicAgent()` lazily uses the real CNF and DPLL modules. Explicit dependency
injection remains available for isolated tests. Preserve existing GUI/CLI call
sites, production tests and imports when changing a module.

The GUI calls Controller methods, not Engine's reveal operation directly.
Main's web Match serializes actions with a lock. Preserve that coordination,
and do not overlap a background Controller operation with Restart/Load.
Timer-driven stepping helps display each reveal but does not make long SAT
queries nonblocking by itself.

## 8. Common problems

- **Wrong working folder:** run the quoted Set-Location command above.
- **`python` opens the Microsoft Store:** use the explicit `.venv` executable.
- **Activation is blocked:** the provided commands do not need activation.
- **`No module named pip`:** use ensurepip, then install requirements.
- **`No module named pytest`:** install requirements in the same interpreter
  selected by VS Code.
- **`attempted relative import with no known parent package`:** run modules
  with `-m`; agent.py is a library, not a standalone executable.
- **Missing CNF/DPLL/Engine module:** this checkout should include those from
  main. Check that the complete branch was checked out; do not copy test fixtures
  into production as replacements.
- **Only class-based tests appear:** ensure pytest discovery is enabled and
  unittest discovery is disabled, then refresh Testing.
- **Unknown debugger:** install Microsoft's Python Debugger extension and select
  a named launch configuration.

These steps run local code. Publishing changes is a separate Git operation.
