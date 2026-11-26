"""Integration checks against main's real public imports, models, CNF and DPLL."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import unittest

import griductive
from griductive.agent import LogicAgent
from griductive.cnf import CNFEncoder
from griductive.controller import GameController
from griductive.dpll import DPLLSolver
from griductive.engine import GameController as EngineController, GameEngine
from griductive.models import Clue, PublicGameState, Puzzle, RegionSpec, Status, VerdictResult


ROOT = Path(__file__).resolve().parents[1]
CHAIN = ROOT / "puzzles" / "3x3_binary_chain.json"


class MainContractTests(unittest.TestCase):
    def test_existing_controller_import_paths_reach_one_implementation(self):
        self.assertIs(griductive.GameController, EngineController)
        self.assertIs(EngineController, GameController)
        self.assertIs(griductive.GameEngine, GameEngine)
        self.assertIs(griductive.LogicAgent, LogicAgent)

    def test_default_real_auto_step_preserves_main_three_query_contract(self):
        controller = EngineController(GameEngine.load(CHAIN))
        before = controller.engine.public_state
        result = controller.auto_step()
        self.assertIs(result.result, VerdictResult.ACCEPTED)
        self.assertEqual(result.cell_id, "B1")
        self.assertIs(result.forced, Status.CRIMINAL)
        self.assertEqual(controller.agent.stats.sat_calls, 3)
        self.assertEqual(len(controller.trace), 1)
        self.assertEqual(len(controller.engine.public_state.proved), len(before.proved) + 1)
        self.assertEqual(controller.trace[0].active_clues,
                         tuple(clue.id for clue in before.revealed_clues))
        self.assertNotIn(result.revealed_clue.id, controller.trace[0].active_clues)

    def test_strict_reveal_option_checks_new_real_kb_with_one_extra_query(self):
        controller = EngineController(GameEngine.load(CHAIN), check_revealed_consistency=True)
        result = controller.auto_step()
        self.assertIs(result.result, VerdictResult.ACCEPTED)
        self.assertEqual(controller.agent.stats.sat_calls, 4)
        self.assertEqual(controller.agent.query_log[-1], "KB: SAT")

    def test_main_puzzle_and_player_metadata_remain_serializable(self):
        puzzle = Puzzle.load(CHAIN)
        self.assertEqual(len(puzzle.cells), 9)
        first = puzzle.cells[0]
        self.assertTrue(first.slug)
        self.assertIsInstance(first.ovr, int)
        self.assertTrue(first.club)
        self.assertTrue(first.nation)
        self.assertTrue(first.tier)
        self.assertIsInstance(first.shirt_number, int)
        state = GameEngine(puzzle).public_state
        serialized = json.loads(json.dumps(asdict(state)))
        self.assertEqual(serialized["cells"][0]["slug"], first.slug)
        self.assertEqual(serialized["proved"], {"A1": "INNOCENT"})
        self.assertFalse(hasattr(state, "solution"))
        self.assertFalse(hasattr(state, "clues"))
        self.assertFalse(hasattr(state, "_puzzle"))

    def test_main_structured_clue_and_region_parsers_are_available(self):
        clue = Clue.from_dict({
            "type": "all_of",
            "clues": [
                {"type": "fact", "person": "A1", "status": "innocent"},
                {"type": "exactly", "k": 1,
                 "region": {"type": "row", "index": 1}},
            ],
        }, "contract_clue")
        self.assertEqual(clue.type, "ALL_OF")
        self.assertIs(clue.children[0].status, Status.INNOCENT)
        self.assertEqual(clue.children[1].region, RegionSpec(type="ROW", row=1, column=1))
        self.assertEqual(len(clue.children), 2)

    def test_real_counting_cnf_and_dpll_uniqueness_use_primary_labels_only(self):
        puzzle = Puzzle.from_dict({
            "title": "Main contract cardinality fixture", "size": 2,
            "solution": {"A1": "CRIMINAL", "B1": "INNOCENT",
                         "A2": "CRIMINAL", "B2": "INNOCENT"},
            "initially_revealed": ["A1"],
            "clues": {
                "A1": {"type": "FACT", "person": "A1", "status": "CRIMINAL"},
                "B1": {"type": "FACT", "person": "B1", "status": "INNOCENT"},
                "A2": {"type": "FACT", "person": "A2", "status": "CRIMINAL"},
                "B2": {"type": "EXACTLY", "k": 2, "region": {"type": "WHOLE_GRID"}},
            },
        })
        clues = tuple(puzzle.clues.values())
        formula = CNFEncoder(puzzle.size, puzzle.cells).encode_clues(clues)
        self.assertTrue(formula.auxiliary_variables)
        state = PublicGameState(puzzle.title, puzzle.size, puzzle.cells, (), {})
        agent = LogicAgent(solver=DPLLSolver(), encoder_factory=CNFEncoder)
        self.assertEqual(agent.check_uniqueness(state, clues), (True, True))
        self.assertEqual(agent.check_uniqueness(state, clues[-1:]), (True, False))
        contradiction = Clue.from_dict({"type": "FACT", "person": "A1", "status": "INNOCENT"},
                                       "contradictory_fact")
        self.assertEqual(agent.check_uniqueness(state, clues + (contradiction,)), (False, False))

    def test_public_deductions_do_not_need_secret_labels_or_player_art(self):
        engine = GameEngine.load(CHAIN)
        state = engine.public_state
        agent = LogicAgent()
        expected = agent.classify_all(state)
        # The canonical engine keeps secrets. A public deduction must still work
        # after every hidden label and all unrevealed clues become unavailable.
        puzzle = engine._puzzle
        puzzle.solution = {}
        puzzle.clues = {cell: puzzle.clues[cell] for cell in puzzle.initially_revealed}
        self.assertEqual(agent.classify_all(engine.public_state), expected)
        new_cells = tuple(replace(cell, slug="", ovr=1, club="", nation="", tier="",
                                  shirt_number=None) for cell in state.cells)
        self.assertEqual(agent.classify_all(replace(state, cells=new_cells)), expected)


if __name__ == "__main__":
    unittest.main()
