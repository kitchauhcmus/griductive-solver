# Connect the five team modules

The agent is already executable with the isolated test fixtures. To run a real
puzzle, supply the team's Engine, CNF encoder, and DPLL implementation. The GUI
then calls the controller. All teammates must import the shared `Status` and
`PublicGameState` definitions from `griductive.models`; do not create another
`Status` enum with the same names in a different module.

## 1 Agree on the shared data before combining files

The current `models.Clue` is a typing Protocol requiring an `id`, not a concrete
clue constructor. The clue/CNF teammate should implement a frozen clue dataclass
and a parser, together with the engine teammate. For example, a FACT clue might
have `id`, `type`, `person`, and `status`; the other clue types need their own
fields. Keep their semantics in the encoder, not in the agent. This is why the
agent can support new clue types without changing its deduction algorithm.

`CellInfo(id, name, profession, row, column)` contains only public information.
Use stable unique IDs such as `A1`; do not silently rename them between modules.
`PublicGameState(title, size, cells, revealed_clues, proved)` contains a tuple of
cells, only face-up clues, and proved verdicts. `proved` maps cell IDs to the
shared enum values. It is exposed as a read-only copy. Clue objects must also be
immutable and equal by content across snapshots.

`UNKNOWN` is `Classification.status is None`. It is not a third hidden label:
every character is either criminal or innocent in a solution. `None` means that
the available public knowledge cannot decide. An inconsistent KB also has
`status=None`, so inspect `.inconsistent` first, or display `.label`.

## 2 CNF teammate supplies the encoder

Place the implementation in `griductive/cnf.py` and expose:

```python
class CNFEncoder:
    def __init__(self, size, cells): ...
    def encode_public_state(self, state): ...
    def encode_clues(self, clues): ...
```

Each encoding returns `CNFFormula(clauses, primary_variables,
auxiliary_variables)` from `contracts.py`, or an object with those fields.
This is an interface sketch, not code to paste as a finished encoder.

A concrete formula result looks like:

```python
from griductive.contracts import CNFFormula

formula = CNFFormula(
    clauses=((1,), (-1, 2)),
    primary_variables={"A1": 1, "B1": 2},
    auxiliary_variables={},
)
```

That example expresses `A1` and `A1 implies B1`; the two-cell fragment illustrates
the format rather than defining a complete board. The actual primary mapping
must include every cell on the supplied board, including cells absent from
clauses. Literals are signed nonzero integers. Positive means criminal; negative
means innocent. Primary and auxiliary variable IDs must be positive and unique.
The agent takes `variable_count` as the largest declared variable ID.

`encode_public_state` uses only `revealed_clues` and public `proved` values. The
agent also adds any missing proved unit clauses. Do not encode each unopened
card's clue or consult the hidden solution. `encode_clues` accepts exactly the
clues supplied by its caller; it is also used for the separate uniqueness check.

## 3 DPLL teammate supplies the solver

Place `DPLLSolver` in `griductive/dpll.py` with this call:

```python
result = solver.solve(clauses, variable_count, assumptions=())
```

The result needs `satisfiable` as an actual Python bool, `assignment` as a mapping
from variable ID to bool for SAT or `None` for UNSAT, and `metrics`. Use the
`SATResult` and `SolverMetrics` classes in `contracts.py`, or compatible types.
Metrics must contain `decisions`, `propagations`, `conflicts`, `backtracks`,
`recursive_calls`, and `runtime_ms`.

An assumption `(3,)` temporarily asserts variable 3; `(-3,)` temporarily asserts
its negation. These are different calls, never both assumptions together during
classification. The solver may implement assumptions by adding temporary unit
clauses to its working copy. It must discard them before the next call. The
agent supplies fresh clause lists and snapshots returned results.

SAT must include all declared primary and auxiliary variables, with real bool
values rather than integers 0 and 1. Agent checks that the model satisfies both
the clauses and current assumptions. A timeout or implementation error must
raise an exception; returning `False` would incorrectly claim a proof of UNSAT.
This model validation cannot certify an UNSAT answer, so independent DPLL tests
are still required.

## 4 Engine teammate supplies hidden state and atomic reveal

Place `GameEngine` in `griductive/engine.py`. It owns puzzle loading, the hidden
solution and unopened clues, initial public facts, and restart. Provide:

```python
engine = GameEngine.load(path)
state = engine.public_state
is_finished = engine.solved
engine.restart()
new_clue = engine.reveal_after_proof(cell_id, status)
```

`load` is the convention used by the supplied integration example. If the team
chooses another constructor, change that one line in the example. The controller
itself only requires the engine instance's public interface.

For a successful reveal, keep board metadata and earlier public facts unchanged,
record exactly one new proved cell, and publish exactly one new clue with a unique
ID. Return the same clue content that appears in the new snapshot. If the hidden
label disagrees with the proved verdict, raise before changing state: that means
the puzzle or one of the logic modules is invalid.

Only the controller calls `reveal_after_proof`. The method is an internal
capability and is not itself a proof checker. If a GUI called it directly, it
could bypass the agent's no-guess rule. If the controller detects an invalid
returned reveal state, it raises and refuses further operations until restart. It cannot
roll back a private engine implementation it does not own.

Keep Engine independent of the controller to avoid circular imports. Import
`GameController` from `griductive.controller` in the GUI. A compatibility
re-export from `engine.py` is optional; do not implement a second controller.

## 5 Wire the three components together

```python
from griductive.agent import LogicAgent
from griductive.controller import GameController
from griductive.cnf import CNFEncoder
from griductive.dpll import DPLLSolver
from griductive.engine import GameEngine

engine = GameEngine.load("puzzles/your_puzzle.json")
agent = LogicAgent(solver=DPLLSolver(), encoder_factory=CNFEncoder)
controller = GameController(engine, agent)
```

Dependency injection means the agent receives the solver object and encoder
constructor explicitly. Pass `CNFEncoder`, not `CNFEncoder()`: the agent creates
it using each public state's size and cells. The shorter `LogicAgent()` lazily
imports the same conventional modules. Its constructor succeeding does not mean
those dependencies have been installed; they are used on the first query.

The runnable example is `examples/team_integration.py`. Once the real modules
and a team puzzle exist, run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m examples.team_integration puzzles\your_puzzle.json
.\.venv\Scripts\python.exe -m examples.team_integration puzzles\your_puzzle.json --max-steps 1
```

It prints a JSON stop reason, accepted moves, SAT metrics, and deduction trace.
The current agent-only checkout intentionally reports missing team modules.
It never substitutes the exhaustive test oracle for DPLL.

## 6 GUI teammate calls the controller

For a manual move, call `controller.submit(cell_id, Status.CRIMINAL)` or
`Status.INNOCENT`. Show the returned `Submission.message` and inspect `.result`.
`NOT_PROVABLE` means both labels remain possible; `CONTRADICTED` means the opposite
label is forced. Neither opens a card. `INCONSISTENT` means the current KB has no
model. `ALREADY_SOLVED` means the cell was already proved.

For Hint, call `controller.hint()`. `None` means no suggestion; inspect
`last_run_status` to distinguish completion from being stuck. A returned pair is
`(cell_id, classification)`. If `classification.inconsistent` is true, show the
error rather than highlighting it as a valid move. A normal hint can highlight
the cell but must not flip it. Hint increments SAT statistics because it runs
queries, even though it leaves game state and accepted-move trace unchanged.

For Auto Solve, call `controller.auto_step()` once per GUI timer tick. Redraw
from `engine.public_state` after each call. Stop scheduling ticks when the result
is `None` or when `last_run_status` is `SOLVED`, `STUCK`, or `INCONSISTENT`.
`READY` means the last operation permits more work; it does not guarantee another
forced cell exists. Cancel the timer before Restart or loading another puzzle.
Avoid running long SAT work on the GUI thread; a background worker can run a
single controller operation, with results marshalled back to the UI. Do not call
controller operations concurrently or restart while a worker is still running.

`controller.auto_solve(max_steps=...)` is convenient for command-line runs and
tests. The optional step limit counts accepted moves, not SAT calls or seconds.
Hitting it on a consistent, unfinished board gives `STEP_LIMIT`. Completion or
a contradiction discovered by the last reveal takes precedence. A move can
legitimately return `ACCEPTED` while the new state
is `INCONSISTENT`: its proof was valid before the new clue was opened. The GUI
must inspect both the move result and the resulting run status.

For Restart, call `controller.restart()`, which resets the engine, trace, metrics,
query log, and controller guard. For Load, construct a new engine and controller.
Handle exceptions separately from logical rejection results. In particular,
model errors and engine contract failures are defects, not evidence of UNKNOWN.

## 7 Keep complete-clue validation separate from playing

The engine/data owner may expose a separate administrative method returning all
clues for puzzle validation. Never invoke it from normal Hint or Auto Solve.

```python
validator = LogicAgent(solver=DPLLSolver(), encoder_factory=CNFEncoder)
sat, unique = validator.check_uniqueness(public_metadata, all_clues)
```

Here `public_metadata` supplies title, size, and cells; the method deliberately
excludes its current `proved` and `revealed_clues`. `all_clues` must actually be the
complete set supplied by the data owner. Use a separate validator instance to
keep validation counters apart from gameplay counters. If initial labels or
global rules are puzzle axioms, include them explicitly in the validation clue
set: the agent does not infer missing axioms from the hidden solution.

## 8 Integrate incrementally and keep file ownership clear

1. Agree on shared cell IDs, the `Status` enum, concrete clue dataclasses, and
   result signatures. Engine/CNF teammates own that schema together.
2. The DPLL teammate checks simple SAT/UNSAT and assumptions independently. The
   CNF teammate compares encoded clues with direct semantics independently.
3. Run the existing 64 agent tests; these isolate agent behavior with test
   fixtures and do not automatically validate new production modules.
4. Run the team integration example on actual 3×3 and 4×4 JSON puzzles, including
   unknown, contradicted, and inconsistent cases. Verify the trace and reveals.
5. Connect the GUI after the command-line flow works. Capture team benchmark
   metrics from production DPLL, not from `tests/support.py`.

The agent owner edits `agent.py`, `controller.py`, their tests, and this handoff.
Engine/data edits `engine.py` and `puzzles/`; CNF edits `cnf.py`, `clues.py`, and
`regions.py`; DPLL edits `dpll.py`; GUI/video edits `gui.py` and GUI assets.
Review changes to `models.py` and `contracts.py` together. The examples and
instructions here do not commit or push files to GitHub.
