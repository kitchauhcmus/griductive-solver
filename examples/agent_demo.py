"""Run with ``python -m examples.agent_demo`` from the repository root.

This is an agent integration demo with a TEST exhaustive SAT oracle and fixture
encoder/engine. It does not substitute for the teammates' DPLL, CNF, or GUI work.
"""
from griductive.controller import GameController
from tests.support import chain_fixture, make_agent


def main():
    print("Agent integration demo: synthetic 3x3 chain; TEST exhaustive SAT oracle")
    controller = GameController(
        chain_fixture(3), make_agent(), check_revealed_consistency=True,
    )
    for result in controller.auto_solve():
        print(f"{result.cell_id}: {result.forced.value} -> {result.result.value}")
    print(f"Stopped: {controller.last_run_status.value}; SAT calls: {controller.agent.stats.sat_calls}")
    print("First deduction trace:")
    print(controller.trace[0])


if __name__ == "__main__":
    main()
