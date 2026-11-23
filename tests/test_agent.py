from __future__ import annotations

import unittest

from griductive.contracts import SATResult, SolverMetrics
from griductive.models import PublicGameState, Status
from tests.support import EncodedClue, ExhaustiveSolver, FixtureEncoder, make_agent, make_cells, make_state


class ClassificationTests(unittest.TestCase):
    def test_forced_criminal_innocent_and_unknown(self):
        agent = make_agent()
        results = agent.classify_all(make_state((1,), (-2,)))
        self.assertIs(results["A1"].status, Status.CRIMINAL)
        self.assertIs(results["B1"].status, Status.INNOCENT)
        self.assertEqual(results["A2"].label, "UNKNOWN")
        self.assertFalse(results["A2"].inconsistent)
        self.assertEqual(agent.stats.sat_calls, 1 + 2 * 4)

    def test_entailment_requires_opposite_unsat_not_one_sat_model(self):
        agent = make_agent()
        # A1 or B1 has models with either value of A1; one model cannot prove A1.
        classification = agent.classify_cell(make_state((1, 2)), "A1")
        self.assertIsNone(classification.status)
        self.assertEqual(agent.stats.sat_calls, 3)
        self.assertTrue(all(query.endswith("SAT") for query in classification.queries))

    def test_inconsistent_kb_stops_before_assumptions(self):
        agent = make_agent()
        classification = agent.classify_cell(make_state((1,), (-1,)), "B1")
        self.assertTrue(classification.inconsistent)
        self.assertIsNone(classification.status)
        self.assertEqual(agent.stats.sat_calls, 1)
        self.assertEqual(agent.solver.calls[0].assumptions, ())

    def test_proved_cell_still_checks_consistency(self):
        classification = make_agent().classify_cell(
            make_state((-1,), proved={"A1": Status.CRIMINAL}), "A1")
        self.assertTrue(classification.inconsistent)

    def test_public_verdicts_become_unit_clauses(self):
        agent = make_agent()
        state = make_state((-1, 2), proved={"A1": Status.CRIMINAL})
        self.assertIs(agent.classify_cell(state, "B1").status, Status.CRIMINAL)
        self.assertIn((1,), agent.last_formula.clauses)

    def test_classify_all_excludes_proved_cells(self):
        results = make_agent().classify_all(make_state(proved={"A1": Status.CRIMINAL}))
        self.assertEqual(set(results), {"B1", "A2", "B2"})

    def test_invalid_cell_is_rejected_before_solver(self):
        agent = make_agent()
        with self.assertRaises(ValueError):
            agent.classify_cell(make_state(), "Z99")
        self.assertEqual(agent.stats.sat_calls, 0)

    def test_assumptions_are_isolated_between_queries(self):
        agent = make_agent()
        state = make_state()
        self.assertIsNone(agent.classify_cell(state, "A1").status)
        self.assertIsNone(agent.classify_cell(state, "A1").status)
        self.assertEqual([call.assumptions for call in agent.solver.calls],
                         [(), (1,), (-1,), (), (1,), (-1,)])

    def test_public_snapshot_and_cnf_are_not_mutated(self):
        agent = make_agent()
        proved = {"A1": Status.CRIMINAL}
        state = make_state((-1, 2), proved=proved)
        initial_clues = state.revealed_clues
        proved["A1"] = Status.INNOCENT
        self.assertIs(state.proved["A1"], Status.CRIMINAL)
        agent.classify_all(state)
        self.assertEqual(state.revealed_clues, initial_clues)
        self.assertEqual(dict(state.proved), {"A1": Status.CRIMINAL})
        with self.assertRaises(TypeError):
            state.proved["B1"] = Status.CRIMINAL

    def test_solver_in_place_work_cannot_corrupt_saved_formula(self):
        class MutatingSolver(ExhaustiveSolver):
            def solve(self, clauses, variable_count, assumptions=()):
                result = super().solve(clauses, variable_count, assumptions)
                clauses.clear()
                return result
        agent = make_agent(solver=MutatingSolver())
        self.assertIs(agent.classify_cell(make_state((1,)), "A1").status, Status.CRIMINAL)
        self.assertEqual(agent.last_formula.clauses, ((1,),))

    def test_hint_order_is_row_column_then_id(self):
        cells = tuple(reversed(make_cells()))
        # Fixture variable 4 is A1 because the cell tuple is reversed.
        hint = make_agent().hint(make_state((4,), (3,), cells=cells))
        self.assertEqual(hint[0], "A1")

    def test_hint_returns_none_if_no_forced_verdict(self):
        self.assertIsNone(make_agent().hint(make_state((1, 2))))

    def test_reset_clears_counts_formula_and_queries(self):
        agent = make_agent()
        agent.classify_cell(make_state((1,)), "A1")
        self.assertGreater(agent.stats.sat_calls, 0)
        agent.reset_stats()
        self.assertEqual(agent.stats.sat_calls, 0)
        self.assertEqual(agent.stats.solver, SolverMetrics())
        self.assertIsNone(agent.last_formula)
        self.assertEqual(agent.query_log, [])

    def test_every_solver_counter_is_aggregated_per_sat_call(self):
        class MeteredSolver(ExhaustiveSolver):
            def solve(self, *args):
                result = super().solve(*args)
                return SATResult(result.satisfiable, result.assignment,
                                 SolverMetrics(1, 2, 3, 4, 5, 0.25))
        agent = make_agent(solver=MeteredSolver())
        agent.classify_cell(make_state((1,)), "A1")
        self.assertEqual(agent.stats.sat_calls, 3)
        self.assertEqual(agent.stats.solver, SolverMetrics(3, 6, 9, 12, 15, 0.75))

    def test_invalid_primary_mapping_is_rejected(self):
        class BadEncoder(FixtureEncoder):
            def encode_public_state(self, state):
                formula = super().encode_public_state(state)
                formula.primary_variables.pop("A1")
                return formula
        agent = make_agent()
        agent.encoder_factory = BadEncoder
        with self.assertRaises(ValueError):
            agent.classify_cell(make_state(), "A1")


class UniquenessTests(unittest.TestCase):
    def test_zero_one_and_multiple_primary_solutions(self):
        state = make_state()
        fixtures = (
            (((1,), (-1,)), (False, False)),
            (((1,), (-2,), (3,), (-4,)), (True, True)),
            (((1,),), (True, False)),
        )
        for clauses, expected in fixtures:
            with self.subTest(expected=expected):
                self.assertEqual(make_agent().check_uniqueness(state, (EncodedClue("complete", clauses),)), expected)

    def test_auxiliary_assignments_do_not_count_as_extra_puzzle_solutions(self):
        agent = make_agent(auxiliary_count=1)
        result = agent.check_uniqueness(make_state(),
                                        (EncodedClue("complete", ((1,), (-2,), (3,), (-4,))),))
        self.assertEqual(result, (True, True))
        blocking_clause = agent.solver.calls[-1].clauses[-1]
        self.assertEqual({abs(literal) for literal in blocking_clause}, {1, 2, 3, 4})
        self.assertNotIn(5, {abs(literal) for literal in blocking_clause})

    def test_complete_clue_check_excludes_current_reveals_and_proved_verdicts(self):
        state = make_state((-1,), proved={"A1": Status.INNOCENT})
        agent = make_agent()
        full = (EncodedClue("complete", ((1,), (-2,), (3,), (-4,))),)
        self.assertEqual(agent.check_uniqueness(state, full), (True, True))
        self.assertNotIn((-1,), agent.solver.calls[0].clauses)

    def test_unique_complete_clues_can_still_be_stuck_in_play(self):
        state = make_state()
        agent = make_agent()
        full = (EncodedClue("complete", ((1,), (-2,), (3,), (-4,))),)
        self.assertEqual(agent.check_uniqueness(state, full), (True, True))
        self.assertIsNone(agent.hint(state))

    def test_partial_sat_model_is_rejected(self):
        class PartialSolver(ExhaustiveSolver):
            def solve(self, *args):
                result = super().solve(*args)
                return SATResult(result.satisfiable, {1: True}, result.metrics)
        with self.assertRaises(ValueError):
            make_agent(solver=PartialSolver()).check_uniqueness(make_state(), ())

    def test_uniqueness_does_not_replace_play_knowledge_base(self):
        agent = make_agent()
        state = make_state((1,))
        playing_formula = agent.build_kb(state)
        agent.check_uniqueness(state, (EncodedClue("complete", ((-1,),)),))
        self.assertEqual(agent.last_formula, playing_formula)
        self.assertIs(agent.classify_cell(state, "A1").status, Status.CRIMINAL)


if __name__ == "__main__":
    unittest.main()
