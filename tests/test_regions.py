from griductive.models import Puzzle, RegionSpec
from griductive.regions import resolve_region


def test_required_region_types_resolve_in_deterministic_order():
    puzzle = Puzzle.load("puzzles/4x4_easy_training.json")
    assert resolve_region(RegionSpec(type="ROW", row=2), puzzle.cells, 4) == ("A2", "B2", "C2", "D2")
    assert resolve_region(RegionSpec(type="COLUMN", column="B"), puzzle.cells, 4) == ("B1", "B2", "B3", "B4")
    assert resolve_region(RegionSpec(type="NEIGHBORS", center="A1"), puzzle.cells, 4) == ("B1", "A2", "B2")
    assert resolve_region(RegionSpec(type="NEIGHBORS", center="B2"), puzzle.cells, 4) == (
        "A1", "B1", "C1", "A2", "C2", "A3", "B3", "C3",
    )
    assert resolve_region(
        RegionSpec(type="EXPLICIT", cells=("D4", "A1")), puzzle.cells, 4
    ) == ("D4", "A1")


def test_advanced_region_expressions():
    puzzle = Puzzle.load("puzzles/4x4_medium_links.json")
    assert resolve_region(RegionSpec(type="CORNERS"), puzzle.cells, 4) == ("A1", "D1", "A4", "D4")
    assert resolve_region(RegionSpec(type="EDGES"), puzzle.cells, 4) == (
        "A1", "B1", "C1", "D1", "A2", "D2", "A3", "D3", "A4", "B4", "C4", "D4",
    )
    assert resolve_region(RegionSpec(type="BETWEEN", person="A1", other="A4"), puzzle.cells, 4) == ("A2", "A3")
    assert resolve_region(
        RegionSpec(type="COMMON_NEIGHBORS", person="A1", other="C1"), puzzle.cells, 4
    ) == ("B1", "B2")
    assert resolve_region(
        RegionSpec(type="DIRECTIONAL", center="B2", direction="ABOVE"), puzzle.cells, 4
    ) == ("B1",)
    assert resolve_region(
        RegionSpec(
            type="INTERSECTION",
            regions=(RegionSpec(type="NEIGHBORS", center="B2"), RegionSpec(type="ROW", row=1)),
        ), puzzle.cells, 4
    ) == ("A1", "B1", "C1")
