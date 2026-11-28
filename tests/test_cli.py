import json
from pathlib import Path

import pytest

from griductive.cli import run_cli, solve_file, validate_file
from griductive.models import PuzzleValidationError


def _ambiguous_puzzle() -> dict:
    tautology = {
        "type": "AT_MOST",
        "k": 4,
        "region": {
            "type": "WHOLE_GRID",
        },
    }

    return {
        "title": "Ambiguous fixture",
        "size": 2,
        "solution": {
            "A1": "INNOCENT",
            "B1": "INNOCENT",
            "A2": "INNOCENT",
            "B2": "INNOCENT",
        },
        "initially_revealed": ["A1"],
        "clues": {
            cell_id: tautology
            for cell_id in ("A1", "B1", "A2", "B2")
        },
    }


def test_validate_rejects_non_unique_non_progressive_puzzle(
    tmp_path,
    capsys,
):
    path = tmp_path / "ambiguous.json"
    path.write_text(
        json.dumps(_ambiguous_puzzle()),
        encoding="utf-8",
    )

    result = validate_file(path)

    assert not result["valid"]
    assert result["full_clue_set_satisfiable"]
    assert not result["unique"]
    assert not result["progressively_solvable"]
    assert len(result["issues"]) == 2

    assert run_cli(["validate", str(path)]) == 1

    printed = json.loads(capsys.readouterr().out)
    assert printed["valid"] is False


@pytest.mark.parametrize(
    "bad_size",
    [3.5, 3.0, True, "3", 0, -1, None],
)
def test_validate_rejects_invalid_json_size(
    bad_size,
    tmp_path,
    capsys,
):
    source = Path("puzzles/3x3_binary_chain.json")
    data = json.loads(source.read_text(encoding="utf-8"))
    data["size"] = bad_size

    path = tmp_path / "bad_size.json"
    path.write_text(
        json.dumps(data),
        encoding="utf-8",
    )

    assert run_cli(["validate", str(path)]) == 1

    printed = json.loads(capsys.readouterr().out)
    assert "size must be a positive JSON integer" in printed["error"]


@pytest.mark.parametrize(
    ("puzzle", "terminal", "steps"),
    [
        ("3x3_binary_chain.json", "SOLVED", 8),
        (
            "diagnostics/3x3_ambiguous_var_check.json",
            "UNKNOWN",
            0,
        ),
        (
            "diagnostics/3x3_inconsistent_scandal.json",
            "INCONSISTENT",
            0,
        ),
    ],
)
def test_solve_reports_actual_outcome(
    puzzle,
    terminal,
    steps,
    capsys,
):
    path = Path("puzzles") / puzzle

    assert run_cli(["solve", str(path)]) == 0

    result = json.loads(capsys.readouterr().out)

    assert result["terminal"] == terminal
    assert result["solved"] == (terminal == "SOLVED")
    assert result["accepted_reveals"] == steps


def test_inconsistent_demo_exception_is_limited_to_playing_the_bundled_file(
    tmp_path,
):
    source = Path(
        "puzzles/diagnostics/3x3_inconsistent_scandal.json"
    )

    with pytest.raises(PuzzleValidationError):
        validate_file(source)

    copy = tmp_path / source.name
    copy.write_bytes(source.read_bytes())

    with pytest.raises(PuzzleValidationError):
        solve_file(copy)