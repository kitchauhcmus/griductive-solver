from __future__ import annotations

from dataclasses import dataclass, field

from .cnf import CNFEncoder, CNFFormula
from .dpll import DPLLSolver, SolverMetrics
from .models import PublicGameState, Status


@dataclass
class AgentStats:
    sat_calls: int = 0
    solver: SolverMetrics = field(default_factory=SolverMetrics)

    def record(self, metrics: SolverMetrics) -> None:
        self.sat_calls += 1
        self.solver.add(metrics)


@dataclass(frozen=True)
class Classification:
    status: Status | None
    inconsistent: bool = False
    queries: tuple[str, ...] = ()


class LogicAgent:
    """A public-state-only agent. It has no API accepting hidden puzzle labels."""

    def __init__(self, solver: DPLLSolver | None = None):
        self.solver = solver or DPLLSolver()
        self.stats = AgentStats()
        self.last_formula: CNFFormula | None = None

    def reset_stats(self) -> None:
        self.stats = AgentStats()

    def build_kb(self, state: PublicGameState) -> CNFFormula:
        self.last_formula = CNFEncoder(state.size, state.cells).encode_public_state(state)
        return self.last_formula

    def _solve(self, formula: CNFFormula, assumptions=()):
        result = self.solver.solve(formula.clauses, formula.variable_count, assumptions)
        self.stats.record(result.metrics)
        return result

    def _classify_consistent_formula(self, formula: CNFFormula, cell_id: str) -> Classification:
        """Classify one cell after the caller has established that KB is satisfiable."""
        variable = formula.primary_variables[cell_id]
        criminal = self._solve(formula, (variable,))
        innocent = self._solve(formula, (-variable,))
        queries = (
            f"KB & {cell_id}=CRIMINAL: {'SAT' if criminal.satisfiable else 'UNSAT'}",
            f"KB & {cell_id}=INNOCENT: {'SAT' if innocent.satisfiable else 'UNSAT'}",
        )
        if criminal.satisfiable and not innocent.satisfiable:
            return Classification(Status.CRIMINAL, queries=queries)
        if innocent.satisfiable and not criminal.satisfiable:
            return Classification(Status.INNOCENT, queries=queries)
        if not criminal.satisfiable and not innocent.satisfiable:
            return Classification(None, inconsistent=True, queries=queries)
        return Classification(None, queries=queries)

    def classify_cell(self, state: PublicGameState, cell_id: str) -> Classification:
        if cell_id in state.proved:
            return Classification(state.proved[cell_id], queries=("already proved",))
        formula = self.build_kb(state)
        base = self._solve(formula)
        if not base.satisfiable:
            return Classification(None, inconsistent=True, queries=("KB: UNSAT",))
        return self._classify_consistent_formula(formula, cell_id)

    def classify_all(self, state: PublicGameState) -> dict[str, Classification]:
        unresolved = [cell.id for cell in state.cells if cell.id not in state.proved]
        if not unresolved:
            return {}
        formula = self.build_kb(state)
        base = self._solve(formula)
        if not base.satisfiable:
            inconsistent = Classification(None, inconsistent=True, queries=("KB: UNSAT",))
            return {cell_id: inconsistent for cell_id in unresolved}
        return {
            cell_id: self._classify_consistent_formula(formula, cell_id)
            for cell_id in unresolved
        }

    def hint(self, state: PublicGameState) -> tuple[str, Classification] | None:
        unresolved = [cell.id for cell in state.cells if cell.id not in state.proved]
        if not unresolved:
            return None
        formula = self.build_kb(state)
        base = self._solve(formula)
        if not base.satisfiable:
            return unresolved[0], Classification(None, inconsistent=True, queries=("KB: UNSAT",))
        for cell_id in unresolved:
            classification = self._classify_consistent_formula(formula, cell_id)
            if classification.inconsistent or classification.status is not None:
                return cell_id, classification
        return None

    def check_uniqueness(self, state: PublicGameState, all_clues) -> tuple[bool, bool]:
        formula = CNFEncoder(state.size, state.cells).encode_clues(tuple(all_clues))
        first = self._solve(formula)
        if not first.satisfiable or first.assignment is None:
            return False, False
        block = tuple(
            -variable if first.assignment[variable] else variable
            for variable in formula.primary_variables.values()
        )
        second_formula = CNFFormula(
            formula.clauses + (block,), formula.primary_variables, formula.auxiliary_variables
        )
        second = self._solve(second_formula)
        return True, not second.satisfiable
