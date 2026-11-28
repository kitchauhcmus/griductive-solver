from dataclasses import replace

import pytest

from griductive.agent import LogicAgent
from griductive.engine import GameController, GameEngine
from griductive.models import Puzzle, Status, VerdictResult


def make_controller():
    return GameController(
        GameEngine.load("puzzles/4x4_easy_training.json")
    )


def test_public_state_does_not_expose_solution_or_hidden_clues():
    state = make_controller().engine.public_state

    assert not hasattr(state, "solution")
    assert len(state.revealed_clues) == 1
    assert set(state.proved) == {"A1"}


def test_manual_submission_distinguishes_not_provable_and_contradicted():
    controller = make_controller()

    unknown = controller.submit(
        "D4",
        Status.CRIMINAL,
    )
    assert unknown.result is VerdictResult.NOT_PROVABLE

    contradicted = controller.submit(
        "B1",
        Status.CRIMINAL,
    )
    assert contradicted.result is VerdictResult.CONTRADICTED
    assert contradicted.forced is Status.INNOCENT

    accepted = controller.submit(
        "B1",
        Status.INNOCENT,
    )
    assert accepted.result is VerdictResult.ACCEPTED
    assert accepted.revealed_clue is not None
    assert "B1" in controller.engine.public_state.proved


def test_agent_detects_inconsistent_public_kb():
    controller = make_controller()
    state = controller.engine.public_state

    inconsistent = replace(
        state,
        proved={
            **state.proved,
            "B1": Status.CRIMINAL,
        },
    )

    result = LogicAgent().classify_cell(
        inconsistent,
        "D3",
    )
    assert result.inconsistent


def test_auto_solver_produces_trace_and_solves():
    controller = make_controller()
    results = controller.auto_solve()

    assert controller.engine.solved
    assert len(results) == 15
    assert len(controller.trace) == 15
    assert all(step.sat_queries for step in controller.trace)


def test_auto_step_reuses_hint_proof_without_classifying_twice():
    controller = GameController(
        GameEngine.load("puzzles/3x3_binary_chain.json")
    )

    result = controller.auto_step()

    assert result is not None
    assert result.result is VerdictResult.ACCEPTED

    # KB, Criminal assumption, Innocent assumption.
    assert controller.agent.stats.sat_calls == 3
    assert len(controller.trace) == 1


def test_missing_clue_leaves_reveal_retryable():
    puzzle = Puzzle.load("puzzles/3x3_binary_chain.json")
    engine = GameEngine(puzzle)
    before = engine.public_state

    clue = puzzle.clues.pop("B1")

    with pytest.raises(KeyError):
        engine.reveal_after_proof(
            "B1",
            Status.CRIMINAL,
        )

    assert engine.public_state == before

    puzzle.clues["B1"] = clue

    assert engine.reveal_after_proof(
        "B1",
        Status.CRIMINAL,
    ) == clue

    assert engine.public_state.proved == {
        **before.proved,
        "B1": Status.CRIMINAL,
    }


def test_repeated_reveal_requires_the_original_verdict():
    engine = GameEngine.load("puzzles/3x3_binary_chain.json")

    clue = engine.reveal_after_proof(
        "B1",
        Status.CRIMINAL,
    )
    after = engine.public_state

    assert engine.reveal_after_proof(
        "B1",
        Status.CRIMINAL,
    ) == clue

    with pytest.raises(ValueError, match="already proved"):
        engine.reveal_after_proof(
            "B1",
            Status.INNOCENT,
        )

    assert engine.public_state == after