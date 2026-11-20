import json

from griductive.cli import run_cli, validate_file


def _ambiguous_puzzle() -> dict:
    tautology = {"type": "AT_MOST", "k": 4, "region": {"type": "WHOLE_GRID"}}
    return {
        "title": "Ambiguous fixture",
        "size": 2,
        "solution": {
            "A1": "INNOCENT", "B1": "INNOCENT",
            "A2": "INNOCENT", "B2": "INNOCENT",
        },
        "initially_revealed": ["A1"],
        "clues": {cell_id: tautology for cell_id in ("A1", "B1", "A2", "B2")},
    }


def test_validate_rejects_non_unique_non_progressive_puzzle(tmp_path, capsys):
    path = tmp_path / "ambiguous.json"
    path.write_text(json.dumps(_ambiguous_puzzle()), encoding="utf-8")

    result = validate_file(path)
    assert not result["valid"]
    assert result["full_clue_set_satisfiable"]
    assert not result["unique"]
    assert not result["progressively_solvable"]
    assert len(result["issues"]) == 2

    assert run_cli(["validate", str(path)]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["valid"] is False
