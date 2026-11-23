from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from .cnf import Clause


@dataclass
class SolverMetrics:
    decisions: int = 0
    propagations: int = 0
    conflicts: int = 0
    backtracks: int = 0
    recursive_calls: int = 0
    runtime_ms: float = 0.0

    def add(self, other: "SolverMetrics") -> None:
        self.decisions += other.decisions
        self.propagations += other.propagations
        self.conflicts += other.conflicts
        self.backtracks += other.backtracks
        self.recursive_calls += other.recursive_calls
        self.runtime_ms += other.runtime_ms


@dataclass(frozen=True)
class SATResult:
    satisfiable: bool
    assignment: dict[int, bool] | None
    metrics: SolverMetrics


class DPLLSolver:
    def solve(
        self,
        clauses: tuple[Clause, ...] | list[Clause],
        variable_count: int,
        assumptions: tuple[int, ...] | list[int] = (),
    ) -> SATResult:
        started = perf_counter()
        metrics = SolverMetrics()
        working = tuple(tuple(clause) for clause in clauses) + tuple((literal,) for literal in assumptions)
        assignment = self._search(working, {}, variable_count, metrics)
        metrics.runtime_ms = (perf_counter() - started) * 1000
        return SATResult(assignment is not None, assignment, metrics)

    def _search(
        self,
        clauses: tuple[Clause, ...],
        assignment: dict[int, bool],
        variable_count: int,
        metrics: SolverMetrics,
    ) -> dict[int, bool] | None:
        metrics.recursive_calls += 1
        assignment = dict(assignment)
        if not self._unit_propagate(clauses, assignment, metrics):
            return None
        if self._all_satisfied(clauses, assignment):
            for variable in range(1, variable_count + 1):
                assignment.setdefault(variable, False)
            return assignment
        variable = next(v for v in range(1, variable_count + 1) if v not in assignment)
        metrics.decisions += 1
        for value in (False, True):
            branch = dict(assignment)
            branch[variable] = value
            result = self._search(clauses, branch, variable_count, metrics)
            if result is not None:
                return result
            metrics.backtracks += 1
        return None

    def _unit_propagate(
        self,
        clauses: tuple[Clause, ...],
        assignment: dict[int, bool],
        metrics: SolverMetrics,
    ) -> bool:
        changed = True
        while changed:
            changed = False
            for clause in clauses:
                satisfied = False
                undecided: list[int] = []
                for literal in clause:
                    variable = abs(literal)
                    if variable not in assignment:
                        undecided.append(literal)
                    elif assignment[variable] == (literal > 0):
                        satisfied = True
                        break
                if satisfied:
                    continue
                if not undecided:
                    metrics.conflicts += 1
                    return False
                if len(undecided) == 1:
                    literal = undecided[0]
                    variable, value = abs(literal), literal > 0
                    if variable in assignment and assignment[variable] != value:
                        metrics.conflicts += 1
                        return False
                    if variable not in assignment:
                        assignment[variable] = value
                        metrics.propagations += 1
                        changed = True
        return True

    @staticmethod
    def _all_satisfied(clauses: tuple[Clause, ...], assignment: dict[int, bool]) -> bool:
        return all(
            any(abs(lit) in assignment and assignment[abs(lit)] == (lit > 0) for lit in clause)
            for clause in clauses
        )
