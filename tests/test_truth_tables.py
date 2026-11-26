"""Bounded property checks against independently evaluated complete truth tables.

Every subset of at most two non-tautological clauses on three variables is
covered, including the empty clause and empty CNF: 379 formulas per mapping.
Two primary/auxiliary mappings give 758 formulas. All nine partial assignments
of two public verdicts produce 6,822 states. Expected labels and uniqueness are
computed directly from all eight assignments, independently of the SAT oracle.
"""
from __future__ import annotations

from itertools import combinations, product
import unittest

from griductive.agent import LogicAgent
from griductive.contracts import CNFFormula
from griductive.models import CellInfo, PublicGameState, Status
from tests.support import EncodedClue, ExhaustiveSolver


CELLS = (CellInfo("A1", "A", "Fixture", 1, 1), CellInfo("B1", "B", "Fixture", 1, 2))
ASSIGNMENTS = tuple(product((False, True), repeat=3))
CLAUSES = tuple(
    tuple((index + 1) * sign for index, sign in enumerate(pattern) if sign)
    for pattern in product((-1, 0, 1), repeat=3)
)
FORMULAS = tuple(formula for count in range(3) for formula in combinations(CLAUSES, count))
MAPPINGS = ({"A1": 1, "B1": 2}, {"A1": 3, "B1": 1})


def truth_models(formula):
    """Evaluate clauses directly; this function never calls a solver."""
    return tuple(
        assignment for assignment in ASSIGNMENTS
        if all(any(assignment[abs(literal) - 1] == (literal > 0) for literal in clause)
               for clause in formula)
    )


def agent_with_mapping(primary):
    auxiliary = {"helper": next(variable for variable in (1, 2, 3) if variable not in primary.values())}

    class Encoder:
        def __init__(self, size, cells):
            pass

        def encode_clues(self, clues):
            clauses = tuple(clause for clue in clues for clause in clue.clauses)
            return CNFFormula(clauses, dict(primary), dict(auxiliary))

        def encode_public_state(self, state):
            return self.encode_clues(state.revealed_clues)

    return LogicAgent(ExhaustiveSolver(), encoder_factory=Encoder)


class TruthTableProperties(unittest.TestCase):
    def test_classification_and_hints_for_every_small_formula_and_public_verdict_subset(self):
        states_checked = cells_checked = 0
        for primary in MAPPINGS:
            for formula in FORMULAS:
                full_models = truth_models(formula)
                agent = agent_with_mapping(primary)
                clue = EncodedClue("truth_table", formula)
                for given in product((None, False, True), repeat=2):
                    context = (primary, formula, given)
                    proved = {cell.id: Status.from_bool(value) for cell, value in zip(CELLS, given)
                              if value is not None}
                    state = PublicGameState("Truth table fixture", 2, CELLS, (clue,), proved)
                    models = tuple(model for model in full_models if all(
                        model[primary[cell.id] - 1] == value
                        for cell, value in zip(CELLS, given) if value is not None
                    ))
                    expected = {}
                    for cell in CELLS:
                        values = {model[primary[cell.id] - 1] for model in models}
                        status = Status.from_bool(next(iter(values))) if len(values) == 1 else None
                        expected[cell.id] = (status, not bool(models))
                        result = agent.classify_cell(state, cell.id)
                        self.assertEqual((result.status, result.inconsistent), expected[cell.id], context)
                        cells_checked += 1

                    unresolved = [cell.id for cell in CELLS if cell.id not in proved]
                    classifications = agent.classify_all(state)
                    self.assertEqual(set(classifications), set(unresolved), context)
                    for cell_id, result in classifications.items():
                        self.assertEqual((result.status, result.inconsistent), expected[cell_id], context)

                    hint = agent.hint(state)
                    if not models:
                        self.assertIsNotNone(hint, context)
                        self.assertEqual(hint[0], unresolved[0] if unresolved else "A1", context)
                        self.assertTrue(hint[1].inconsistent, context)
                    elif not unresolved:
                        self.assertIsNone(hint, context)
                    else:
                        forced = [cell_id for cell_id in unresolved if expected[cell_id][0] is not None]
                        if forced:
                            self.assertIsNotNone(hint, context)
                            self.assertEqual(hint[0], forced[0], context)
                            self.assertEqual(hint[1].status, expected[forced[0]][0], context)
                            self.assertFalse(hint[1].inconsistent, context)
                        else:
                            self.assertIsNone(hint, context)
                    states_checked += 1
        self.assertEqual(states_checked, 6822)
        self.assertEqual(cells_checked, 13644)

    def test_uniqueness_counts_primary_projections_for_every_small_formula(self):
        formulas_checked = 0
        for primary in MAPPINGS:
            for formula in FORMULAS:
                projections = {tuple(model[primary[cell.id] - 1] for cell in CELLS)
                               for model in truth_models(formula)}
                expected = (bool(projections), len(projections) == 1)
                state = PublicGameState("Truth table fixture", 2, CELLS, (), {})
                result = agent_with_mapping(primary).check_uniqueness(
                    state, (EncodedClue("truth_table", formula),))
                self.assertEqual(result, expected, (primary, formula))
                formulas_checked += 1
        self.assertEqual(formulas_checked, 758)


if __name__ == "__main__":
    unittest.main()
