from dataclasses import replace

from griductive.agent import LogicAgent
from griductive.engine import GameController, GameEngine
from griductive.models import Puzzle
from griductive.web.game import PUZZLES


def test_hint_and_classification_need_only_public_information():
    puzzle = Puzzle.load(PUZZLES / "3x3_binary_chain.json")
    controller = GameController(GameEngine(puzzle))
    state = controller.engine.public_state
    expected = LogicAgent().classify_all(state)
    # Every access to secret clue B1 or any hidden label now fails immediately.
    puzzle.clues = {owner: puzzle.clues[owner] for owner in puzzle.initially_revealed}
    puzzle.solution = {}
    assert controller.hint()[0] == "B1"
    assert controller.agent.classify_all(controller.engine.public_state) == expected
    # Art metadata never participates in the proof.
    new_cells = tuple(replace(c, ovr=1, tier="", nation="", slug="") for c in state.cells)
    assert LogicAgent().classify_all(replace(state, cells=new_cells)) == expected
