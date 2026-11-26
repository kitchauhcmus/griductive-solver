"""Structural contracts, not implementations of the encoder, DPLL, or engine.

Teammates may return their own compatible result dataclasses from cnf.py/dpll.py.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Callable, Iterable, Mapping, Protocol, Sequence

from .models import CellInfo, Clue, PublicGameState, Status


@dataclass(frozen=True)
class CNFFormula:
    clauses: tuple[tuple[int, ...], ...]
    primary_variables: Mapping[str, int]
    auxiliary_variables: Mapping[str, int]

    @property
    def variable_count(self) -> int:
        return max((*self.primary_variables.values(), *self.auxiliary_variables.values()), default=0)

    @property
    def clause_count(self) -> int:
        return len(self.clauses)


@dataclass
class SolverMetrics:
    decisions: int = 0
    propagations: int = 0
    conflicts: int = 0
    backtracks: int = 0
    recursive_calls: int = 0
    runtime_ms: float = 0.0

    def add(self, other: SolverMetrics) -> None:
        for item in fields(self):
            setattr(self, item.name, getattr(self, item.name) + getattr(other, item.name))


@dataclass(frozen=True)
class SATResult:
    satisfiable: bool
    assignment: Mapping[int, bool] | None
    metrics: SolverMetrics


class SATSolver(Protocol):
    def solve(self, clauses: Sequence[Sequence[int]], variable_count: int,
              assumptions: Iterable[int] = ()) -> SATResult: ...


class Encoder(Protocol):
    def encode_public_state(self, state: PublicGameState) -> CNFFormula: ...
    def encode_clues(self, clues: tuple[Clue, ...]) -> CNFFormula: ...


EncoderFactory = Callable[[int, tuple[CellInfo, ...]], Encoder]


class PublicEngine(Protocol):
    """Only the controller receives this capability; LogicAgent receives a snapshot."""
    @property
    def public_state(self) -> PublicGameState: ...
    @property
    def solved(self) -> bool: ...
    def restart(self) -> None: ...
    def reveal_after_proof(self, cell_id: str, status: Status) -> Clue:
        """Atomically validate, record the verdict, and reveal its clue or raise.

        Preserve the board and all earlier public information. Publish exactly
        one new clue with a unique ID; return that same clue. On an error the
        engine must leave public state unchanged. Public clue values must be
        immutable and support equality by content across successive snapshots.
        """
        ...
