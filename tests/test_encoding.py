from itertools import product

from griductive.clues import evaluate_clue, validate_clue
from griductive.cnf import CNFEncoder
from griductive.dpll import DPLLSolver
from griductive.models import Clue, Puzzle


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
