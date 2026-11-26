"""Small test doubles, intentionally separate from teammates' production modules.

ExhaustiveSolver enumerates assignments. It is an independent correctness oracle,
not the project's DPLL implementation or an experimental benchmark baseline.
EncodedClue already contains CNF, so FixtureEncoder does not implement clue logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from griductive.agent import LogicAgent
from griductive.contracts import CNFFormula, SATResult, SolverMetrics
from griductive.models import CellInfo, PublicGameState, Status


@dataclass(frozen=True)
class EncodedClue:
    id: str
    clauses: tuple[tuple[int, ...], ...] = ()


@dataclass(frozen=True)
class SolverCall:
    clauses: tuple[tuple[int, ...], ...]
    variable_count: int
    assumptions: tuple[int, ...]


class ExhaustiveSolver:
    """Independent exhaustive SAT oracle, only for small test/demo fixtures."""

    def __init__(self):
        self.calls: list[SolverCall] = []

    def solve(self, clauses, variable_count, assumptions=()):
        clauses = tuple(tuple(clause) for clause in clauses)
        assumptions = tuple(assumptions)
        self.calls.append(SolverCall(clauses, variable_count, assumptions))
        clauses += tuple((literal,) for literal in assumptions)
        # Fix explicit units only to avoid enumerating variables already assigned
        # by the fixture. Remaining assignments are exhaustively enumerated.
        fixed = {}
        for clause in clauses:
            if not clause:
                return SATResult(False, None, SolverMetrics())
            if len(clause) == 1:
                literal = clause[0]
                variable, value = abs(literal), literal > 0
                if variable in fixed and fixed[variable] != value:
                    return SATResult(False, None, SolverMetrics())
                fixed[variable] = value
        free = [variable for variable in range(1, variable_count + 1) if variable not in fixed]
        checked = 0
        for values in product((False, True), repeat=len(free)):
            checked += 1
            model = {**fixed, **dict(zip(free, values))}
            if all(any(model[abs(literal)] == (literal > 0) for literal in clause) for clause in clauses):
                return SATResult(True, model, SolverMetrics(decisions=checked))
        return SATResult(False, None, SolverMetrics(decisions=checked))


class FixtureEncoder:
    """Assemble pre-encoded fixture clauses; proved units are left to the agent."""

    def __init__(self, size, cells, *, auxiliary_count=0):
        self.cells = tuple(cells)
        self.primary = {cell.id: index + 1 for index, cell in enumerate(self.cells)}
        self.auxiliary = {f"aux_{index}": len(cells) + index + 1 for index in range(auxiliary_count)}

    def encode_clues(self, clues):
        return CNFFormula(
            tuple(clause for clue in clues for clause in clue.clauses),
            dict(self.primary), dict(self.auxiliary),
        )

    def encode_public_state(self, state):
        return self.encode_clues(state.revealed_clues)


def make_cells(size=2):
    return tuple(
        CellInfo(f"{chr(65 + column)}{row + 1}", f"Person {row * size + column + 1}",
                 "Test fixture", row + 1, column + 1)
        for row in range(size) for column in range(size)
    )


def make_state(*clauses, size=2, proved=None, cells=None):
    return PublicGameState("Agent test fixture", size, tuple(cells or make_cells(size)),
                           (EncodedClue("public", tuple(clauses)),), proved or {})


def make_agent(*, auxiliary_count=0, solver=None):
    factory = lambda size, cells: FixtureEncoder(size, cells, auxiliary_count=auxiliary_count)
    return LogicAgent(solver=solver if solver is not None else ExhaustiveSolver(), encoder_factory=factory)


class FixtureEngine:
    """Secret-owning stand-in with a strict, observable reveal boundary."""

    def __init__(self, initial_state, *, hidden_clues=None, solution=None):
        self._initial_state = initial_state
        self._hidden_clues = dict(hidden_clues or {})
        self._solution = dict(solution or {})
        self.reveal_calls = []
        self.restart()

    def restart(self):
        self._proved = dict(self._initial_state.proved)
        self._revealed = list(self._initial_state.revealed_clues)
        self.reveal_calls.clear()

    @property
    def public_state(self):
        initial = self._initial_state
        return PublicGameState(initial.title, initial.size, initial.cells,
                               tuple(self._revealed), dict(self._proved))

    @property
    def solved(self):
        return len(self._proved) == len(self._initial_state.cells)

    def reveal_after_proof(self, cell_id, status):
        if cell_id not in self._solution or self._solution[cell_id] is not status:
            raise RuntimeError("Proof conflicts with fixture secret")
        clue = self._hidden_clues.get(cell_id, EncodedClue(f"clue_{cell_id}"))
        self._proved[cell_id] = status
        self._revealed.append(clue)
        self.reveal_calls.append((cell_id, status))
        return clue

    def all_clues_for_validation(self):
        raise AssertionError("A play operation attempted to access complete hidden clues")


def chain_fixture(size=3):
    cells = make_cells(size)
    statuses = {cell.id: Status.CRIMINAL if index % 2 == 0 else Status.INNOCENT
                for index, cell in enumerate(cells)}
    hidden = {}
    for index, cell in enumerate(cells):
        next_index = index + 1
        clauses = ()
        if next_index < len(cells):
            variable = next_index + 1
            literal = variable if statuses[cells[next_index].id].boolean else -variable
            clauses = ((literal,),)
        hidden[cell.id] = EncodedClue(f"clue_{cell.id}", clauses)
    initial = PublicGameState("Synthetic sequential reveal fixture", size, cells,
                              (EncodedClue("initial", ((1,),)),), {})
    return FixtureEngine(initial, hidden_clues=hidden, solution=statuses)
