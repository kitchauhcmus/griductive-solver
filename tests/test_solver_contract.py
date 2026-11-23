"""Regression cases for invalid solver outputs and terminal public states."""
from __future__ import annotations

from types import SimpleNamespace
import unittest

from griductive.contracts import SATResult, SolverMetrics
from griductive.models import PublicGameState, Status
from tests.support import EncodedClue, ExhaustiveSolver, make_agent, make_cells, make_state


class SolverContractTests(unittest.TestCase):
    def test_wrong_complete_model_cannot_change_uniqueness_result(self):
        class WrongModelSolver(ExhaustiveSolver):
            def solve(self, *args):
                result = super().solve(*args)
                model = dict(result.assignment)
                model[1] = not model[1]
                return SATResult(True, model, result.metrics)

        full = (EncodedClue("complete", ((1,), (-2,), (3,), (-4,))),)
        self.assertEqual(make_agent().check_uniqueness(make_state(), full), (True, True))
        with self.assertRaisesRegex(ValueError, "knowledge base"):
            make_agent(solver=WrongModelSolver()).check_uniqueness(make_state(), full)

    def test_sat_requires_complete_boolean_primary_and_auxiliary_models(self):
        invalid_models = (None, {1: True}, {1: True, 2: False, 3: True, 4: False},
                          {1: 1, 2: False, 3: True, 4: False, 5: True})
        for model in invalid_models:
            with self.subTest(model=model):
                solver = SimpleNamespace(solve=lambda *args: SATResult(True, model, SolverMetrics()))
                with self.assertRaisesRegex(ValueError, "boolean"):
                    make_agent(solver=solver, auxiliary_count=1).check_consistency(make_state())

    def test_a_satisfying_model_must_also_satisfy_the_query_assumptions(self):
        class IgnoringAssumptionsSolver(ExhaustiveSolver):
            def solve(self, clauses, count, assumptions=()):
                return super().solve(clauses, count)

        agent = make_agent(solver=IgnoringAssumptionsSolver())
        with self.assertRaisesRegex(ValueError, "assumptions"):
            agent.classify_cell(make_state(), "A1")

    def test_unsat_must_not_include_a_model(self):
        solver = SimpleNamespace(solve=lambda *args: SATResult(False, {}, SolverMetrics()))
        with self.assertRaisesRegex(ValueError, "UNSAT"):
            make_agent(solver=solver).check_consistency(make_state((1,), (-1,)))

    def test_nonboolean_sat_flag_is_rejected(self):
        solver = SimpleNamespace(solve=lambda *args: SATResult(1, None, SolverMetrics()))
        with self.assertRaisesRegex(ValueError, "boolean satisfiable"):
            make_agent(solver=solver).check_consistency(make_state())

    def test_mutable_reused_solver_result_cannot_change_an_earlier_query(self):
        class ReusingSolver(ExhaustiveSolver):
            def __init__(self):
                super().__init__()
                self.result = SimpleNamespace()
                self.model = {}
                self.metrics = SolverMetrics(decisions=1)

            def solve(self, *args):
                current = super().solve(*args)
                self.model.clear()
                self.model.update(current.assignment or {})
                self.result.satisfiable = current.satisfiable
                self.result.assignment = self.model if current.satisfiable else None
                self.result.metrics = self.metrics
                return self.result

        agent = make_agent(solver=ReusingSolver())
        classification = agent.classify_cell(make_state((1,)), "A1")
        self.assertIs(classification.status, Status.CRIMINAL)
        self.assertFalse(classification.inconsistent)
        self.assertEqual(agent.stats.solver.decisions, 3)


class PublicConsistencyTests(unittest.TestCase):
    def test_consistency_query_checks_kb_without_classifying_a_cell(self):
        for clauses, inconsistent in (((), False), (((1,), (-1,)), True)):
            with self.subTest(inconsistent=inconsistent):
                agent = make_agent()
                result = agent.check_consistency(make_state(*clauses))
                self.assertIsNone(result.status)
                self.assertEqual(result.inconsistent, inconsistent)
                self.assertEqual(result.queries, ("KB: UNSAT" if inconsistent else "KB: SAT",))
                self.assertEqual(agent.stats.sat_calls, 1)
                self.assertEqual(agent.solver.calls[0].assumptions, ())

    def test_all_proved_inconsistent_hint_is_observable_and_deterministic(self):
        cells = tuple(reversed(make_cells()))
        proved = {cell.id: Status.CRIMINAL for cell in cells}
        # Reversed cells map variable 4 to A1, whose public verdict conflicts.
        state = make_state((-4,), cells=cells, proved=proved)
        hint = make_agent().hint(state)
        self.assertEqual(hint[0], "A1")
        self.assertTrue(hint[1].inconsistent)
        self.assertIsNone(hint[1].status)

    def test_all_proved_consistent_board_has_no_hint(self):
        proved = {cell.id: Status.CRIMINAL for cell in make_cells()}
        self.assertIsNone(make_agent().hint(make_state(proved=proved)))

    def test_empty_public_board_is_invalid_for_all_kb_entry_points(self):
        state = PublicGameState("Invalid empty board", 0, (), (), {})
        agent = make_agent()
        operations = (lambda: agent.check_consistency(state), lambda: agent.hint(state),
                      lambda: agent.classify_all(state), lambda: agent.check_uniqueness(state, ()))
        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(ValueError, "at least one cell"):
                    operation()
        self.assertEqual(agent.stats.sat_calls, 0)

    def test_one_by_one_board_remains_supported(self):
        agent = make_agent()
        hint = agent.hint(make_state((1,), size=1))
        self.assertEqual(hint[0], "A1")
        self.assertIs(hint[1].status, Status.CRIMINAL)


if __name__ == "__main__":
    unittest.main()
