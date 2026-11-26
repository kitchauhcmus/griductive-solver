from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
import json

from .roster import SQUADS


class Status(str, Enum):
    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"

    @property
    def boolean(self) -> bool:
        return self is Status.CRIMINAL

    @classmethod
    def from_bool(cls, value: bool) -> "Status":
        return cls.CRIMINAL if value else cls.INNOCENT


class VerdictResult(str, Enum):
    ACCEPTED = "ACCEPTED"
    NOT_PROVABLE = "NOT_PROVABLE"
    CONTRADICTED = "CONTRADICTED"
    INCONSISTENT = "INCONSISTENT"
    ALREADY_SOLVED = "ALREADY_SOLVED"


class RunStatus(str, Enum):
    READY = "READY"
    SOLVED = "SOLVED"
    STUCK = "STUCK"
    INCONSISTENT = "INCONSISTENT"
    STEP_LIMIT = "STEP_LIMIT"


@dataclass(frozen=True)
class CellInfo:
    id: str
    name: str
    profession: str
    row: int
    column: int
    slug: str = ""
    ovr: int | None = None
    club: str = ""
    nation: str = ""
    tier: str = ""
    shirt_number: int | None = None


@dataclass(frozen=True)
class RegionSpec:
    type: str
    row: int | None = None
    column: str | int | None = None
    center: str | None = None
    cells: tuple[str, ...] = ()
    person: str | None = None
    other: str | None = None
    direction: str | None = None
    profession: str | None = None
    regions: tuple["RegionSpec", ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RegionSpec":
        return cls(
            type=str(data.get("type", "")).upper(),
            row=data.get("row", data.get("index")),
            column=data.get("column", data.get("index")),
            center=data.get("center"),
            cells=tuple(data.get("cells", ())),
            person=data.get("person"),
            other=data.get("other"),
            direction=str(data["direction"]).upper() if data.get("direction") else None,
            profession=data.get("profession"),
            regions=tuple(cls.from_dict(item) for item in data.get("regions", ())),
        )


@dataclass(frozen=True)
class Clue:
    id: str
    type: str
    person: str | None = None
    other: str | None = None
    status: Status | None = None
    k: int | None = None
    overlap_k: int | None = None
    region: RegionSpec | None = None
    left: RegionSpec | None = None
    right: RegionSpec | None = None
    operator: str | None = None
    parity: str | None = None
    target_status: Status = Status.CRIMINAL
    children: tuple["Clue", ...] = ()
    group_kind: str | None = None
    group: str | int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], default_id: str) -> "Clue":
        status = data.get("status")
        target_status = data.get("target_status", "CRIMINAL")
        return cls(
            id=str(data.get("id", default_id)),
            type=str(data.get("type", "")).upper(),
            person=data.get("person"),
            other=data.get("other"),
            status=Status(str(status).upper()) if status is not None else None,
            k=data.get("k"),
            overlap_k=data.get("overlap_k"),
            region=RegionSpec.from_dict(data["region"]) if data.get("region") else None,
            left=RegionSpec.from_dict(data["left"]) if data.get("left") else None,
            right=RegionSpec.from_dict(data["right"]) if data.get("right") else None,
            operator=str(data["operator"]).upper() if data.get("operator") else None,
            parity=str(data["parity"]).upper() if data.get("parity") else None,
            target_status=Status(str(target_status).upper()),
            children=tuple(
                cls.from_dict(child, f"{default_id}_part_{index + 1}")
                for index, child in enumerate(data.get("clues", data.get("children", ())))
            ),
            group_kind=str(data["group_kind"]).upper() if data.get("group_kind") else None,
            group=data.get("group"),
        )


@dataclass(frozen=True)
class PublicGameState:
    title: str
    size: int
    cells: tuple[CellInfo, ...]
    revealed_clues: tuple[Clue, ...]
    proved: dict[str, Status]


@dataclass
class Puzzle:
    title: str
    size: int
    cells: tuple[CellInfo, ...]
    solution: dict[str, Status]
    clues: dict[str, Clue]
    initially_revealed: tuple[str, ...]
    source: Path | None = None

    @classmethod
    def load(cls, path: str | Path) -> "Puzzle":
        source = Path(path)
        with source.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        puzzle = cls.from_dict(data)
        puzzle.source = source
        return puzzle

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Puzzle":
        size = int(data["size"])
        raw_cells = data.get("cells")
        if data.get("roster") == "football":
            if size not in SQUADS:
                raise ValueError("Football squads support 3x3, 4x4 and 5x5 boards.")
            raw_cells = [
                {
                    "id": f"{chr(65 + index % size)}{index // size + 1}",
                    "name": player.name, "slug": player.slug, "profession": player.pos,
                    "ovr": player.ovr, "club": player.club, "nation": player.nation,
                    "tier": player.tier, "shirt_number": player.number,
                }
                for index, player in enumerate(SQUADS[size])
            ]
        if raw_cells is None:
            raw_cells = []
            names = data.get("names", {})
            professions = data.get("professions", {})
            for row in range(1, size + 1):
                for col in range(size):
                    cell_id = f"{chr(65 + col)}{row}"
                    display_index = len(raw_cells) + 1
                    raw_cells.append({
                        "id": cell_id,
                        "name": names.get(cell_id, f"Person {display_index:02d}"),
                        "profession": professions.get(cell_id, "Suspect"),
                    })
        cells: list[CellInfo] = []
        for index, item in enumerate(raw_cells):
            cell_id = str(item["id"]).upper()
            cells.append(CellInfo(
                id=cell_id,
                name=str(item.get("name", cell_id)),
                profession=str(item.get("profession", "Suspect")),
                row=index // size + 1,
                column=index % size + 1,
                slug=item.get("slug", ""), ovr=item.get("ovr"),
                club=item.get("club", ""), nation=item.get("nation", ""),
                tier=item.get("tier", ""), shirt_number=item.get("shirt_number"),
            ))
        solution = {
            str(cell_id).upper(): Status(str(status).upper())
            for cell_id, status in data["solution"].items()
        }
        clues = {
            str(owner).upper(): Clue.from_dict(clue, f"clue_{str(owner).upper()}")
            for owner, clue in data["clues"].items()
        }
        return cls(
            title=str(data.get("title", "Untitled Griductive Puzzle")),
            size=size,
            cells=tuple(cells),
            solution=solution,
            clues=clues,
            initially_revealed=tuple(str(x).upper() for x in data.get("initially_revealed", ())),
        )


@dataclass
class DeductionStep:
    step: int
    active_clues: tuple[str, ...]
    sat_queries: tuple[str, ...]
    cell_id: str
    verdict: Status
    revealed_clue: str


@dataclass
class Submission:
    result: VerdictResult
    cell_id: str
    submitted: Status
    forced: Status | None = None
    revealed_clue: Clue | None = None
    message: str = ""


class PuzzleValidationError(ValueError):
    pass
