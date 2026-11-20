from pathlib import Path

from griductive.engine import GameController, GameEngine
from griductive.models import Status


def test_all_puzzles_are_unique_progressive_and_alphabetized():
    paths = sorted(Path("puzzles").glob("*.json"))
    assert [path.name for path in paths] == [
        "3x3_binary_chain.json",
        "3x3_counting_chain.json",
        "4x4_easy_training.json",
        "4x4_medium_links.json",
        "5x5_deep_inference.json",
    ]
    for path in paths:
        controller = GameController(GameEngine.load(path))
        names = [cell.name.casefold() for cell in controller.engine.public_state.cells]
        assert names == sorted(names), path
        satisfiable, unique = controller.agent.check_uniqueness(
            controller.engine.public_state,
            controller.engine.all_clues_for_validation(),
        )
        assert satisfiable and unique, path
        controller.restart()
        controller.auto_solve()
        assert controller.engine.solved, path


def test_three_by_three_cases_have_clear_single_step_paths():
    expected = ["A1", "B1", "C1", "A2", "B2", "C2", "A3", "B3", "C3"]
    for name in ("3x3_binary_chain.json", "3x3_counting_chain.json"):
        controller = GameController(GameEngine.load(Path("puzzles") / name))
        controller.auto_solve()
        assert ["A1"] + [step.cell_id for step in controller.trace] == expected


def test_easy_case_has_a_clear_single_step_learning_path():
    controller = GameController(GameEngine.load("puzzles/4x4_easy_training.json"))
    controller.auto_solve()
    assert ["A1"] + [step.cell_id for step in controller.trace] == [
        "A1", "B1", "C1", "B2", "C2", "B3", "C3", "B4",
        "A2", "A3", "D2", "D3", "A4", "D1", "C4", "D4",
    ]


def test_medium_case_starts_with_original_style_neighbor_reasoning():
    controller = GameController(GameEngine.load("puzzles/4x4_medium_links.json"))
    opening = controller.agent.classify_all(controller.engine.public_state)
    assert opening["A3"].status is Status.INNOCENT
    assert all(opening[cell].status is None for cell in ("D2", "C3", "D3", "C2"))

    controller.submit("A3", Status.INNOCENT)
    overlap = controller.agent.classify_all(controller.engine.public_state)
    assert overlap["D2"].status is Status.INNOCENT
    assert overlap["C3"].status is Status.INNOCENT
    assert overlap["C2"].status is None

    controller.auto_solve()
    assert ["A1"] + [step.cell_id for step in controller.trace] == [
        "A1", "A3", "D2", "C3", "D3", "C2", "A4", "C4",
        "B3", "B1", "B2", "C1", "A2", "D1", "B4", "D4",
    ]


def test_deep_inference_case_preserves_multi_source_reveal_chain():
    controller = GameController(GameEngine.load("puzzles/5x5_deep_inference.json"))
    opening = controller.agent.classify_all(controller.engine.public_state)
    assert opening["A3"].status is Status.INNOCENT
    assert all(opening[cell].status is None for cell in ("D2", "C3", "C4", "B3"))

    controller.auto_solve()
    assert ["A1"] + [step.cell_id for step in controller.trace] == [
        "A1", "A3", "D2", "C3", "C4", "B3", "B1", "E3", "B5",
        "E4", "C2", "E2", "D3", "B2", "C1", "D1", "A2", "E1",
        "A4", "B4", "D4", "A5", "C5", "D5", "E5",
    ]
