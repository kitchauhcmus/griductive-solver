from __future__ import annotations

from .agent import LogicAgent
from .clues import validate_puzzle
from .models import (
    DeductionStep, PublicGameState, Puzzle, Status, Submission, VerdictResult,
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


class GameController:
    def __init__(self, engine: GameEngine, agent: LogicAgent | None = None):
        self.engine = engine
        self.agent = agent or LogicAgent()
        self.trace: list[DeductionStep] = []

    def restart(self) -> None:
        self.engine.restart()
        self.agent.reset_stats()
        self.trace.clear()

    def _accept_proved(self, state: PublicGameState, cell_id: str, status: Status, classification) -> Submission:
        clue = self.engine.reveal_after_proof(cell_id, status)
        self.trace.append(DeductionStep(
            step=len(self.trace) + 1,
            active_clues=tuple(item.id for item in state.revealed_clues),
            sat_queries=classification.queries,
            cell_id=cell_id,
            verdict=status,
            revealed_clue=clue.id,
        ))
        return Submission(
            VerdictResult.ACCEPTED, cell_id, status, status, clue,
            "Verdict proved; card revealed.",
        )

    def submit(self, cell_id: str, status: Status) -> Submission:
        state = self.engine.public_state
        if cell_id in state.proved:
            return Submission(VerdictResult.ALREADY_SOLVED, cell_id, status, state.proved[cell_id], message="Card is already solved.")
        classification = self.agent.classify_cell(state, cell_id)
        if classification.inconsistent:
            return Submission(VerdictResult.INCONSISTENT, cell_id, status, message="The public knowledge base is inconsistent.")
        if classification.status is None:
            return Submission(VerdictResult.NOT_PROVABLE, cell_id, status, message="Neither verdict follows from current public clues.")
        if classification.status is not status:
            return Submission(VerdictResult.CONTRADICTED, cell_id, status, classification.status, message="The opposite verdict is logically forced.")
        return self._accept_proved(state, cell_id, status, classification)

    def hint(self):
        return self.agent.hint(self.engine.public_state)

    def auto_step(self) -> Submission | None:
        state = self.engine.public_state
        hint = self.agent.hint(state)
        if hint is None:
            return None
        cell_id, classification = hint
        if classification.inconsistent or classification.status is None:
            return None
        return self._accept_proved(state, cell_id, classification.status, classification)

    def auto_solve(self) -> list[Submission]:
        results: list[Submission] = []
        while not self.engine.solved:
            result = self.auto_step()
            if result is None or result.result is not VerdictResult.ACCEPTED:
                break
            results.append(result)
        return results
