"""Proof-gated game flow, kept separate from the engine owner's engine.py."""
from __future__ import annotations

from .agent import Classification, LogicAgent
from .contracts import PublicEngine
from .models import (
    DeductionStep, PublicGameState, RunStatus, Status, Submission, VerdictResult,
)


class GameController:
    def __init__(self, engine: PublicEngine, agent: LogicAgent | None = None):
        self.engine = engine
        self.agent = agent if agent is not None else LogicAgent()
        self.trace: list[DeductionStep] = []
        self.last_run_status = RunStatus.READY
        self._engine_contract_failed = False

    def restart(self) -> None:
        self.engine.restart()
        self.agent.reset_stats()
        self.trace.clear()
        self.last_run_status = RunStatus.READY
        self._engine_contract_failed = False

    def _require_valid_engine(self) -> None:
        if self._engine_contract_failed:
            raise RuntimeError("Engine violated the reveal contract; restart before continuing")

    @staticmethod
    def _validate_cell(state: PublicGameState, cell_id: str) -> None:
        if cell_id not in {cell.id for cell in state.cells}:
            raise ValueError(f"Unknown cell ID: {cell_id!r}")

    @staticmethod
    def _complete(state: PublicGameState) -> bool:
        return all(cell.id in state.proved for cell in state.cells)

    @staticmethod
    def _validate_reveal(state: PublicGameState, updated: PublicGameState,
                         cell_id: str, status: Status, clue) -> None:
        if (updated.title, updated.size, updated.cells) != (state.title, state.size, state.cells):
            raise RuntimeError("Engine changed the board during reveal")
        if updated.proved.get(cell_id) != status:
            raise RuntimeError("Engine did not record the proved verdict")
        if (set(updated.proved) != set(state.proved) | {cell_id}
                or any(updated.proved.get(key) != value for key, value in state.proved.items())):
            raise RuntimeError("Engine must preserve prior verdicts and prove exactly one new card")
        previous = {item.id: item for item in state.revealed_clues}
        published = {item.id: item for item in updated.revealed_clues}
        if (len(previous) != len(state.revealed_clues)
                or len(published) != len(updated.revealed_clues)):
            raise RuntimeError("Engine must use unique revealed clue IDs")
        if clue.id in previous or set(published) != set(previous) | {clue.id}:
            raise RuntimeError("Engine must publish exactly the newly earned clue")
        if any(published[key] != item for key, item in previous.items()):
            raise RuntimeError("Engine must preserve previously revealed clues")
        if published[clue.id] != clue:
            raise RuntimeError("Engine returned a different clue from the one it published")

    def _accept_proved(self, state: PublicGameState, cell_id: str,
                       classification: Classification) -> Submission:
        status = classification.status
        if classification.inconsistent or status is None:
            raise ValueError("Only a consistent, forced verdict can be revealed")
        if self.engine.public_state != state:
            raise RuntimeError("Public state changed after proof; request a new proof")
        clue = self.engine.reveal_after_proof(cell_id, status)
        updated = self.engine.public_state
        try:
            self._validate_reveal(state, updated, cell_id, status, clue)
        except Exception:
            # The engine has already mutated. Do not let a subsequent hint use
            # any unearned clues from that state; only restart can recover it.
            self._engine_contract_failed = True
            raise
        self.trace.append(DeductionStep(
            step=len(self.trace) + 1,
            active_clues=tuple(item.id for item in state.revealed_clues),
            sat_queries=classification.queries,
            cell_id=cell_id,
            verdict=status,
            revealed_clue=clue.id,
        ))
        consistency = self.agent.check_consistency(updated)
        if consistency.inconsistent:
            self.last_run_status = RunStatus.INCONSISTENT
        else:
            self.last_run_status = RunStatus.SOLVED if self._complete(updated) else RunStatus.READY
        return Submission(VerdictResult.ACCEPTED, cell_id, status, status, clue,
                          "Verdict proved; card revealed.")

    def submit(self, cell_id: str, status: Status | str) -> Submission:
        """Verify a manual move without ever consulting hidden labels."""
        self._require_valid_engine()
        status = Status(status)
        state = self.engine.public_state
        self._validate_cell(state, cell_id)
        classification = self.agent.classify_cell(state, cell_id)
        if classification.inconsistent:
            self.last_run_status = RunStatus.INCONSISTENT
            return Submission(VerdictResult.INCONSISTENT, cell_id, status,
                              message="The public knowledge base is inconsistent.")
        self.last_run_status = RunStatus.SOLVED if self._complete(state) else RunStatus.READY
        if cell_id in state.proved:
            return Submission(VerdictResult.ALREADY_SOLVED, cell_id, status,
                              state.proved[cell_id], message="Card is already solved.")
        if classification.status is None:
            return Submission(VerdictResult.NOT_PROVABLE, cell_id, status,
                              message="Neither verdict follows from the public clues.")
        if classification.status != status:
            return Submission(VerdictResult.CONTRADICTED, cell_id, status,
                              classification.status,
                              message="The opposite verdict is logically forced.")
        return self._accept_proved(state, cell_id, classification)

    def _hint(self, state: PublicGameState) -> tuple[str, Classification] | None:
        suggestion = self.agent.hint(state)
        if suggestion is None:
            self.last_run_status = RunStatus.SOLVED if self._complete(state) else RunStatus.STUCK
        elif suggestion[1].inconsistent:
            self.last_run_status = RunStatus.INCONSISTENT
        else:
            self.last_run_status = RunStatus.READY
        return suggestion

    def hint(self) -> tuple[str, Classification] | None:
        """Read-only hint. The GUI may highlight it without opening a card."""
        self._require_valid_engine()
        return self._hint(self.engine.public_state)

    def auto_step(self) -> Submission | None:
        """Prove and reveal one card; fetch the next public KB on the next call."""
        self._require_valid_engine()
        state = self.engine.public_state
        suggestion = self._hint(state)
        if suggestion is None or suggestion[1].inconsistent:
            return None
        cell_id, classification = suggestion
        self._validate_cell(state, cell_id)
        if cell_id in state.proved:
            raise RuntimeError("Agent selected an already proved card")
        return self._accept_proved(state, cell_id, classification)

    def auto_solve(self, max_steps: int | None = None) -> list[Submission]:
        """Stop at SOLVED, STUCK, INCONSISTENT, or an optional accepted-step limit.

        Exceptions from a solver or engine propagate; they are never interpreted
        as SAT, UNSAT, or a proved verdict. The GUI can call auto_step per timer
        tick to remain responsive and stop/restart between steps.
        """
        self._require_valid_engine()
        if max_steps is not None and (type(max_steps) is not int or max_steps < 0):
            raise ValueError("max_steps must be a nonnegative integer or None")
        results: list[Submission] = []
        while True:
            # Observe the terminal state even if the last allowed step solved it.
            state = self.engine.public_state
            if self._complete(state):
                self._hint(state)
                break
            if max_steps is not None and len(results) >= max_steps:
                self.last_run_status = RunStatus.STEP_LIMIT
                break
            result = self.auto_step()
            if result is None:
                break
            results.append(result)
            if self.last_run_status is not RunStatus.READY:
                break
        return results
