from __future__ import annotations

from .models import CellInfo, RegionSpec, PuzzleValidationError


def resolve_region(region: RegionSpec, cells: tuple[CellInfo, ...], size: int) -> tuple[str, ...]:
    by_id = {cell.id: cell for cell in cells}
    kind = region.type.upper()
    if kind == "ROW":
        if not isinstance(region.row, int) or not 1 <= region.row <= size:
            raise PuzzleValidationError(f"Invalid row: {region.row}")
        result = [cell.id for cell in cells if cell.row == region.row]
    elif kind == "COLUMN":
        column = region.column
        if isinstance(column, str):
            column = ord(column.upper()) - 64
        if not isinstance(column, int) or not 1 <= column <= size:
            raise PuzzleValidationError(f"Invalid column: {region.column}")
        result = [cell.id for cell in cells if cell.column == column]
    elif kind == "NEIGHBORS":
        center = str(region.center or "").upper()
        if center not in by_id:
            raise PuzzleValidationError(f"Unknown neighbor center: {center}")
        origin = by_id[center]
        result = [
            cell.id for cell in cells
            if cell.id != center
            and abs(cell.row - origin.row) <= 1
            and abs(cell.column - origin.column) <= 1
        ]
    elif kind == "EXPLICIT":
        result = [str(cell_id).upper() for cell_id in region.cells]
        if not result:
            raise PuzzleValidationError("Explicit region cannot be empty")
        if len(result) != len(set(result)):
            raise PuzzleValidationError("Explicit region contains duplicate cells")
        unknown = [cell_id for cell_id in result if cell_id not in by_id]
        if unknown:
            raise PuzzleValidationError(f"Unknown cells in region: {', '.join(unknown)}")
    elif kind in {"WHOLE", "WHOLE_GRID"}:
        result = [cell.id for cell in cells]
    elif kind == "CORNERS":
        result = [
            cell.id for cell in cells
            if cell.row in {1, size} and cell.column in {1, size}
        ]
    elif kind == "EDGES":
        result = [
            cell.id for cell in cells
            if cell.row in {1, size} or cell.column in {1, size}
        ]
    elif kind == "BETWEEN":
        first_id = str(region.person or "").upper()
        second_id = str(region.other or "").upper()
        if first_id not in by_id or second_id not in by_id or first_id == second_id:
            raise PuzzleValidationError(f"Invalid BETWEEN endpoints: {first_id}, {second_id}")
        first, second = by_id[first_id], by_id[second_id]
        row_delta = second.row - first.row
        column_delta = second.column - first.column
        straight = row_delta == 0 or column_delta == 0 or abs(row_delta) == abs(column_delta)
        if not straight:
            raise PuzzleValidationError("BETWEEN endpoints must share a row, column, or diagonal")
        steps = max(abs(row_delta), abs(column_delta))
        if steps <= 1:
            raise PuzzleValidationError("BETWEEN endpoints must have at least one cell between them")
        row_step = 0 if row_delta == 0 else (1 if row_delta > 0 else -1)
        column_step = 0 if column_delta == 0 else (1 if column_delta > 0 else -1)
        coordinates = {
            (first.row + row_step * step, first.column + column_step * step)
            for step in range(1, steps)
        }
        result = [cell.id for cell in cells if (cell.row, cell.column) in coordinates]
    elif kind == "COMMON_NEIGHBORS":
        first_id = str(region.person or "").upper()
        second_id = str(region.other or "").upper()
        if first_id not in by_id or second_id not in by_id or first_id == second_id:
            raise PuzzleValidationError(f"Invalid COMMON_NEIGHBORS people: {first_id}, {second_id}")
        first, second = by_id[first_id], by_id[second_id]
        result = [
            cell.id for cell in cells
            if cell.id not in {first_id, second_id}
            and abs(cell.row - first.row) <= 1 and abs(cell.column - first.column) <= 1
            and abs(cell.row - second.row) <= 1 and abs(cell.column - second.column) <= 1
        ]
    elif kind == "DIRECTIONAL":
        center = str(region.center or region.person or "").upper()
        if center not in by_id:
            raise PuzzleValidationError(f"Unknown directional center: {center}")
        direction = str(region.direction or "").upper()
        offsets = {"ABOVE": (-1, 0), "BELOW": (1, 0), "LEFT": (0, -1), "RIGHT": (0, 1)}
        if direction not in offsets:
            raise PuzzleValidationError(f"Invalid direction: {direction}")
        origin = by_id[center]
        dr, dc = offsets[direction]
        result = [cell.id for cell in cells if (cell.row, cell.column) == (origin.row + dr, origin.column + dc)]
        if not result:
            raise PuzzleValidationError(f"{center} has no cell directly {direction.lower()}")
    elif kind == "PROFESSION":
        if not region.profession:
            raise PuzzleValidationError("PROFESSION region requires a profession")
        result = [cell.id for cell in cells if cell.profession.casefold() == region.profession.casefold()]
    elif kind in {"INTERSECTION", "UNION"}:
        if len(region.regions) < 2:
            raise PuzzleValidationError(f"{kind} requires at least two child regions")
        resolved = [resolve_region(child, cells, size) for child in region.regions]
        if kind == "INTERSECTION":
            allowed = set(resolved[0]).intersection(*(set(item) for item in resolved[1:]))
        else:
            allowed = set().union(*(set(item) for item in resolved))
        result = [cell.id for cell in cells if cell.id in allowed]
    else:
        raise PuzzleValidationError(f"Unsupported region type: {kind}")
    if not result:
        raise PuzzleValidationError(f"Region {kind} resolved to no cells")
    return tuple(result)


def referenced_cells(region: RegionSpec | None, cells: tuple[CellInfo, ...], size: int) -> tuple[str, ...]:
    return resolve_region(region, cells, size) if region else ()
