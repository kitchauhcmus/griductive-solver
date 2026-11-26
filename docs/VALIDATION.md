# Agent validation and main compatibility — 23 November 2026

The integration contract is team `main` at
`d946dd1e3c9dab194b3931d71957ab226c2a270a`. The compatibility update retains
main's application modules, assets, puzzles, concrete shared models, package
exports and production tests. On Windows with Python 3.13.5 and pytest 8.4.2,
the combined checkout passed **106 tests in 78.11 seconds**: all 35 main tests
unchanged, the original 64 Agent tests, and seven added main-contract tests.
This is a correctness run, not a repeated performance benchmark.

## Run the complete suite

From the repository root, using the local virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m examples.agent_demo
.\.venv\Scripts\python.exe main.py validate puzzles
.\.venv\Scripts\python.exe -m examples.team_integration puzzles\3x3_binary_chain.json
```

The game itself uses the standard library. The full test suite needs pytest;
it includes main's function tests/fixtures and the Agent's unittest classes.
`unittest discover` alone does not validate the production suite. If this local
environment lacks pip, first run `.\.venv\Scripts\python.exe -m ensurepip --upgrade`.

## Contracts to verify

- Main's public import paths resolve to the same GameController implementation.
- Clue/RegionSpec/Puzzle parsers and player metadata remain available.
- Existing CNF and DPLL result objects are accepted without schema changes.
- The default initial 3x3 auto-step uses exactly three SAT calls, preserving main.
- Optional `check_revealed_consistency=True` adds one immediate KB query per
  accepted reveal; strict-mode demo counters must be compared within that mode.
- Existing 3x3, 4x4 and 5x5 reveal sequences, uniqueness, no-secret-information
  behavior, CLI, web API, experiment runner and all original main tests remain valid.
- Agent regression tests reject invalid SAT models and malformed Engine reveals,
  preserve prior facts, isolate assumptions and stop safely on inconsistent KBs.

The bounded truth-table tests compare 758 formula/mapping cases and 6,822
public-verdict states against independently evaluated truth tables. These are
bounded correctness checks, not a general proof of Encoder or DPLL correctness.

The synthetic `examples.agent_demo` uses an exhaustive test oracle and fixture
Encoder/Engine, with immediate post-reveal consistency checks enabled. Its
verified result is nine accepted moves, 36 SAT calls and SOLVED. Real puzzle
integration uses the production modules from main, not the test oracle. A real
3x3 CLI solve also passed: eight accepted moves, 24 SAT calls and SOLVED;
the strict integration example passed one accepted move with four SAT calls
and STEP_LIMIT when run with `--max-steps 1`.

## Historical evidence

Before main was integrated, the isolated Agent suite passed 64 unittest methods
and a temporary reference harness solved four 3x3/4x4 puzzles from
[reference commit 587b04c](https://github.com/hyt2434/Griductive-Solver/tree/587b04cbd56ab2f2835e9ce905e6c98ff5817187).
That earlier check did not validate the team's current web/CLI/5x5 application.
It is retained only as historical context; the current full suite is the acceptance
check. Existing reports and benchmark files from main are retained and are not
presented as new measurements of this compatibility update.
