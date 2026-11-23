"""Shared public interfaces. The engine owner can extend these with puzzle types.

No hidden labels or unrevealed clues belong in PublicGameState.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Protocol


class Status(str, Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"

    @property
    def boolean(self) -> bool:
        return self is Status.CRIMINAL

    @classmethod
    def from_bool(cls, value: bool) -> Status:
        if type(value) is not bool:
            raise TypeError("A status requires a boolean value")
        return cls.CRIMINAL if value else cls.INNOCENT


class VerdictResult(str, Enum):
    ACCEPTED = "ACCEPTED"
    NOT_PROVABLE = "NOT_PROVABLE"
    CONTRADICTED = "CONTRADICTED"
    INCONSISTENT = "INCONSISTENT"
    ALREADY_SOLVED = "ALREADY_SOLVED"


class RunStatus(str, Enum):
    READY = "READY"
    SOLVED = "SOLVED"
    STUCK = "STUCK"
    INCONSISTENT = "INCONSISTENT"
    STEP_LIMIT = "STEP_LIMIT"


class Clue(Protocol):
    """The encoder owner supplies the concrete clue and region dataclasses."""
    id: str


@dataclass(frozen=True)
class CellInfo:
    id: str
    name: str
    profession: str
    row: int
    column: int


@dataclass(frozen=True)
class PublicGameState:
    title: str
    size: int
    cells: tuple[CellInfo, ...]
    revealed_clues: tuple[Clue, ...]
    proved: Mapping[str, Status]

    def __post_init__(self) -> None:
        object.__setattr__(self, "cells", tuple(self.cells))
        object.__setattr__(self, "revealed_clues", tuple(self.revealed_clues))
        object.__setattr__(self, "proved", MappingProxyType(dict(self.proved)))


@dataclass(frozen=True)
class DeductionStep:
    step: int
    active_clues: tuple[str, ...]
    sat_queries: tuple[str, ...]
    cell_id: str
    verdict: Status
    revealed_clue: str


@dataclass(frozen=True)
class Submission:
    result: VerdictResult
    cell_id: str
    submitted: Status
    forced: Status | None = None
    revealed_clue: Clue | None = None
    message: str = ""
