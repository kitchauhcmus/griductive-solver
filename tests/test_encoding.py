from itertools import product

import pytest

from griductive.clues import evaluate_clue, validate_clue
from griductive.cnf import CNFEncoder
from griductive.dpll import DPLLSolver
from griductive.models import Clue, PublicGameState, Puzzle, PuzzleValidationError, Status


def tiny_puzzle():
    return Puzzle.from_dict({
        "title": "Encoder fixture", "size": 2,
        "solution": {"A1":"INNOCENT", "B1":"CRIMINAL", "A2":"CRIMINAL", "B2":"INNOCENT"},
        "initially_revealed": ["A1"],
        "clues": {
            "A1":{"type":"FACT", "person":"A1", "status":"INNOCENT"},
            "B1":{"type":"SAME", "person":"A1", "other":"B2"},
            "A2":{"type":"DIFFERENT", "person":"A1", "other":"A2"},
            "B2":{"type":"EXACTLY", "k":2, "region":{"type":"WHOLE_GRID"}}
        }
    })


def satisfies(clauses, assignment, encoder):
    assumptions = tuple(
        number if assignment[cell_id] else -number
        for cell_id, number in encoder.primary.items()
    )
    variable_count = len(encoder.primary) + len(encoder.auxiliary)
    return DPLLSolver().solve(tuple(clauses), variable_count, assumptions).satisfiable


def test_every_required_and_extension_encoder_matches_semantic_oracle():
    puzzle = tiny_puzzle()
    encoder = CNFEncoder(puzzle.size, puzzle.cells)
    ids = tuple(cell.id for cell in puzzle.cells)
    observed_types = set()
    definitions = (
        {"type":"FACT", "person":"A1", "status":"INNOCENT"},
        {"type":"SAME", "person":"A1", "other":"B2"},
        {"type":"DIFFERENT", "person":"A1", "other":"A2"},
        {"type":"EXACTLY", "k":2, "region":{"type":"WHOLE_GRID"}},
        {"type":"AT_LEAST", "k":1, "target_status":"INNOCENT", "region":{"type":"ROW", "row":1}},
        {"type":"AT_MOST", "k":1, "region":{"type":"COLUMN", "column":"A"}},
        {"type":"PARITY", "parity":"EVEN", "region":{"type":"WHOLE_GRID"}},
        {"type":"COUNT_COMPARE", "operator":"EQ", "left":{"type":"ROW", "row":1}, "right":{"type":"ROW", "row":2}},
        {"type":"COUNT_COMPARE", "operator":"NE", "left":{"type":"ROW", "row":1}, "right":{"type":"ROW", "row":2}},
        {"type":"COUNT_COMPARE", "operator":"LT", "left":{"type":"ROW", "row":1}, "right":{"type":"ROW", "row":2}},
        {"type":"COUNT_COMPARE", "operator":"LE", "left":{"type":"ROW", "row":1}, "right":{"type":"ROW", "row":2}},
        {"type":"COUNT_COMPARE", "operator":"GT", "left":{"type":"ROW", "row":1}, "right":{"type":"ROW", "row":2}},
        {"type":"COUNT_COMPARE", "operator":"GE", "left":{"type":"ROW", "row":1}, "right":{"type":"ROW", "row":2}},
        {"type":"INCLUDED_COUNT", "person":"A1", "k":2, "region":{"type":"WHOLE_GRID"}},
        {"type":"OVERLAP_COUNT", "k":2, "overlap_k":1, "region":{"type":"WHOLE_GRID"}, "left":{"type":"ROW", "row":1}},
        {"type":"CONNECTED", "region":{"type":"WHOLE_GRID"}},
        {"type":"CONNECTED_COUNT", "k":2, "region":{"type":"WHOLE_GRID"}},
        {"type":"ALL_OF", "clues":[
            {"type":"FACT", "person":"A1", "status":"INNOCENT"},
            {"type":"DIFFERENT", "person":"A1", "other":"A2"}
        ]},
        {"type":"GROUP_MOST", "group_kind":"ROW", "group":1},
        {"type":"GROUP_ONLY", "group_kind":"COLUMN", "group":"A", "k":1},
    )
    for index, raw in enumerate(definitions):
        clue = Clue.from_dict(raw, f"fixture_{index}")
        validate_clue(clue, puzzle)
        observed_types.add(clue.type)
        clauses = encoder.encode_clue(clue)
        for bits in product((False, True), repeat=len(ids)):
            assignment = dict(zip(ids, bits))
            assert satisfies(clauses, assignment, encoder) == evaluate_clue(clue, assignment, puzzle)
    assert observed_types == {
        "FACT", "SAME", "DIFFERENT", "EXACTLY", "AT_LEAST", "AT_MOST",
        "PARITY", "COUNT_COMPARE", "INCLUDED_COUNT", "OVERLAP_COUNT",
        "CONNECTED", "CONNECTED_COUNT", "ALL_OF", "GROUP_MOST", "GROUP_ONLY",
    }


def test_variable_mapping_is_deterministic_row_major():
    puzzle = tiny_puzzle()
    mapping = CNFEncoder(puzzle.size, puzzle.cells).primary
    assert mapping == {"A1": 1, "B1": 2, "A2": 3, "B2": 4}


def test_boundary_counts_parity_overlapping_comparisons_and_people_match_oracle():
    puzzle = tiny_puzzle()
    ids = tuple(cell.id for cell in puzzle.cells)
    definitions = []
    for status in ("CRIMINAL", "INNOCENT"):
        for kind in ("EXACTLY", "AT_LEAST", "AT_MOST"):
            for k in (0, len(ids)):
                definitions.append({
                    "type": kind, "k": k, "target_status": status,
                    "region": {"type": "WHOLE_GRID"},
                })
        for parity in ("EVEN", "ODD"):
            definitions.append({
                "type": "PARITY", "parity": parity, "target_status": status,
                "region": {"type": "WHOLE_GRID"},
            })
        for op in ("EQ", "NE", "LT", "LE", "GT", "GE"):
            definitions.append({
                "type": "COUNT_COMPARE", "operator": op, "target_status": status,
                "left": {"type": "ROW", "row": 1},
                "right": {"type": "COLUMN", "column": "A"},
            })
    for kind in ("GROUP_MOST", "GROUP_ONLY"):
        definitions.append({
            "type": kind, "group_kind": "PERSON", "group": "A1", "k": 1,
        })

    for index, raw in enumerate(definitions):
        clue = Clue.from_dict(raw, f"boundary_{index}")
        formula = CNFEncoder(puzzle.size, puzzle.cells).encode_clues((clue,))
        for bits in product((False, True), repeat=len(ids)):
            assignment = dict(zip(ids, bits))
            assumptions = tuple(
                number if assignment[cell_id] else -number
                for cell_id, number in formula.primary_variables.items()
            )
            encoded = DPLLSolver().solve(
                formula.clauses, formula.variable_count, assumptions
            ).satisfiable
            assert encoded == evaluate_clue(clue, assignment, puzzle), (clue, assignment)


def test_public_formula_excludes_unrevealed_clues_and_keeps_proved_units():
    puzzle = tiny_puzzle()
    state = PublicGameState(
        puzzle.title, puzzle.size, puzzle.cells, (puzzle.clues["A1"],),
        {"B1": Status.CRIMINAL},
    )
    formula = CNFEncoder(puzzle.size, puzzle.cells).encode_public_state(state)
    assert formula.clauses == ((-1,), (2,))
    assert formula.auxiliary_variables == {}
    assert formula.primary_variables == {"A1": 1, "B1": 2, "A2": 3, "B2": 4}


def test_person_group_compares_every_other_persons_eight_neighbors():
    puzzle = Puzzle.load("puzzles/3x3_binary_chain.json")
    assignment = {cell.id: cell.id != "B2" for cell in puzzle.cells}
    # B2 has 8 criminal neighbors. Corners have 3, edges have at most 5.
    most = Clue.from_dict({
        "type": "GROUP_MOST", "group_kind": "PERSON", "group": "B2",
    }, "center_most")
    only = Clue.from_dict({
        "type": "GROUP_ONLY", "group_kind": "PERSON", "group": "B2", "k": 8,
    }, "center_only")
    for clue in (most, only):
        formula = CNFEncoder(puzzle.size, puzzle.cells).encode_clues((clue,))
        assumptions = tuple(
            variable if assignment[cell_id] else -variable
            for cell_id, variable in formula.primary_variables.items()
        )
        assert evaluate_clue(clue, assignment, puzzle)
        assert DPLLSolver().solve(formula.clauses, formula.variable_count, assumptions).satisfiable


def test_reusing_encoder_does_not_leak_auxiliary_variables_or_counts():
    puzzle = tiny_puzzle()
    encoder = CNFEncoder(puzzle.size, puzzle.cells)
    long_clue = Clue.from_dict({
        "type": "PARITY", "parity": "ODD", "region": {"type": "WHOLE_GRID"}
    }, "odd")
    short_clue = puzzle.clues["A1"]
    encoder.encode_clues((long_clue,))
    actual = encoder.encode_clues((short_clue,))
    expected = CNFEncoder(puzzle.size, puzzle.cells).encode_clues((short_clue,))
    assert actual == expected


def test_encoder_rejects_malformed_clues_and_duplicate_ids():
    puzzle = tiny_puzzle()
    encoder = CNFEncoder(puzzle.size, puzzle.cells)
    missing_overlap = Clue.from_dict({
        "type": "OVERLAP_COUNT", "region": {"type": "WHOLE_GRID"},
        "k": 0, "overlap_k": 0,
    }, "missing_overlap")
    boolean_k = Clue.from_dict({
        "type": "EXACTLY", "region": {"type": "ROW", "row": 1}, "k": True,
    }, "boolean_k")
    boolean_row = Clue.from_dict({
        "type": "EXACTLY", "region": {"type": "ROW", "row": True}, "k": 0,
    }, "boolean_row")
    invalid_column = Clue.from_dict({
        "type": "EXACTLY", "region": {"type": "COLUMN", "column": "AA"}, "k": 0,
    }, "invalid_column")
    for clue in (missing_overlap, boolean_k, boolean_row, invalid_column):
        with pytest.raises(PuzzleValidationError):
            encoder.encode_clues((clue,))
    with pytest.raises(PuzzleValidationError, match="Duplicate clue id"):
        encoder.encode_clues((puzzle.clues["A1"], puzzle.clues["A1"]))


def test_large_parity_and_count_comparisons_remain_polynomial():
    puzzle = Puzzle.load("puzzles/5x5_deep_inference.json")
    parity = Clue.from_dict({
        "type": "PARITY", "parity": "ODD", "region": {"type": "WHOLE_GRID"},
    }, "large_parity")
    compare = Clue.from_dict({
        "type": "COUNT_COMPARE", "operator": "NE",
        "left": {"type": "WHOLE_GRID"}, "right": {"type": "EDGES"},
    }, "large_compare")
    formula = CNFEncoder(puzzle.size, puzzle.cells).encode_clues((parity, compare))
    assert len(formula.auxiliary_variables) < 1500
    assert formula.clause_count < 15000
