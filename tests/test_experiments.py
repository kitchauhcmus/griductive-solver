import csv
import json
import shutil
from pathlib import Path

import pytest

from griductive.experiments import (
    build_experiment_metadata,
    load_puzzle_manifest,
    run_experiments,
    write_csv,
    write_json_report,
    write_markdown_report,
)


def test_experiments_repeat_successful_runs_and_write_csv(tmp_path):
    cases = tmp_path / "cases"
    cases.mkdir()
    shutil.copyfile("puzzles/3x3_binary_chain.json", cases / "case.json")

    rows = run_experiments(cases, runs=2)
    assert len(rows) == 1
    row = rows[0]
    assert row["terminal"] == "SOLVED"
    assert row["runs_requested"] == row["runs_completed"] == 2
    assert row["error"] is None
    assert row["end_to_end_runtime_ms_min"] <= row["end_to_end_runtime_ms_max"]

    output = tmp_path / "results.csv"
    write_csv(rows, output)
    with output.open(encoding="utf-8", newline="") as handle:
        saved = list(csv.DictReader(handle))
    assert saved[0]["terminal"] == "SOLVED"


def test_experiments_record_failure_without_raising(tmp_path):
    (tmp_path / "broken.json").write_text("{not valid JSON", encoding="utf-8")
    row = run_experiments(tmp_path)[0]
    assert row["terminal"] == "FAILED"
    assert row["runs_completed"] == 0
    assert "JSONDecodeError" in row["error"]


def test_experiments_record_timeout(tmp_path):
    shutil.copyfile("puzzles/3x3_binary_chain.json", tmp_path / "case.json")
    row = run_experiments(tmp_path, timeout_s=0.001)[0]
    assert row["terminal"] == "TIMEOUT"
    assert row["runs_completed"] == 0
    assert row["error"].startswith("Timed out")


def test_experiments_validate_run_count(tmp_path):
    with pytest.raises(ValueError, match="runs"):
        run_experiments(tmp_path, runs=0)


def test_manifest_locks_ordered_puzzle_set(tmp_path):
    cases = tmp_path / "cases"
    cases.mkdir()
    shutil.copyfile("puzzles/3x3_binary_chain.json", cases / "first.json")
    shutil.copyfile("puzzles/3x3_counting_chain.json", cases / "second.json")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({
        "name": "fixture",
        "puzzles": ["cases/second.json", "cases/first.json"],
    }), encoding="utf-8")

    manifest = load_puzzle_manifest(manifest_path)
    assert manifest["name"] == "fixture"
    assert [path.name for path in manifest["paths"]] == ["second.json", "first.json"]
    rows = run_experiments(tmp_path, puzzle_paths=manifest["paths"])
    assert [row["puzzle"] for row in rows] == ["second.json", "first.json"]


def test_json_and_markdown_reports_include_metadata_and_failure_section(tmp_path):
    rows = run_experiments(Path("puzzles"), puzzle_paths=[Path("puzzles/3x3_binary_chain.json")])
    metadata = build_experiment_metadata("fixture", [Path("puzzles/3x3_binary_chain.json")], 1, 60)
    json_path = tmp_path / "results.json"
    markdown_path = tmp_path / "results.md"

    write_json_report(rows, metadata, json_path)
    write_markdown_report(rows, metadata, markdown_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["puzzle_count"] == 1
    assert payload["results"][0]["terminal"] == "SOLVED"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "## Results" in markdown
    assert "## Failures and timeouts" in markdown
    assert "No failures or timeouts occurred" in markdown
