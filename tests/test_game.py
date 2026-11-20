from dataclasses import replace

from griductive.agent import LogicAgent
from griductive.engine import GameController, GameEngine
from griductive.models import Status, VerdictResult


def make_controller():
    return GameController(GameEngine.load("puzzles/4x4_easy_training.json"))


def test_public_state_does_not_expose_solution_or_hidden_clues():
    state = make_controller().engine.public_state
    assert not hasattr(state, "solution")
    assert len(state.revealed_clues) == 1
    assert set(state.proved) == {"A1"}


def test_manual_submission_distinguishes_not_provable_and_contradicted():
    controller = make_controller()
    unknown = controller.submit("D4", Status.CRIMINAL)
    assert unknown.result is VerdictResult.NOT_PROVABLE
    contradicted = controller.submit("B1", Status.CRIMINAL)
    assert contradicted.result is VerdictResult.CONTRADICTED
    assert contradicted.forced is Status.INNOCENT
    accepted = controller.submit("B1", Status.INNOCENT)
    assert accepted.result is VerdictResult.ACCEPTED
    assert accepted.revealed_clue is not None
    assert "B1" in controller.engine.public_state.proved


def test_agent_detects_inconsistent_public_kb():
    controller = make_controller()
    state = controller.engine.public_state
    inconsistent = replace(state, proved={**state.proved, "B1": Status.CRIMINAL})
    result = LogicAgent().classify_cell(inconsistent, "D3")
    assert result.inconsistent


def test_auto_solver_produces_trace_and_solves():
    controller = make_controller()
    results = controller.auto_solve()
    assert controller.engine.solved
    assert len(results) == 15
    assert len(controller.trace) == 15
    assert all(step.sat_queries for step in controller.trace)


def test_auto_step_reuses_hint_proof_without_classifying_twice():
    controller = GameController(GameEngine.load("puzzles/3x3_binary_chain.json"))
    result = controller.auto_step()
    assert result is not None and result.result is VerdictResult.ACCEPTED
    assert controller.agent.stats.sat_calls == 3  # KB, Criminal assumption, Innocent assumption
    assert len(controller.trace) == 1
