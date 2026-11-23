"""Regression coverage for the one-proof/one-clue reveal boundary."""
from __future__ import annotations

import unittest

from griductive.controller import GameController
from griductive.models import RunStatus, Status, VerdictResult
from tests.support import EncodedClue, FixtureEngine, chain_fixture, make_agent, make_state


class RevealContractTests(unittest.TestCase):
    def assert_bad_reveal_rejected(self, engine_type):
        engine = engine_type(make_state((1,)), solution={"A1": Status.CRIMINAL})
        controller = GameController(engine, make_agent(), check_revealed_consistency=True)
        with self.assertRaises(RuntimeError):
            controller.submit("A1", Status.CRIMINAL)
        self.assertEqual(controller.trace, [])
        # The engine has already run. Its own contract requires atomic updates;
        # the controller can detect a violation but cannot roll back its internals.

    def test_returning_existing_clue_without_publishing_a_new_one_is_rejected(self):
        class MissingClueEngine(FixtureEngine):
            def reveal_after_proof(self, cell_id, status):
                super().reveal_after_proof(cell_id, status)
                self._revealed.pop()
                return self._initial_state.revealed_clues[0]

        self.assert_bad_reveal_rejected(MissingClueEngine)

    def test_publishing_an_extra_unearned_clue_is_rejected(self):
        class ExtraClueEngine(FixtureEngine):
            def reveal_after_proof(self, cell_id, status):
                clue = super().reveal_after_proof(cell_id, status)
                self._revealed.append(EncodedClue("unearned_hidden_B1", ((2,),)))
                return clue

        self.assert_bad_reveal_rejected(ExtraClueEngine)

    def test_returned_clue_must_match_published_content_not_only_id(self):
        class MismatchedClueEngine(FixtureEngine):
            def reveal_after_proof(self, cell_id, status):
                clue = super().reveal_after_proof(cell_id, status)
                return EncodedClue(clue.id, ((-1,),))

        self.assert_bad_reveal_rejected(MismatchedClueEngine)

    def test_duplicate_clue_ids_in_new_public_state_are_rejected(self):
        class DuplicateClueEngine(FixtureEngine):
            def reveal_after_proof(self, cell_id, status):
                clue = super().reveal_after_proof(cell_id, status)
                self._revealed.append(clue)
                return clue

        self.assert_bad_reveal_rejected(DuplicateClueEngine)

    def test_failed_engine_contract_blocks_play_until_restart(self):
        class ExtraClueEngine(FixtureEngine):
            def reveal_after_proof(self, cell_id, status):
                clue = super().reveal_after_proof(cell_id, status)
                self._revealed.append(EncodedClue("unearned_hidden_B1", ((2,),)))
                return clue

        operations = {
            "hint": lambda controller: controller.hint(),
            "submit": lambda controller: controller.submit("B1", Status.CRIMINAL),
            "auto_step": lambda controller: controller.auto_step(),
            "auto_solve": lambda controller: controller.auto_solve(),
        }
        for name, operation in operations.items():
            with self.subTest(operation=name):
                engine = ExtraClueEngine(
                    make_state((1,)),
                    solution={"A1": Status.CRIMINAL, "B1": Status.CRIMINAL},
                )
                initial = engine.public_state
                controller = GameController(engine, make_agent(), check_revealed_consistency=True)
                with self.assertRaises(RuntimeError):
                    controller.submit("A1", Status.CRIMINAL)
                calls_after_failure = controller.agent.stats.sat_calls
                reveals_after_failure = list(engine.reveal_calls)
                with self.assertRaises(RuntimeError):
                    operation(controller)
                self.assertEqual(controller.agent.stats.sat_calls, calls_after_failure)
                self.assertEqual(engine.reveal_calls, reveals_after_failure)
                self.assertEqual(controller.trace, [])
                controller.restart()
                self.assertEqual(engine.public_state, initial)
                self.assertEqual(controller.hint()[0], "A1")


class RevealedContradictionTests(unittest.TestCase):
    @staticmethod
    def controller_with_bad_first_clue():
        engine = chain_fixture(2)
        engine._hidden_clues["A1"] = EncodedClue("bad_first_clue", ((-1,),))
        return GameController(engine, make_agent(), check_revealed_consistency=True)

    def assert_accepted_but_now_inconsistent(self, controller, result):
        self.assertIs(result.result, VerdictResult.ACCEPTED)
        self.assertFalse(controller.engine.solved)
        self.assertIs(controller.last_run_status, RunStatus.INCONSISTENT)
        self.assertEqual(controller.engine.reveal_calls, [("A1", Status.CRIMINAL)])
        self.assertEqual(len(controller.trace), 1)
        self.assertEqual(controller.trace[0].revealed_clue, "bad_first_clue")
        self.assertIs(controller.trace[0].verdict, Status.CRIMINAL)
        # The original move was proved from the earlier, consistent public KB.
        # Its newly revealed clue makes subsequent play inconsistent.
        self.assertEqual(controller.auto_solve(), [])
        self.assertEqual(len(controller.engine.reveal_calls), 1)

    def test_manual_submit_reports_intermediate_revealed_contradiction(self):
        controller = self.controller_with_bad_first_clue()
        result = controller.submit("A1", Status.CRIMINAL)
        self.assert_accepted_but_now_inconsistent(controller, result)

    def test_auto_step_reports_intermediate_revealed_contradiction(self):
        controller = self.controller_with_bad_first_clue()
        result = controller.auto_step()
        self.assertIsNotNone(result)
        self.assert_accepted_but_now_inconsistent(controller, result)

    def test_step_limit_does_not_hide_intermediate_revealed_contradiction(self):
        controller = self.controller_with_bad_first_clue()
        results = controller.auto_solve(max_steps=1)
        self.assertEqual(len(results), 1)
        self.assert_accepted_but_now_inconsistent(controller, results[0])


if __name__ == "__main__":
    unittest.main()
