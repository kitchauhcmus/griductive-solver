from itertools import product

from griductive.clues import (
    clue_neighborhood_centers,
    clue_referenced_cells,
    clue_review_cells,
    describe_clue_html,
    evaluate_clue,
    validate_puzzle,
)
from griductive.cnf import CNFEncoder
from griductive.dpll import DPLLSolver
from griductive.engine import GameController, GameEngine
from griductive.models import Puzzle, RegionSpec, Status
from griductive.regions import resolve_region


def test_original_style_clues_match_direct_semantics():
    puzzle = Puzzle.load("puzzles/5x5_deep_inference.json")
    validate_puzzle(puzzle)
    solver = DPLLSolver()
    observed = set()
    for owner in ("A1", "A3", "B3"):
        clue = puzzle.clues[owner]
        observed.add(clue.type)
        referenced = clue_referenced_cells(clue, puzzle)
        encoder = CNFEncoder(puzzle.size, puzzle.cells)
        formula = encoder.encode_clues((clue,))
        base = {cell_id: status.boolean for cell_id, status in puzzle.solution.items()}
        for bits in product((False, True), repeat=len(referenced)):
            assignment = {**base, **dict(zip(referenced, bits))}
            assumptions = tuple(
                variable if assignment[cell_id] else -variable
                for cell_id, variable in formula.primary_variables.items()
            )
            encoded = solver.solve(formula.clauses, formula.variable_count, assumptions).satisfiable
            assert encoded == evaluate_clue(clue, assignment, puzzle)
    assert observed == {"INCLUDED_COUNT", "OVERLAP_COUNT", "CONNECTED_COUNT"}


def test_deep_puzzle_is_unique_and_progressively_solvable():
    controller = GameController(GameEngine.load("puzzles/5x5_deep_inference.json"))
    satisfiable, unique = controller.agent.check_uniqueness(
        controller.engine.public_state, controller.engine.all_clues_for_validation()
    )
    assert satisfiable and unique
    controller.restart()
    controller.auto_solve()
    assert controller.engine.solved


def test_deep_opening_has_exactly_one_forced_cell():
    controller = GameController(GameEngine.load("puzzles/5x5_deep_inference.json"))
    classifications = controller.agent.classify_all(controller.engine.public_state)
    forced = {cell_id for cell_id, result in classifications.items() if result.status is not None}
    assert controller.engine.public_state.revealed_clues[0].type == "INCLUDED_COUNT"
    assert forced == {"A3"}
    assert classifications["A3"].status is Status.INNOCENT


def test_overlap_clue_links_people_and_combines_complete_neighborhoods():
    puzzle = Puzzle.load("puzzles/4x4_medium_links.json")
    clue = puzzle.clues["A3"]

    html = describe_clue_html(clue, puzzle)
    assert '<a href="D3"' in html and ">Rodri</a>" in html
    assert '<a href="C2"' in html and ">Kroos</a>" in html
    assert clue_neighborhood_centers(clue) == ("D3", "C2")

    expected = {"D3", "C2"}
    for center in ("D3", "C2"):
        expected.update(resolve_region(
            RegionSpec(type="NEIGHBORS", center=center), puzzle.cells, puzzle.size
        ))
    assert set(clue_review_cells(clue, puzzle)) == expected
