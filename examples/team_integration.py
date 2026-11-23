"""Run the real team modules once engine.py, cnf.py, and dpll.py are available.

Usage from the repository root:
    python -m examples.team_integration puzzles/your_puzzle.json
This example deliberately uses no test doubles or hidden-clue validation API.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json

from griductive.agent import LogicAgent
from griductive.controller import GameController


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("puzzle", help="JSON puzzle path accepted by GameEngine.load")
    parser.add_argument("--max-steps", type=int, help="Maximum accepted moves in this run")
    args = parser.parse_args()
    if args.max_steps is not None and args.max_steps < 0:
        parser.error("--max-steps must be nonnegative")

    try:
        from griductive.cnf import CNFEncoder
        from griductive.dpll import DPLLSolver
        from griductive.engine import GameEngine
    except ModuleNotFoundError as exc:
        if exc.name not in {"griductive.cnf", "griductive.dpll", "griductive.engine"}:
            raise
        parser.error(
            f"Team module {exc.name} is not available yet. "
            "Add the real engine, encoder, and solver modules before running this example. "
            "For the current standalone demo use: python -m examples.agent_demo"
        )

    engine = GameEngine.load(args.puzzle)
    agent = LogicAgent(solver=DPLLSolver(), encoder_factory=CNFEncoder)
    controller = GameController(engine, agent)
    accepted = controller.auto_solve(max_steps=args.max_steps)
    print(json.dumps({
        "stop_reason": controller.last_run_status.value,
        "accepted_moves": len(accepted),
        "sat_calls": agent.stats.sat_calls,
        "solver_metrics": asdict(agent.stats.solver),
        "trace": [asdict(step) for step in controller.trace],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
