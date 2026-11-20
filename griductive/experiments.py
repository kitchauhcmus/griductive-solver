from __future__ import annotations

import csv
import json
import multiprocessing
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty
from statistics import fmean, pstdev
from time import perf_counter

from .cnf import CNFEncoder
from .engine import GameController, GameEngine


def load_puzzle_manifest(path: Path) -> dict:
    """Load one ordered, reusable experiment set from a JSON manifest."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    entries = data.get("puzzles")
    if not isinstance(entries, list) or not entries:
        raise ValueError("experiment manifest must contain a non-empty 'puzzles' list")

    paths = tuple((path.parent / str(entry)).resolve() for entry in entries)
    if len(paths) != len(set(paths)):
        raise ValueError("experiment manifest contains duplicate puzzle paths")
    return {
        "name": str(data.get("name", path.stem)),
        "description": str(data.get("description", "")),
        "source": path.as_posix(),
        "paths": paths,
    }


def build_experiment_metadata(
    puzzle_source: str,
    puzzle_paths: list[Path] | tuple[Path, ...],
    runs: int,
    timeout_s: float | None,
) -> dict:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "puzzle_source": puzzle_source,
        "puzzle_count": len(puzzle_paths),
        "puzzles": [path.name for path in puzzle_paths],
        "runs_per_case": runs,
        "timeout_seconds_per_run": timeout_s,
        "runtime_definition": (
            "Solver runtime is accumulated DPLL time; end-to-end runtime measures "
            "the progressive auto-solve loop. Loading and full-CNF size inspection are excluded."
        ),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine() or "unknown",
    }


def _run_once(path: Path) -> dict:
    """Run one measured solve. Loading and CNF-size inspection are not timed."""
    engine = GameEngine.load(path)
    controller = GameController(engine)
    full_formula = CNFEncoder(
        engine.public_state.size, engine.public_state.cells
    ).encode_clues(engine.all_clues_for_validation())
    started = perf_counter()
    controller.auto_solve()
    elapsed_ms = (perf_counter() - started) * 1000
    metrics = controller.agent.stats.solver
    return {
        "size": engine.public_state.size,
        "primary_variables": len(full_formula.primary_variables),
        "auxiliary_variables": len(full_formula.auxiliary_variables),
        "full_cnf_clauses": full_formula.clause_count,
        "sat_calls": controller.agent.stats.sat_calls,
        "decisions": metrics.decisions,
        "propagations": metrics.propagations,
        "conflicts": metrics.conflicts,
        "backtracks": metrics.backtracks,
        "deduction_steps": len(controller.trace),
        "solver_runtime_ms": metrics.runtime_ms,
        "end_to_end_runtime_ms": elapsed_ms,
        "terminal": "SOLVED" if engine.solved else "UNKNOWN",
    }


def _worker(path: str, output) -> None:
    """Process entry point used so a timed-out solver can be terminated safely."""
    try:
        output.put(("ok", _run_once(Path(path))))
    except Exception as exc:
        output.put(("error", f"{type(exc).__name__}: {exc}"))


def _run_with_timeout(path: Path, timeout_s: float | None) -> tuple[dict | None, str | None]:
    if timeout_s is None:
        try:
            return _run_once(path), None
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive or None")

    context = multiprocessing.get_context("spawn")
    output = context.Queue()
    process = context.Process(target=_worker, args=(str(path.resolve()), output))
    process.start()
    process.join(timeout_s)
    if process.is_alive():
        process.terminate()
        process.join(2)
        if process.is_alive():
            process.kill()
            process.join()
        output.close()
        output.join_thread()
        return None, f"Timed out after {timeout_s:g} seconds"

    try:
        kind, payload = output.get(timeout=1)
    except Empty:
        kind, payload = "error", f"Worker exited with code {process.exitcode} without a result"
    finally:
        output.close()
        output.join_thread()
    return (payload, None) if kind == "ok" else (None, payload)


def _empty_row(path: Path, runs: int) -> dict:
    return {
        "puzzle": path.name,
        "size": None,
        "runs_requested": runs,
        "runs_completed": 0,
        "primary_variables": None,
        "auxiliary_variables": None,
        "full_cnf_clauses": None,
        "sat_calls": None,
        "decisions": None,
        "propagations": None,
        "conflicts": None,
        "backtracks": None,
        "deduction_steps": None,
        "solver_runtime_ms": None,
        "solver_runtime_ms_min": None,
        "solver_runtime_ms_max": None,
        "solver_runtime_ms_stdev": None,
        "end_to_end_runtime_ms": None,
        "end_to_end_runtime_ms_min": None,
        "end_to_end_runtime_ms_max": None,
        "end_to_end_runtime_ms_stdev": None,
        "terminal": "FAILED",
        "error": None,
    }


def _rounded(value: float) -> float:
    return round(value, 4)


def _aggregate(path: Path, runs: int, completed: list[dict], terminal: str, error: str | None) -> dict:
    row = _empty_row(path, runs)
    row["runs_completed"] = len(completed)
    row["terminal"] = terminal
    row["error"] = error
    if not completed:
        return row

    first = completed[0]
    for key in (
        "size", "primary_variables", "auxiliary_variables", "full_cnf_clauses",
        "sat_calls", "decisions", "propagations", "conflicts", "backtracks",
        "deduction_steps",
    ):
        row[key] = first[key]

    solver_times = [item["solver_runtime_ms"] for item in completed]
    end_to_end_times = [item["end_to_end_runtime_ms"] for item in completed]
    row.update({
        "solver_runtime_ms": _rounded(fmean(solver_times)),
        "solver_runtime_ms_min": _rounded(min(solver_times)),
        "solver_runtime_ms_max": _rounded(max(solver_times)),
        "solver_runtime_ms_stdev": _rounded(pstdev(solver_times)),
        "end_to_end_runtime_ms": _rounded(fmean(end_to_end_times)),
        "end_to_end_runtime_ms_min": _rounded(min(end_to_end_times)),
        "end_to_end_runtime_ms_max": _rounded(max(end_to_end_times)),
        "end_to_end_runtime_ms_stdev": _rounded(pstdev(end_to_end_times)),
    })
    return row


def run_experiments(
    puzzle_directory: Path,
    runs: int = 1,
    timeout_s: float | None = None,
    puzzle_paths: list[Path] | tuple[Path, ...] | None = None,
) -> list[dict]:
    """Benchmark every JSON case without dropping failures or timeouts."""
    if runs < 1:
        raise ValueError("runs must be at least 1")
    if timeout_s is not None and timeout_s <= 0:
        raise ValueError("timeout_s must be positive or None")

    paths = list(puzzle_paths) if puzzle_paths is not None else sorted(puzzle_directory.glob("*.json"))
    if len(paths) != len({path.resolve() for path in paths}):
        raise ValueError("experiment puzzle set contains duplicate paths")

    rows: list[dict] = []
    for path in paths:
        completed: list[dict] = []
        terminal = "FAILED"
        error: str | None = None
        for _ in range(runs):
            result, run_error = _run_with_timeout(path, timeout_s)
            if result is None:
                error = run_error
                terminal = "TIMEOUT" if run_error and run_error.startswith("Timed out") else "FAILED"
                break
            completed.append(result)
            terminal = result["terminal"]
            if terminal != "SOLVED":
                error = "Auto solver reached no forced verdict before solving the puzzle"
                break
        rows.append(_aggregate(path, runs, completed, terminal, error))
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json_report(rows: list[dict], metadata: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump({"metadata": metadata, "results": rows}, handle, indent=2)
        handle.write("\n")


def _markdown_value(value, decimals: int = 4) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:,.{decimals}f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value).replace("|", "\\|")


def write_markdown_report(rows: list[dict], metadata: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timeout = metadata.get("timeout_seconds_per_run")
    timeout_text = "disabled" if timeout is None else f"{timeout:g} seconds per run"
    lines = [
        "# Griductive Experiment Results",
        "",
        f"Generated at `{metadata.get('generated_at_utc', 'unknown')}`.",
        "",
        "## Method",
        "",
        f"- Experiment: `{metadata.get('experiment_name', 'directory_scan')}`.",
        f"- Description: {metadata.get('experiment_description', 'All JSON puzzles in the selected directory.')}",
        f"- Puzzle set: `{metadata.get('puzzle_source', 'unknown')}`.",
        f"- Cases: {metadata.get('puzzle_count', len(rows))}.",
        f"- Repetitions: {metadata.get('runs_per_case', 1)} measured runs per case.",
        f"- Timeout: {timeout_text}.",
        "- Every comparison uses the same ordered puzzle set.",
        "- Runtime columns report the mean across completed runs; `+/-` is population standard deviation.",
        f"- Environment: Python {metadata.get('python_version', 'unknown')} on {metadata.get('platform', 'unknown')}.",
        "",
        "## Results",
        "",
        "| Puzzle | Size | Runs | Primary | Auxiliary | CNF clauses | SAT calls | Decisions | Propagations | Conflicts | Backtracks | Steps | Solver ms | End-to-end ms | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        solver_time = _markdown_value(row.get("solver_runtime_ms"))
        end_time = _markdown_value(row.get("end_to_end_runtime_ms"))
        if row.get("solver_runtime_ms") is not None:
            solver_time += f" +/- {_markdown_value(row.get('solver_runtime_ms_stdev'))}"
        if row.get("end_to_end_runtime_ms") is not None:
            end_time += f" +/- {_markdown_value(row.get('end_to_end_runtime_ms_stdev'))}"
        completed_runs = f"{row.get('runs_completed', 0)}/{row.get('runs_requested', 0)}"
        values = (
            row.get("puzzle"), row.get("size"), completed_runs, row.get("primary_variables"),
            row.get("auxiliary_variables"), row.get("full_cnf_clauses"),
            row.get("sat_calls"), row.get("decisions"), row.get("propagations"),
            row.get("conflicts"), row.get("backtracks"), row.get("deduction_steps"),
            solver_time, end_time, row.get("terminal"),
        )
        lines.append("| " + " | ".join(_markdown_value(value) for value in values) + " |")

    problems = [row for row in rows if row.get("terminal") != "SOLVED"]
    lines.extend(["", "## Failures and timeouts", ""])
    if not problems:
        lines.append("No failures or timeouts occurred in this experiment run.")
    else:
        lines.extend([
            "| Puzzle | Completed runs | Terminal | Error |",
            "|---|---:|---|---|",
        ])
        for row in problems:
            lines.append(
                "| " + " | ".join(_markdown_value(value) for value in (
                    row.get("puzzle"), row.get("runs_completed"),
                    row.get("terminal"), row.get("error"),
                )) + " |"
            )

    successful = [
        row for row in rows
        if row.get("terminal") == "SOLVED" and row.get("end_to_end_runtime_ms") is not None
    ]
    lines.extend(["", "## Observations", ""])
    lines.append(
        f"- {len(successful)}/{len(rows)} cases completed successfully; "
        f"{len(problems)} failure or timeout outcome(s) were recorded."
    )
    if successful:
        slowest = max(successful, key=lambda row: row["end_to_end_runtime_ms"])
        largest = max(successful, key=lambda row: row["full_cnf_clauses"])
        lines.append(
            f"- `{slowest['puzzle']}` had the highest mean end-to-end runtime "
            f"({_markdown_value(slowest['end_to_end_runtime_ms'])} ms)."
        )
        lines.append(
            f"- `{largest['puzzle']}` generated the largest CNF "
            f"({_markdown_value(largest['full_cnf_clauses'])} clauses and "
            f"{_markdown_value(largest['auxiliary_variables'])} auxiliary variables)."
        )
        lines.append(
            "- Search effort grows with clue structure as well as board size: counting and "
            "connectivity encodings introduce auxiliary state beyond the primary character variables."
        )

    lines.extend([
        "",
        "## Measurement notes and limitations",
        "",
        f"- {metadata.get('runtime_definition', '')}",
        "- Primary, auxiliary, clause, SAT-call, decision, propagation, backtrack, and step counts are deterministic for the current solver and puzzle set.",
        "- Failed or timed-out cases remain in every output with empty unavailable metrics; they are never silently removed.",
        "- Runtime is machine- and load-dependent; repeated-run statistics reduce but do not eliminate that variation.",
        "- The suite contains five curated puzzles and evaluates one deterministic DPLL configuration; it is not a universal SAT benchmark.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")
