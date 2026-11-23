"""Deduction from public clues, with no access to the engine's hidden puzzle."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from typing import Any, Callable, Iterable

from .contracts import CNFFormula, SATResult, SolverMetrics
from .models import PublicGameState, Status


@dataclass
class AgentStats:
    sat_calls: int = 0
    solver: SolverMetrics = field(default_factory=SolverMetrics)

    def record(self, metrics: Any) -> None:
        self.sat_calls += 1
        self.solver.add(metrics)


@dataclass(frozen=True)
class Classification:
    status: Status | None
    inconsistent: bool = False
    queries: tuple[str, ...] = ()

    @property
    def label(self) -> str:
        if self.inconsistent:
            return "INCONSISTENT"
        return self.status.value if self.status is not None else "UNKNOWN"


class LogicAgent:
    """Use a teammate's encoder and DPLL solver through narrow interfaces.

    Dependencies can be injected while the other modules are being developed.
    With no injection, their normal ``cnf`` and ``dpll`` modules load on demand.
    An SAT model alone never establishes a verdict: the opposite assumption
    must be UNSAT, after the unmodified knowledge base has passed a SAT check.
    """

    def __init__(self, solver: Any = None, *, encoder_factory: Callable | None = None):
        self.solver = solver
        self.encoder_factory = encoder_factory
        self.stats = AgentStats()
        self.last_formula: CNFFormula | None = None
        self.query_log: list[str] = []

    def reset_stats(self) -> None:
        self.stats = AgentStats()
        self.last_formula = None
        self.query_log.clear()

    def _encoder(self, state: PublicGameState):
        factory = self.encoder_factory
        if factory is None:
            try:
                from .cnf import CNFEncoder
            except ImportError as exc:
                raise ImportError(
                    "CNFEncoder is unavailable. Add griductive/cnf.py or inject "
                    "encoder_factory=CNFEncoder into LogicAgent."
                ) from exc
            factory = CNFEncoder
        return factory(state.size, tuple(state.cells))

    @staticmethod
    def _cell_ids(state: PublicGameState) -> set[str]:
        ids = [cell.id for cell in state.cells]
        if not ids:
            raise ValueError("Public state must contain at least one cell.")
        if len(ids) != len(set(ids)):
            raise ValueError("Public state contains duplicate cell IDs.")
        if not set(state.proved).issubset(ids):
            raise ValueError("Public verdict refers to an unknown cell.")
        for status in state.proved.values():
            if not isinstance(status, Status):
                raise ValueError("Public verdicts must use Status values.")
        return set(ids)

    @classmethod
    def _checked_formula(cls, formula: Any, state: PublicGameState) -> CNFFormula:
        primary = dict(formula.primary_variables)
        auxiliary = dict(formula.auxiliary_variables)
        if set(primary) != cls._cell_ids(state):
            raise ValueError("CNF primary variables must map every public cell exactly once.")
        variables = [*primary.values(), *auxiliary.values()]
        if any(type(variable) is not int or variable <= 0 for variable in variables):
            raise ValueError("CNF variables must be positive integers.")
        if len(variables) != len(set(variables)):
            raise ValueError("Primary and auxiliary variables must have distinct IDs.")
        clauses = tuple(tuple(clause) for clause in formula.clauses)
        for clause in clauses:
            if any(type(literal) is not int or abs(literal) not in variables for literal in clause):
                raise ValueError("CNF literal is zero or refers to an undeclared variable.")
        return CNFFormula(clauses, primary, auxiliary)

    def build_kb(self, state: PublicGameState) -> CNFFormula:
        """Encode only revealed clues, then enforce every public proved verdict."""
        self._cell_ids(state)
        # Copy the public container so encoder mutation cannot change the caller's state.
        snapshot = PublicGameState(
            state.title, state.size, tuple(state.cells), tuple(state.revealed_clues),
            dict(state.proved),
        )
        formula = self._checked_formula(self._encoder(snapshot).encode_public_state(snapshot), snapshot)
        clauses = list(formula.clauses)
        present = set(clauses)
        for cell_id, status in snapshot.proved.items():
            variable = formula.primary_variables[cell_id]
            clause = (variable if status is Status.CRIMINAL else -variable,)
            if clause not in present:
                clauses.append(clause)
                present.add(clause)
        self.last_formula = CNFFormula(tuple(clauses), formula.primary_variables, formula.auxiliary_variables)
        return self.last_formula

    def _solve(self, formula: CNFFormula, assumptions=(), *, purpose: str = "KB"):
        if self.solver is None:
            try:
                from .dpll import DPLLSolver
            except ImportError as exc:
                raise ImportError(
                    "DPLLSolver is unavailable. Add griductive/dpll.py or inject "
                    "solver=DPLLSolver() into LogicAgent."
                ) from exc
            self.solver = DPLLSolver()
        # Fresh lists protect the saved formula even if a solver works in place.
        assumptions = tuple(assumptions)
        result = self.solver.solve(
            [list(clause) for clause in formula.clauses], formula.variable_count,
            assumptions,
        )
        if type(result.satisfiable) is not bool:
            raise ValueError("Solver must return a boolean satisfiable result.")
        assignment = None
        if result.satisfiable:
            if not isinstance(result.assignment, Mapping):
                raise ValueError("SAT requires a complete boolean assignment mapping.")
            assignment = dict(result.assignment)
            variables = (*formula.primary_variables.values(), *formula.auxiliary_variables.values())
            if any(variable not in assignment or type(assignment[variable]) is not bool
                   for variable in variables):
                raise ValueError("SAT requires a complete boolean model for primary and auxiliary variables.")
            if not all(any(assignment[abs(literal)] == (literal > 0) for literal in clause)
                       for clause in formula.clauses):
                raise ValueError("SAT assignment does not satisfy the knowledge base.")
            if any(assignment.get(abs(literal)) != (literal > 0) for literal in assumptions):
                raise ValueError("SAT assignment does not satisfy the query assumptions.")
        elif result.assignment is not None:
            raise ValueError("UNSAT must return no assignment.")
        # A solver may reuse mutable result/model/metric objects on its next call.
        metrics = SolverMetrics(**{item.name: getattr(result.metrics, item.name)
                                   for item in fields(SolverMetrics)})
        result = SATResult(result.satisfiable, assignment, metrics)
        self.stats.record(result.metrics)
        query = f"{purpose}: {'SAT' if result.satisfiable else 'UNSAT'}"
        self.query_log.append(query)
        return result, query

    def _classify(self, formula: CNFFormula, cell_id: str) -> Classification:
        variable = formula.primary_variables[cell_id]
        criminal, criminal_query = self._solve(
            formula, (variable,), purpose=f"KB & {cell_id}=CRIMINAL"
        )
        innocent, innocent_query = self._solve(
            formula, (-variable,), purpose=f"KB & {cell_id}=INNOCENT"
        )
        queries = (criminal_query, innocent_query)
        if criminal.satisfiable and not innocent.satisfiable:
            return Classification(Status.CRIMINAL, queries=queries)
        if innocent.satisfiable and not criminal.satisfiable:
            return Classification(Status.INNOCENT, queries=queries)
        return Classification(None, inconsistent=not criminal.satisfiable, queries=queries)

    def classify_cell(self, state: PublicGameState, cell_id: str) -> Classification:
        if cell_id not in self._cell_ids(state):
            raise ValueError(f"Unknown cell ID: {cell_id}")
        formula = self.build_kb(state)
        base, base_query = self._solve(formula)
        if not base.satisfiable:
            return Classification(None, inconsistent=True, queries=(base_query,))
        if cell_id in state.proved:
            return Classification(state.proved[cell_id], queries=(base_query, "already proved"))
        result = self._classify(formula, cell_id)
        return Classification(result.status, result.inconsistent, (base_query,) + result.queries)

    def check_consistency(self, state: PublicGameState) -> Classification:
        """Check the public KB without choosing a cell or revealing a card."""
        base, query = self._solve(self.build_kb(state))
        return Classification(None, inconsistent=not base.satisfiable, queries=(query,))

    @staticmethod
    def _unresolved(state: PublicGameState):
        return [
            cell.id for cell in sorted(state.cells, key=lambda cell: (cell.row, cell.column, cell.id))
            if cell.id not in state.proved
        ]

    def classify_all(self, state: PublicGameState) -> dict[str, Classification]:
        formula = self.build_kb(state)
        base, base_query = self._solve(formula)
        unresolved = self._unresolved(state)
        if not base.satisfiable:
            return {cell_id: Classification(None, True, (base_query,)) for cell_id in unresolved}
        classifications = {}
        for cell_id in unresolved:
            result = self._classify(formula, cell_id)
            classifications[cell_id] = Classification(
                result.status, result.inconsistent, (base_query,) + result.queries
            )
        return classifications

    def hint(self, state: PublicGameState) -> tuple[str, Classification] | None:
        formula = self.build_kb(state)
        base, base_query = self._solve(formula)
        unresolved = self._unresolved(state)
        if not base.satisfiable:
            cell_id = unresolved[0] if unresolved else min(
                state.cells, key=lambda cell: (cell.row, cell.column, cell.id)
            ).id
            return cell_id, Classification(None, True, (base_query,))
        if not unresolved:
            return None
        queries = [base_query]
        for cell_id in unresolved:
            result = self._classify(formula, cell_id)
            queries.extend(result.queries)
            if result.status is not None or result.inconsistent:
                return cell_id, Classification(result.status, result.inconsistent, tuple(queries))
        return None

    def check_uniqueness(self, state: PublicGameState, all_clues: Iterable[Any]) -> tuple[bool, bool]:
        """Validate the complete clue set, independently of current play knowledge.

        Return ``(False, False)`` for no solutions, ``(True, True)`` for one,
        and ``(True, False)`` for multiple primary-variable assignments.
        Auxiliary-variable assignments never count as distinct puzzle solutions.
        """
        # The public proved/revealed values are deliberately excluded from encoding.
        clean = PublicGameState(state.title, state.size, tuple(state.cells), (), {})
        formula = self._checked_formula(self._encoder(clean).encode_clues(tuple(all_clues)), clean)
        first, _ = self._solve(formula, purpose="ALL_CLUES")
        if not first.satisfiable:
            return False, False
        assignment = first.assignment
        variables = tuple(formula.primary_variables.values())
        block = tuple(-variable if assignment[variable] else variable for variable in variables)
        blocked = CNFFormula(
            formula.clauses + (block,), dict(formula.primary_variables), dict(formula.auxiliary_variables)
        )
        second, _ = self._solve(blocked, purpose="ALL_CLUES & BLOCK_PRIMARY_MODEL")
        return True, not second.satisfiable
