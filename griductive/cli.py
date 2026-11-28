from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent import LogicAgent
from .clues import validate_puzzle
from .engine import GameController, GameEngine
from .models import Puzzle, RunStatus


def validate_file(path: Path) -> dict:
    puzzle = Puzzle.load(path)
    validate_puzzle(puzzle)

    controller = GameController(GameEngine(puzzle))

    full_sat, unique = controller.agent.check_uniqueness(
        controller.engine.public_state,
        controller.engine.all_clues_for_validation(),
    )

    controller.agent.reset_stats()
    steps = controller.auto_solve()
    progressively_solvable = controller.engine.solved
    valid = full_sat and unique and progressively_solvable

    issues: list[str] = []

    if not full_sat:
        issues.append("the complete clue set is unsatisfiable")
    elif not unique:
        issues.append("the complete clue set has multiple solutions")

    if not progressively_solvable:
        issues.append(
            "the public reveal sequence cannot be completed without guessing"
        )

    return {
        "file": str(path),
        "valid": valid,
        "full_clue_set_satisfiable": full_sat,
        "unique": unique,
        "progressively_solvable": progressively_solvable,
        "deduction_steps": len(steps),
        "issues": issues,
    }


def solve_file(path: Path) -> dict:
    controller = GameController(
        GameEngine.load(path, allow_diagnostic=True)
    )

    results = controller.auto_solve()
    outcome = controller.last_run_status

    return {
        "puzzle": controller.engine.public_state.title,
        "solved": outcome is RunStatus.SOLVED,
        "steps": [
            {
                "step": step.step,
                "cell": step.cell_id,
                "verdict": step.verdict.value,
                "active_clues": step.active_clues,
                "queries": step.sat_queries,
                "revealed_clue": step.revealed_clue,
            }
            for step in controller.trace
        ],
        "sat_calls": controller.agent.stats.sat_calls,
        "metrics": vars(controller.agent.stats.solver),
        "terminal": (
            "UNKNOWN"
            if outcome is RunStatus.STUCK
            else outcome.value
        ),
        "accepted_reveals": len(results),
    }


def run_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Griductive validation and solver CLI"
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    solve = sub.add_parser(
        "solve",
        help="auto-solve one puzzle",
    )
    solve.add_argument("puzzle", type=Path)

    validate = sub.add_parser(
        "validate",
        help="validate a puzzle or directory",
    )
    validate.add_argument("target", type=Path)

    experiment = sub.add_parser(
        "experiments",
        help="run benchmark suite",
    )
    experiment.add_argument(
        "--puzzles",
        type=Path,
        default=Path("puzzles"),
    )
    experiment.add_argument(
        "--manifest",
        type=Path,
        help="fixed ordered JSON puzzle-set manifest",
    )
    experiment.add_argument("--csv", type=Path)
    experiment.add_argument("--json", type=Path)
    experiment.add_argument("--markdown", type=Path)
    experiment.add_argument(
        "--runs",
        type=int,
        default=3,
        help="measured runs per puzzle (default: 3)",
    )
    experiment.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help=(
            "timeout in seconds for each run; "
            "use 0 to disable (default: 60)"
        ),
    )

    args = parser.parse_args(argv)

    if args.command == "experiments":
        if args.runs < 1:
            parser.error("--runs must be at least 1")

        if args.timeout < 0:
            parser.error("--timeout must be zero or positive")

    if args.command == "solve":
        print(json.dumps(
            solve_file(args.puzzle),
            indent=2,
        ))
        return 0

    if args.command == "validate":
        paths = (
            sorted(args.target.glob("*.json"))
            if args.target.is_dir()
            else [args.target]
        )

        failed = False

        for path in paths:
            try:
                result = validate_file(path)
                print(json.dumps(result, indent=2))
                failed = failed or not result["valid"]
            except Exception as exc:
                failed = True
                print(json.dumps({
                    "file": str(path),
                    "valid": False,
                    "error": str(exc),
                }, indent=2))

        return 1 if failed else 0

    from .experiments import (
        build_experiment_metadata,
        load_puzzle_manifest,
        run_experiments,
        write_csv,
        write_json_report,
        write_markdown_report,
    )

    timeout_s = None if args.timeout == 0 else args.timeout

    try:
        if args.manifest:
            manifest = load_puzzle_manifest(args.manifest)
            puzzle_paths = manifest["paths"]
            puzzle_source = manifest["source"]
        else:
            puzzle_paths = tuple(
                sorted(args.puzzles.glob("*.json"))
            )
            puzzle_source = str(args.puzzles)

        rows = run_experiments(
            args.puzzles,
            runs=args.runs,
            timeout_s=timeout_s,
            puzzle_paths=puzzle_paths,
        )

        metadata = build_experiment_metadata(
            puzzle_source,
            puzzle_paths,
            args.runs,
            timeout_s,
        )

        if args.manifest:
            metadata["experiment_name"] = manifest["name"]
            metadata["experiment_description"] = manifest["description"]

    except Exception as exc:
        print(json.dumps({
            "terminal": "FAILED",
            "error": f"{type(exc).__name__}: {exc}",
        }, indent=2))
        return 1

    print(json.dumps(rows, indent=2))

    if args.csv:
        write_csv(rows, args.csv)

    if args.json:
        write_json_report(rows, metadata, args.json)

    if args.markdown:
        write_markdown_report(rows, metadata, args.markdown)

    return (
        0
        if rows and all(row["terminal"] == "SOLVED" for row in rows)
        else 1
    )