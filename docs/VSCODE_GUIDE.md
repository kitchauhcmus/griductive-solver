# Run, test, and debug your agent in VS Code

Your local repository is `E:\FAI 2\griductive-solver`. The space in `FAI 2`
is part of the path. This guide uses the existing local Python 3.13.5 virtual
environment at `.venv\Scripts\python.exe`.

The demo runs your Logic Agent and integration controller with synthetic test
fixtures. It uses an exhaustive test SAT oracle, not the team's DPLL solver.
The final game and GUI depend on your teammates' modules.

## 1. Open the correct workspace

1. Open VS Code.
2. Choose **File > Open Workspace from File...**.
3. Open `E:\FAI 2\griductive-solver\griductive-solver.code-workspace`.
4. If VS Code asks whether you trust the workspace, review the folder and make
   that decision yourself. Running and debugging can be limited in Restricted
   Mode.
5. In Explorer, check that you can see `griductive`, `tests`, `examples`, and
   `griductive-solver.code-workspace` directly under the project folder.

The workspace already enables `unittest` discovery and recommends Microsoft's
Python extension. In **Extensions** (`Ctrl+Shift+X`), install **Python** by
Microsoft if it is missing. For F5 debugging, also install **Python Debugger**
by Microsoft if VS Code says the `debugpy` debugger is unavailable.

## 2. Select the local Python interpreter

1. Press `Ctrl+Shift+P` to open the Command Palette.
2. Run **Python: Select Interpreter**.
3. Select the interpreter whose path ends with
   `E:\FAI 2\griductive-solver\.venv\Scripts\python.exe`.
4. If it is not listed, use **Enter interpreter path...** and browse to that
   executable.

The tasks and debug configurations explicitly use this executable. The terminal
commands below also use it directly, so you do not need to activate the virtual
environment or change PowerShell's execution policy.

## 3. Run the tests in the terminal

Choose **Terminal > New Terminal**. With a PowerShell terminal, run:

```powershell
Set-Location -LiteralPath 'E:\FAI 2\griductive-solver'
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v
```

The current suite ends with `Ran 64 tests` and `OK`. The test count can grow as
your team adds tests. A failing test prints `FAIL` or `ERROR` and a traceback;
read the final traceback lines to find the failing assertion or exception.

These tests cover forced and unknown verdicts, inconsistent knowledge,
manual-move rejection, sequential clue reveals, traces, restart, solver result
validation, and uniqueness. The truth-table tests check many formulas inside two
test methods; the displayed method count is not the number of formula cases.

Run one test module:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest tests.test_agent -v
```

Run one test class:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest tests.test_agent.ClassificationTests -v
```

Run one test method:

```powershell
& '.\.venv\Scripts\python.exe' -m unittest tests.test_agent.ClassificationTests.test_forced_criminal_innocent_and_unknown -v
```

## 4. Run the agent demonstration

From the same repository-root terminal, run:

```powershell
& '.\.venv\Scripts\python.exe' -m examples.agent_demo
```

Expected results are nine accepted card verdicts, `Stopped: SOLVED`, and
`SAT calls: 36`, followed by the first deduction trace. Each accepted verdict
reveals a clue used by the next deduction. The trace shows the active clues,
SAT queries, chosen verdict, and newly revealed clue.

The 36 calls include checking the updated public knowledge base after each
reveal. This is a synthetic integration demonstration, not a benchmark of the
team's finished application.

You can also run either command through **Terminal > Run Task...**:

- **Agent: run all tests** runs the complete suite.
- **Agent: run demo** runs the synthetic demonstration.

The test task is the default test task, also available from **Tasks: Run Test
Task** in the Command Palette. These tasks set the working folder and Python
path automatically.

## 5. Use VS Code's Testing view

1. Select the flask-shaped **Testing** icon in the left Activity Bar.
2. Let the Python extension discover the tests. Use the view's refresh button
   if the list is empty.
3. Expand a test module and class to see individual methods.
4. Use the play button beside a method, class, or module to run that selection.
5. Use **Run All Tests** to run the complete suite.
6. Select a failed test to see its output and the source location of the failure.

Discovery is already configured in the workspace for `tests/test_*.py` using
`unittest`. If VS Code asks you to configure tests, choose **unittest**, the
`tests` directory, and the `test_*.py` pattern. If discovery fails, check the
selected interpreter and run the terminal test command first.
The supported discovery and run/debug workflow is described in the official
[VS Code Python testing guide](https://code.visualstudio.com/docs/python/testing).

## 6. Debug the demo with F5

1. Open `griductive/agent.py` in Explorer.
2. Find `def _classify(...)` and click in the left gutter beside its first
   executable line to set a red breakpoint. This method tests the criminal and
   innocent assumptions.
3. Open `griductive/controller.py` and set another breakpoint on the first
   executable line of `def _accept_proved(...)`. This is where a proved verdict
   is handed to the engine for reveal.
4. Open **Run and Debug** (`Ctrl+Shift+D`).
5. Select **Agent demo (test oracle)** from the configuration dropdown.
6. Press `F5`. Execution stops at your breakpoints.

While paused, inspect **Variables**, **Watch**, and **Call Stack**. Useful Watch
expressions depend on the selected stack frame:

- In `_classify`: `cell_id`, `variable`, `formula.clauses`, and
  `formula.primary_variables`.
- In `_solve`: `assumptions`, `purpose`, and `self.stats.sat_calls`. Set a
  breakpoint inside `_solve` to watch `()` for the base KB, then a positive or
  negative literal for a verdict query.
- In `_accept_proved`: `cell_id`, `classification.status`,
  `classification.queries`, `state.proved`, and `state.revealed_clues`.
- After the `updated` assignment in `_accept_proved`: `updated.proved` and
  `updated.revealed_clues`, so you can compare the snapshots before and after
  reveal.

Use `F10` to step over a line, `F11` to step into a function, `Shift+F11` to step
out, `F5` to continue, and `Shift+F5` to stop debugging. Hover over a variable
to see its current value. Read-only Watch expressions are enough for inspecting
the workflow.

Two more F5 configurations are provided:

- **Agent tests (all)** debugs the full test suite.
- **Agent test (forced verdicts)** debugs the single forced-verdict test used in
  the terminal example above.

To debug a different single test, use its debug action in the Testing view.
The supplied configurations use the Python Debugger's `debugpy` type and module
launch settings documented in the official
[VS Code Python debugging guide](https://code.visualstudio.com/docs/python/debugging).

## 7. Connect the real team modules

Read [TEAM_INTEGRATION.md](TEAM_INTEGRATION.md) for the step-by-step connection
guide and runnable real-module example. [AGENT_HANDOFF.md](AGENT_HANDOFF.md)
provides the Vietnamese handoff. Agree on shared types before combining files.

The agent owner maintains `griductive/agent.py` and
`griductive/controller.py`. Teammates add their implementations at the agreed
paths, such as `griductive/cnf.py`, `griductive/dpll.py`, and
`griductive/engine.py`. The production constructor `LogicAgent()` loads the CNF
encoder and DPLL solver when needed. The current tests and demo inject test
doubles, so they can run before those production modules exist.

After the real modules are connected, keep the current tests and add integration
tests that load your team's puzzle JSON and use its actual encoder, DPLL, engine,
and controller. The GUI should call the controller's public methods; it should
not call the engine's reveal method directly. Use `auto_step()` on GUI timer
ticks to show each reveal. For long SAT queries, run the operation in a worker
and update the GUI on its UI thread; timer ticks alone do not make SAT work
nonblocking. Never overlap controller operations or restart during a running
operation.

## 8. Common problems

- **PowerShell opens in the wrong folder:** run the quoted `Set-Location`
  command above. Imports and test discovery must start from the repository root.
- **`python` opens the Microsoft Store or is not found:** use the explicit
  `.venv\Scripts\python.exe` commands in this guide.
- **Activation is blocked by execution policy:** activation is unnecessary for
  the provided commands, tasks, and debug configurations.
- **`attempted relative import with no known parent package`:** run modules
  with `-m`. For example, use `-m examples.agent_demo` rather than running
  `griductive/agent.py` directly. The agent file is a library module.
- **`No module named griductive` or `tests`:** confirm the terminal folder is
  `E:\FAI 2\griductive-solver`, then rerun the exact command.
- **`CNFEncoder is unavailable` or `DPLLSolver is unavailable`:** the default
  production dependencies have not been added yet. The supplied tests/demo
  work independently through injected fixtures. Follow the handoff to connect
  the real modules; do not copy the test oracle into production.
- **`No module named pip`:** this existing local environment has no pip, and
  the agent/tests/demo require no third-party packages. You can run all commands
  in this guide without installing packages. Teammates can document any later
  GUI dependencies separately.
- **F5 offers the wrong file or reports an unknown debugger:** select one of
  the named configurations above and check that Microsoft's Python Debugger
  extension is installed. The configurations launch Python modules from the
  project root.
- **Test methods do not appear:** check the selected `.venv` interpreter,
  refresh the Testing view, and inspect its output. The terminal test command is
  an independent way to verify discovery.

These steps run and inspect local work. Publishing code to the team repository
is a separate Git action.
