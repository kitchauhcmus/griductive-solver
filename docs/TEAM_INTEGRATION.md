# Connect the five team modules

The team's `main` branch is the integration contract. This checkout includes its
real Engine, CNF encoder, DPLL, CLI, web interface, puzzles and production tests.
Agent changes extend that application; they must preserve its shared models,
package exports and existing call sites. The small synthetic demo remains a
separate way to inspect agent behavior with an exhaustive test oracle.

## 1. Preserve the shared schema and imports

Import `Status`, `CellInfo`, `Clue`, `RegionSpec`, `Puzzle` and `PublicGameState`
from `griductive.models`. `Clue` and `RegionSpec` are concrete frozen
dataclasses, with `from_dict` parsers; they are not typing Protocols. Keep every
existing field and its defaults, including the player metadata on `CellInfo`
(`slug`, `ovr`, `club`, `nation`, `tier`, `shirt_number`). The web API serializes
these fields. Do not substitute a smaller agent-only model or a second enum.

`Puzzle` owns the full parsed puzzle, including secrets. `PublicGameState`
contains only title, size, cells, revealed clues and proved verdicts. Its
`proved` field remains a dictionary under the main contract. Engine returns a
fresh dictionary in each snapshot; callers must treat snapshots as read-only.
The Agent separately copies public containers before passing them to an Encoder.
Neither a frozen dataclass nor a shallow copy makes every nested object immutable.

`UNKNOWN` is `Classification.status is None`, not a third solution label.
Inspect `classification.inconsistent` before treating `None` as insufficient
knowledge. `.label` is available for display. Hints examine unresolved cells in
`(row, column, id)` order, matching the main puzzles' row-major cell order.

## 2. Connect the existing CNF encoder

The production implementation is `griductive.cnf.CNFEncoder`:

```python
encoder = CNFEncoder(state.size, state.cells)
formula = encoder.encode_public_state(state)
full_formula = encoder.encode_clues(tuple(all_clues))
```

Its result exposes `clauses`, `primary_variables` and `auxiliary_variables`.
Main's `griductive.cnf.CNFFormula` remains valid; the Agent accepts that structure
and normalizes it to its local contract container. Teammates need not replace
their types with those in `contracts.py`.

For example, `clauses=((1,), (-1, 2))` means `A1` and `A1 implies B1` when
the mapping is `{"A1": 1, "B1": 2}`. This two-cell fragment illustrates the
format; the real mapping must include every cell on the board. All declared
variable IDs must be distinct positive integers; literals are nonzero signed
IDs. Positive means criminal and negative means innocent. Main generates dense
IDs, while the Agent also supports sparse IDs by taking the largest declared ID
as the solver's `variable_count`.

`encode_public_state` must use only revealed clues and proved verdicts. The
Agent additionally inserts any missing proved unit clauses. `encode_clues`
encodes the supplied clue set for the separate administrative uniqueness check.
Do not pass unopened clues or the hidden solution to gameplay deduction.

## 3. Connect the existing DPLL solver

The production implementation is `griductive.dpll.DPLLSolver`:

```python
result = solver.solve(clauses, variable_count, assumptions=())
```

Main's `SATResult` and `SolverMetrics` types are structurally compatible with
the Agent. The result supplies a real Boolean `satisfiable`, a complete Boolean
`assignment` for SAT or `None` for UNSAT, and `metrics` containing `decisions`,
`propagations`, `conflicts`, `backtracks`, `recursive_calls` and `runtime_ms`.
The Agent's aggregate remains a dataclass usable with both `vars()` and
`dataclasses.asdict()`, as required by the CLI and web serializers.

`assumptions=(3,)` temporarily asserts variable 3; `(-3,)` asserts its negation.
They are separate classification queries. Assumptions must not leak into later
calls. The Agent supplies fresh clause lists, verifies returned SAT models
against the original clauses and assumptions, and copies returned metrics/models.
Errors and timeouts must raise exceptions rather than masquerading as UNSAT.
Model validation cannot certify UNSAT; retain the independent DPLL tests.

## 4. Keep Engine and Controller entry points compatible

The existing `GameEngine` remains in `griductive.engine`. It owns secrets,
loading, initial public facts and restart, and exposes:

```python
engine = GameEngine.load(path)
state = engine.public_state
finished = engine.solved
engine.restart()
clue = engine.reveal_after_proof(cell_id, status)
```

The Controller calls `reveal_after_proof` only after obtaining a forced verdict.
For a new accepted card, Engine must preserve the board and earlier public
facts, record exactly one new verdict, publish exactly one new clue ID, and
return that published clue. A mismatch must raise before mutating state. The
Controller validates the returned update and blocks further play until restart
if it detects a malformed update; it cannot roll back private Engine state.

There is one Controller implementation, in `griductive.controller`.
`griductive.engine` re-exports it to preserve main's imports. The GUI, CLI,
experiments and existing tests can continue using:

```python
from griductive.engine import GameController, GameEngine
```

`from griductive.controller import GameController` and the package-level exports
refer to the same class. Do not keep a second Controller with different behavior.

## 5. Wire the real components

```python
from griductive.agent import LogicAgent
from griductive.cnf import CNFEncoder
from griductive.dpll import DPLLSolver
from griductive.engine import GameController, GameEngine

engine = GameEngine.load("puzzles/3x3_binary_chain.json")
agent = LogicAgent(solver=DPLLSolver(), encoder_factory=CNFEncoder)
controller = GameController(engine, agent)
controller.auto_solve()
```

Pass `CNFEncoder`, not `CNFEncoder()`: the Agent creates an Encoder with the
current board's size and cells. The shorter `LogicAgent()` lazily loads the
same production modules. Explicit injection remains useful for isolated tests.

Main-compatible behavior is the default: an immediately forced `auto_step`
uses one base SAT check and two assumption checks. It reuses the hint proof.
To additionally check the new KB immediately after each reveal, opt in:

```python
controller = GameController(engine, agent, check_revealed_consistency=True)
```

This adds one SAT call per accepted reveal. In strict mode an accepted move may
return `ACCEPTED` while `last_run_status` becomes `INCONSISTENT`, because the
new clue contradicts the previously consistent knowledge. In default mode that
extra immediate check is omitted to preserve main's established query count;
subsequent deduction or an explicit consistency check can detect the contradiction.
Do not compare counters across modes as if the query workload were identical.

The real-module example can be run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m examples.team_integration puzzles\3x3_binary_chain.json
.\.venv\Scripts\python.exe -m examples.team_integration puzzles\3x3_binary_chain.json --max-steps 1
```

It prints a JSON stop reason, accepted moves, SAT metrics and trace. The separate
`examples.agent_demo` deliberately uses fixtures and opts into immediate
post-reveal consistency checks; it is not a DPLL benchmark.

## 6. Connect GUI actions

Manual verdicts call `controller.submit(cell_id, Status.CRIMINAL)` or
`Status.INNOCENT`. Show the returned message and inspect `Submission.result`.
`NOT_PROVABLE` means both labels remain possible; `CONTRADICTED` means the
opposite is forced. Neither opens a card. `INCONSISTENT` means no public model
exists; `ALREADY_SOLVED` means the card was already proved.

`controller.hint()` returns `(cell_id, classification)` or `None`. A hint can
highlight a cell but does not reveal it. Inspect `.inconsistent` before treating
the returned pair as a valid move. Hint changes Agent counters, not game state
or accepted-move trace. `last_run_status` distinguishes `SOLVED`, `STUCK`,
`INCONSISTENT` and `READY`; `READY` does not promise that another forced cell exists.

Use `controller.auto_step()` to reveal at most one card per UI update.
`auto_solve(max_steps=...)` is convenient for CLI/tests; the limit counts accepted
moves in that call, not SAT queries or elapsed seconds. Stop on `None` or a
terminal run status. Restart resets Engine, trace, statistics, query log and
the invalid-update guard. Load constructs a new Engine and Controller.

Main's web Match already serializes operations with a lock. Preserve that
coordination. If adding background work, do not overlap Controller operations
or restart while a query is running. A timer alone does not make long SAT work
nonblocking. Handle solver/engine exceptions separately from logical rejections.

## 7. Keep validation separate from playing

Only administrative code may call
`engine.all_clues_for_validation()` and
`agent.check_uniqueness(public_metadata, all_clues)`. The latter deliberately
excludes current `proved` and `revealed_clues`, blocks only primary-variable
assignments, and never feeds the complete-clue model into Hint. If initial labels
or global rules are puzzle axioms, explicitly include them in the full validation
constraints. Use a separate Agent or reset counters when measuring gameplay.

## 8. Verify all contracts before merging

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m examples.agent_demo
.\.venv\Scripts\python.exe main.py validate puzzles
```

The full pytest run includes main's function tests/fixtures and the Agent's
unittest classes. `unittest discover` alone does not execute the full production
suite. Preserve existing tests, including the three-call auto-step contract,
expected reveal sequences, public-information isolation, CLI and web API tests.
Do not copy the test oracle into production or overwrite shared types to match a
fixture. Treat `main` as the authority when updating module ownership or imports.
