from __future__ import annotations

from .controller import GameController  # Preserve main's public import path.
from .clues import validate_puzzle
from .models import (
    PublicGameState, Puzzle, Status,
)


class GameEngine:
    """Owns secrets. It exposes only sanitized PublicGameState objects."""

    def __init__(self, puzzle: Puzzle, *, inconsistent_demo: bool = False):
        validate_puzzle(puzzle, check_truth=not inconsistent_demo)
        self._puzzle = puzzle
        self._revealed: set[str] = set()
        self._proved: dict[str, Status] = {}
        self.restart()

    @classmethod
    def load(cls, path) -> "GameEngine":
        return cls(Puzzle.load(path))

    def restart(self) -> None:
        self._revealed = set(self._puzzle.initially_revealed)
        self._proved = {
            cell_id: self._puzzle.solution[cell_id]
            for cell_id in self._puzzle.initially_revealed
        }

    @property
    def public_state(self) -> PublicGameState:
        clues = tuple(
            self._puzzle.clues[cell.id]
            for cell in self._puzzle.cells if cell.id in self._revealed
        )
        return PublicGameState(
            title=self._puzzle.title,
            size=self._puzzle.size,
            cells=self._puzzle.cells,
            revealed_clues=clues,
            proved=dict(self._proved),
        )

    @property
    def solved(self) -> bool:
        return len(self._proved) == len(self._puzzle.cells)

    def reveal_after_proof(self, cell_id: str, status: Status):
        if cell_id in self._proved:
            return self._puzzle.clues[cell_id]
        if self._puzzle.solution[cell_id] is not status:
            raise RuntimeError("Proof/solution mismatch: puzzle or logic implementation is invalid")
        self._proved[cell_id] = status
        self._revealed.add(cell_id)
        return self._puzzle.clues[cell_id]

    def all_clues_for_validation(self):
        """Administrative API; never pass this result to hint/classification code."""
        return tuple(self._puzzle.clues[cell.id] for cell in self._puzzle.cells)
