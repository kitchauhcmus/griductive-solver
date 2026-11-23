from __future__ import annotations

import unittest

from griductive.controller import GameController
from griductive.models import RunStatus, Status, VerdictResult
from tests.support import EncodedClue, FixtureEngine, chain_fixture, make_agent, make_state


class ControllerTests(unittest.TestCase):
    def make_controller(self, state=None, **kwargs):
        engine = FixtureEngine(state or make_state((1,), (-2,)), **kwargs)
        return GameController(engine, make_agent())

    def test_not_provable_and_contradicted_rejections_do_not_reveal(self):
        controller = self.make_controller()
        before = controller.engine.public_state
        self.assertIs(controller.submit("A2", Status.CRIMINAL).result, VerdictResult.NOT_PROVABLE)
        self.assertIs(controller.submit("A1", Status.INNOCENT).result, VerdictResult.CONTRADICTED)
        self.assertEqual(controller.engine.public_state, before)
        self.assertEqual(controller.engine.reveal_calls, [])
        self.assertEqual(controller.trace, [])

    def test_acceptance_reveals_after_proof_and_records_trace(self):
        controller = self.make_controller(solution={"A1": Status.CRIMINAL})
        result = controller.submit("A1", "CRIMINAL")
        self.assertIs(result.result, VerdictResult.ACCEPTED)
        self.assertEqual(controller.engine.reveal_calls, [("A1", Status.CRIMINAL)])
        step = controller.trace[0]
        self.assertEqual(step.step, 1)
        self.assertEqual(step.active_clues, ("public",))
        self.assertEqual(step.cell_id, "A1")
        self.assertIs(step.verdict, Status.CRIMINAL)
        self.assertEqual(step.revealed_clue, "clue_A1")
        self.assertIn("KB: SAT", step.sat_queries)
        self.assertTrue(any("INNOCENT: UNSAT" in query for query in step.sat_queries))

    def test_hint_does_not_change_state_or_reveal(self):
        controller = self.make_controller(solution={"A1": Status.CRIMINAL})
        before = controller.engine.public_state
        self.assertEqual(controller.hint()[0], "A1")
        self.assertEqual(controller.engine.public_state, before)
        self.assertEqual(controller.trace, [])
        self.assertEqual(controller.engine.reveal_calls, [])

    def test_inconsistent_submission_and_auto_stop(self):
        controller = self.make_controller(make_state((1,), (-1,)))
        self.assertIs(controller.submit("A1", Status.CRIMINAL).result, VerdictResult.INCONSISTENT)
        self.assertEqual(controller.auto_solve(), [])
        self.assertIs(controller.last_run_status, RunStatus.INCONSISTENT)
        self.assertEqual(controller.engine.reveal_calls, [])

    def test_already_solved_rechecks_inconsistent_knowledge(self):
        controller = self.make_controller(make_state((-1,), proved={"A1": Status.CRIMINAL}))
        self.assertIs(controller.submit("A1", Status.CRIMINAL).result, VerdictResult.INCONSISTENT)

    def test_repeat_submission_does_not_reveal_twice(self):
        controller = self.make_controller(solution={"A1": Status.CRIMINAL})
        controller.submit("A1", Status.CRIMINAL)
        self.assertIs(controller.submit("A1", Status.CRIMINAL).result, VerdictResult.ALREADY_SOLVED)
        self.assertEqual(len(controller.engine.reveal_calls), 1)
        self.assertEqual(len(controller.trace), 1)

    def test_invalid_cell_and_verdict_fail_without_reveal(self):
        controller = self.make_controller()
        for cell, verdict in (("Z99", Status.CRIMINAL), ("A1", "UNKNOWN")):
            with self.subTest(cell=cell, verdict=verdict), self.assertRaises(ValueError):
                controller.submit(cell, verdict)
        self.assertEqual(controller.engine.reveal_calls, [])

    def test_unknown_auto_solve_stops_without_guessing(self):
        controller = self.make_controller(make_state((1, 2)))
        self.assertEqual(controller.auto_solve(), [])
        self.assertIs(controller.last_run_status, RunStatus.STUCK)
        self.assertEqual(controller.engine.reveal_calls, [])

    def test_sequential_reveal_chain_on_3x3_and_4x4(self):
        for size in (3, 4):
            with self.subTest(size=size):
                controller = GameController(chain_fixture(size), make_agent())
                submissions = controller.auto_solve()
                self.assertEqual(len(submissions), size * size)
                self.assertTrue(controller.engine.solved)
                self.assertIs(controller.last_run_status, RunStatus.SOLVED)
                self.assertEqual([step.step for step in controller.trace], list(range(1, size * size + 1)))
                for index, step in enumerate(controller.trace):
                    self.assertEqual(len(step.active_clues), index + 1)
                self.assertIn("clue_A1", controller.trace[1].active_clues)

    def test_step_limit_preserves_partial_progress(self):
        controller = GameController(chain_fixture(3), make_agent())
        self.assertEqual(len(controller.auto_solve(max_steps=2)), 2)
        self.assertIs(controller.last_run_status, RunStatus.STEP_LIMIT)
        self.assertFalse(controller.engine.solved)
        self.assertEqual(len(controller.auto_solve()), 7)
        self.assertIs(controller.last_run_status, RunStatus.SOLVED)

    def test_zero_step_limit_does_not_reveal(self):
        controller = GameController(chain_fixture(3), make_agent())
        self.assertEqual(controller.auto_solve(max_steps=0), [])
        self.assertEqual(controller.engine.reveal_calls, [])
        self.assertIs(controller.last_run_status, RunStatus.STEP_LIMIT)

    def test_invalid_step_limit_is_rejected_before_reveal(self):
        controller = GameController(chain_fixture(3), make_agent())
        for limit in (-1, True, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                controller.auto_solve(max_steps=limit)
        self.assertEqual(controller.engine.reveal_calls, [])

    def test_complete_board_still_checks_revealed_clue_consistency(self):
        proved = {"A1": Status.CRIMINAL, "B1": Status.INNOCENT,
                  "A2": Status.CRIMINAL, "B2": Status.INNOCENT}
        controller = self.make_controller(make_state((-1,), proved=proved))
        self.assertEqual(controller.auto_solve(), [])
        self.assertIs(controller.last_run_status, RunStatus.INCONSISTENT)

    def test_last_revealed_clue_is_checked_before_reporting_solved(self):
        engine = chain_fixture(3)
        engine._hidden_clues["C3"] = EncodedClue("bad_final_clue", ((-1,),))
        controller = GameController(engine, make_agent())
        self.assertEqual(len(controller.auto_solve()), 9)
        self.assertIs(controller.last_run_status, RunStatus.INCONSISTENT)

    def test_auto_step_reports_final_clue_contradiction_immediately(self):
        engine = chain_fixture(2)
        engine._hidden_clues["B2"] = EncodedClue("bad_final_clue", ((-1,),))
        controller = GameController(engine, make_agent())
        self.assertEqual(len(controller.auto_solve(max_steps=3)), 3)
        result = controller.auto_step()
        self.assertIs(result.result, VerdictResult.ACCEPTED)
        self.assertTrue(engine.solved)
        self.assertIs(controller.last_run_status, RunStatus.INCONSISTENT)
        self.assertEqual(len(controller.trace), 4)

    def test_manual_submit_reports_final_clue_contradiction_immediately(self):
        engine = chain_fixture(2)
        engine._hidden_clues["B2"] = EncodedClue("bad_final_clue", ((-1,),))
        controller = GameController(engine, make_agent())
        self.assertEqual(len(controller.auto_solve(max_steps=3)), 3)
        result = controller.submit("B2", Status.INNOCENT)
        self.assertIs(result.result, VerdictResult.ACCEPTED)
        self.assertTrue(engine.solved)
        self.assertIs(controller.last_run_status, RunStatus.INCONSISTENT)
        self.assertEqual(len(controller.trace), 4)

    def test_restart_clears_trace_stats_and_engine_progress(self):
        controller = GameController(chain_fixture(3), make_agent())
        initial = controller.engine.public_state
        controller.auto_solve(max_steps=2)
        controller.restart()
        self.assertEqual(controller.engine.public_state, initial)
        self.assertEqual(controller.trace, [])
        self.assertEqual(controller.agent.stats.sat_calls, 0)
        self.assertIs(controller.last_run_status, RunStatus.READY)

    def test_hidden_labels_and_clues_cannot_influence_hint(self):
        state = make_state((1,))
        first = self.make_controller(state, hidden_clues={"A1": EncodedClue("secret1", ((2,),))},
                                     solution={"A1": Status.CRIMINAL})
        second = self.make_controller(state, hidden_clues={"A1": EncodedClue("secret2", ((-2,),))},
                                      solution={"A1": Status.INNOCENT})
        self.assertEqual(first.hint(), second.hint())
        self.assertEqual(first.engine.reveal_calls, [])
        self.assertEqual(second.engine.reveal_calls, [])

    def test_engine_failure_does_not_record_accepted_trace(self):
        controller = self.make_controller(solution={"A1": Status.INNOCENT})
        before = controller.engine.public_state
        with self.assertRaises(RuntimeError):
            controller.submit("A1", Status.CRIMINAL)
        self.assertEqual(controller.engine.public_state, before)
        self.assertEqual(controller.trace, [])

    def test_no_progress_engine_cannot_create_infinite_auto_solve_loop(self):
        class NoProgressEngine(FixtureEngine):
            def reveal_after_proof(self, cell_id, status):
                return EncodedClue("not_actually_revealed")
        controller = GameController(NoProgressEngine(make_state((1,))), make_agent())
        with self.assertRaises(RuntimeError):
            controller.auto_solve()
        self.assertEqual(controller.trace, [])

    def test_engine_cannot_erase_or_change_prior_verdicts_or_add_unproved_ones(self):
        for corruption in ("erase", "change", "add"):
            with self.subTest(corruption=corruption):
                class CorruptingEngine(FixtureEngine):
                    def reveal_after_proof(self, cell_id, status):
                        clue = super().reveal_after_proof(cell_id, status)
                        if corruption == "erase":
                            self._proved.pop("A1")
                        elif corruption == "change":
                            self._proved["A1"] = Status.INNOCENT
                        else:
                            self._proved["A2"] = Status.CRIMINAL
                        return clue
                state = make_state((2,), proved={"A1": Status.CRIMINAL})
                engine = CorruptingEngine(state, solution={"B1": Status.CRIMINAL})
                controller = GameController(engine, make_agent())
                with self.assertRaises(RuntimeError):
                    controller.auto_solve()
                self.assertEqual(controller.trace, [])

    def test_engine_cannot_erase_previous_revealed_clues(self):
        class ErasingEngine(FixtureEngine):
            def reveal_after_proof(self, cell_id, status):
                clue = super().reveal_after_proof(cell_id, status)
                self._revealed = [clue]
                return clue
        engine = ErasingEngine(make_state((1,)), solution={"A1": Status.CRIMINAL})
        controller = GameController(engine, make_agent())
        with self.assertRaises(RuntimeError):
            controller.auto_solve()
        self.assertEqual(controller.trace, [])


if __name__ == "__main__":
    unittest.main()
