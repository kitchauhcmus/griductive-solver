from __future__ import annotations

from collections import deque
from html import escape

from .models import Clue, PublicGameState, Puzzle, PuzzleValidationError, RegionSpec, Status
from .regions import resolve_region

CORE_TYPES = {"FACT", "SAME", "DIFFERENT", "EXACTLY", "AT_LEAST", "AT_MOST"}
EXTENSION_TYPES = {
    "PARITY", "COUNT_COMPARE", "ALL_OF", "CONNECTED", "GROUP_MOST", "GROUP_ONLY",
    "INCLUDED_COUNT", "OVERLAP_COUNT", "CONNECTED_COUNT",
}
ALL_TYPES = CORE_TYPES | EXTENSION_TYPES
GROUP_KINDS = {"ROW", "COLUMN", "PROFESSION"}


def validate_puzzle(puzzle: Puzzle, *, check_truth: bool = True) -> None:
    expected = puzzle.size * puzzle.size
    ids = [cell.id for cell in puzzle.cells]
    expected_ids = [
        f"{chr(65 + column)}{row}"
        for row in range(1, puzzle.size + 1)
        for column in range(puzzle.size)
    ]
    errors: list[str] = []
    if puzzle.size < 1:
        errors.append("size must be positive")
    if len(ids) != expected:
        errors.append(f"expected {expected} cells, got {len(ids)}")
    if len(ids) != len(set(ids)):
        errors.append("cell IDs must be unique")
    if ids != expected_ids:
        errors.append("cells must use deterministic row-major IDs (A1, B1, ..., A2, ...)")
    names = [cell.name.casefold() for cell in puzzle.cells]
    if names != sorted(names):
        errors.append("characters must be ordered alphabetically by display name")
    if set(puzzle.solution) != set(ids):
        errors.append("solution must contain exactly one status for every cell")
    if set(puzzle.clues) != set(ids):
        errors.append("clues must contain exactly one clue for every cell")
    if not puzzle.initially_revealed:
        errors.append("at least one card must be initially revealed")
    if len(puzzle.initially_revealed) != len(set(puzzle.initially_revealed)):
        errors.append("initially revealed cells must be unique")
    unknown_initial = set(puzzle.initially_revealed) - set(ids)
    if unknown_initial:
        errors.append(f"unknown initially revealed cells: {sorted(unknown_initial)}")
    if errors:
        raise PuzzleValidationError("; ".join(errors))
    clue_ids: set[str] = set()
    for owner, clue in puzzle.clues.items():
        for clue_id in _all_clue_ids(clue):
            if clue_id in clue_ids:
                raise PuzzleValidationError(f"Duplicate clue id: {clue_id}")
            clue_ids.add(clue_id)
        validate_clue(clue, puzzle)
        if check_truth and not evaluate_clue(clue, {k: v.boolean for k, v in puzzle.solution.items()}, puzzle):
            raise PuzzleValidationError(f"Clue {clue.id} owned by {owner} is false under hidden solution")


def _all_clue_ids(clue: Clue) -> tuple[str, ...]:
    return (clue.id,) + tuple(item for child in clue.children for item in _all_clue_ids(child))


def validate_clue(clue: Clue, puzzle: Puzzle) -> None:
    if clue.type not in ALL_TYPES:
        raise PuzzleValidationError(f"Unsupported clue type: {clue.type}")
    ids = {cell.id for cell in puzzle.cells}
    if clue.type == "FACT":
        if clue.person not in ids or clue.status is None:
            raise PuzzleValidationError(f"Invalid FACT clue: {clue.id}")
    elif clue.type in {"SAME", "DIFFERENT"}:
        if clue.person not in ids or clue.other not in ids or clue.person == clue.other:
            raise PuzzleValidationError(f"Invalid binary clue: {clue.id}")
    elif clue.type in {"EXACTLY", "AT_LEAST", "AT_MOST"}:
        members = _validated_region(clue, puzzle)
        if not isinstance(clue.k, int) or not 0 <= clue.k <= len(members):
            raise PuzzleValidationError(f"Invalid k in clue {clue.id}")
    elif clue.type == "INCLUDED_COUNT":
        members = _validated_region(clue, puzzle)
        if clue.person not in members or not isinstance(clue.k, int) or not 0 <= clue.k <= len(members):
            raise PuzzleValidationError(f"Invalid INCLUDED_COUNT clue: {clue.id}")
    elif clue.type == "OVERLAP_COUNT":
        total_members = _validated_region(clue, puzzle)
        overlap_members = resolve_region(clue.left, puzzle.cells, puzzle.size) if clue.left else ()
        if (
            not isinstance(clue.k, int) or not 0 <= clue.k <= len(total_members)
            or not isinstance(clue.overlap_k, int) or not 0 <= clue.overlap_k <= len(overlap_members)
            or not set(overlap_members) <= set(total_members)
        ):
            raise PuzzleValidationError(f"Invalid OVERLAP_COUNT clue: {clue.id}")
    elif clue.type == "CONNECTED_COUNT":
        members = _validated_region(clue, puzzle)
        if not isinstance(clue.k, int) or not 0 <= clue.k <= len(members):
            raise PuzzleValidationError(f"Invalid CONNECTED_COUNT clue: {clue.id}")
    elif clue.type == "PARITY":
        _validated_region(clue, puzzle)
        if clue.parity not in {"EVEN", "ODD"}:
            raise PuzzleValidationError(f"Invalid PARITY clue: {clue.id}")
    elif clue.type == "COUNT_COMPARE":
        if clue.left is None or clue.right is None or clue.operator not in {"EQ", "NE", "LT", "LE", "GT", "GE"}:
            raise PuzzleValidationError(f"Invalid COUNT_COMPARE clue: {clue.id}")
        resolve_region(clue.left, puzzle.cells, puzzle.size)
        resolve_region(clue.right, puzzle.cells, puzzle.size)
    elif clue.type == "ALL_OF":
        if len(clue.children) < 2:
            raise PuzzleValidationError(f"ALL_OF requires at least two child clues: {clue.id}")
        for child in clue.children:
            if child.type == "ALL_OF":
                raise PuzzleValidationError("Nested ALL_OF is unnecessary and not supported")
            validate_clue(child, puzzle)
    elif clue.type == "CONNECTED":
        _validated_region(clue, puzzle)
    elif clue.type in {"GROUP_MOST", "GROUP_ONLY"}:
        groups = resolve_groups(clue.group_kind, puzzle)
        key = normalize_group_key(clue.group_kind, clue.group)
        if key not in groups:
            raise PuzzleValidationError(f"Unknown target group {clue.group!r} for {clue.group_kind}")
        if clue.type == "GROUP_ONLY" and (not isinstance(clue.k, int) or not 0 <= clue.k <= len(groups[key])):
            raise PuzzleValidationError(f"GROUP_ONLY requires a valid k: {clue.id}")


def _validated_region(clue: Clue, puzzle: Puzzle) -> tuple[str, ...]:
    if clue.region is None:
        raise PuzzleValidationError(f"Missing region: {clue.id}")
    return resolve_region(clue.region, puzzle.cells, puzzle.size)


def normalize_group_key(kind: str | None, key) -> str | int:
    kind = str(kind or "").upper()
    if kind == "ROW":
        try:
            return int(key)
        except (TypeError, ValueError) as exc:
            raise PuzzleValidationError(f"Invalid row group: {key}") from exc
    if kind == "COLUMN":
        if isinstance(key, int):
            return chr(64 + key)
        return str(key or "").upper()
    if kind == "PROFESSION":
        return str(key or "").casefold()
    raise PuzzleValidationError(f"Unsupported group kind: {kind}")


def resolve_groups(kind: str | None, puzzle: Puzzle | PublicGameState) -> dict[str | int, tuple[str, ...]]:
    kind = str(kind or "").upper()
    if kind not in GROUP_KINDS:
        raise PuzzleValidationError(f"Unsupported group kind: {kind}")
    groups: dict[str | int, list[str]] = {}
    for cell in puzzle.cells:
        if kind == "ROW":
            key: str | int = cell.row
        elif kind == "COLUMN":
            key = chr(64 + cell.column)
        else:
            key = cell.profession.casefold()
        groups.setdefault(key, []).append(cell.id)
    return {key: tuple(value) for key, value in groups.items()}


def _compare(left: int, right: int, operator: str) -> bool:
    return {
        "EQ": left == right, "NE": left != right,
        "LT": left < right, "LE": left <= right,
        "GT": left > right, "GE": left >= right,
    }[operator]


def _count(members: tuple[str, ...], assignment: dict[str, bool], status: Status) -> int:
    target = status.boolean
    return sum(assignment[cell_id] == target for cell_id in members)


def evaluate_clue(clue: Clue, assignment: dict[str, bool], puzzle: Puzzle) -> bool:
    """Direct semantic oracle. It deliberately does not use the CNF encoder."""
    if clue.type == "FACT":
        return assignment[clue.person] == clue.status.boolean  # type: ignore[index,union-attr]
    if clue.type == "SAME":
        return assignment[clue.person] == assignment[clue.other]  # type: ignore[index]
    if clue.type == "DIFFERENT":
        return assignment[clue.person] != assignment[clue.other]  # type: ignore[index]
    if clue.type in {"EXACTLY", "AT_LEAST", "AT_MOST", "PARITY", "INCLUDED_COUNT", "CONNECTED_COUNT"}:
        members = resolve_region(clue.region, puzzle.cells, puzzle.size)  # type: ignore[arg-type]
        count = _count(members, assignment, clue.target_status)
        if clue.type == "EXACTLY":
            return count == clue.k
        if clue.type == "AT_LEAST":
            return count >= clue.k  # type: ignore[operator]
        if clue.type == "AT_MOST":
            return count <= clue.k  # type: ignore[operator]
        if clue.type == "PARITY":
            return count % 2 == (1 if clue.parity == "ODD" else 0)
        if clue.type == "INCLUDED_COUNT":
            return count == clue.k and assignment[clue.person] == clue.target_status.boolean  # type: ignore[index]
        selected = {cell_id for cell_id in members if assignment[cell_id] == clue.target_status.boolean}
        return count == clue.k and is_connected(selected, puzzle)
    if clue.type == "OVERLAP_COUNT":
        total = resolve_region(clue.region, puzzle.cells, puzzle.size)  # type: ignore[arg-type]
        overlap = resolve_region(clue.left, puzzle.cells, puzzle.size)  # type: ignore[arg-type]
        return (
            _count(total, assignment, clue.target_status) == clue.k
            and _count(overlap, assignment, clue.target_status) == clue.overlap_k
        )
    if clue.type == "COUNT_COMPARE":
        left = resolve_region(clue.left, puzzle.cells, puzzle.size)  # type: ignore[arg-type]
        right = resolve_region(clue.right, puzzle.cells, puzzle.size)  # type: ignore[arg-type]
        return _compare(
            _count(left, assignment, clue.target_status),
            _count(right, assignment, clue.target_status),
            clue.operator or "EQ",
        )
    if clue.type == "ALL_OF":
        return all(evaluate_clue(child, assignment, puzzle) for child in clue.children)
    if clue.type == "CONNECTED":
        members = resolve_region(clue.region, puzzle.cells, puzzle.size)  # type: ignore[arg-type]
        selected = {cell_id for cell_id in members if assignment[cell_id] == clue.target_status.boolean}
        return is_connected(selected, puzzle)
    if clue.type in {"GROUP_MOST", "GROUP_ONLY"}:
        groups = resolve_groups(clue.group_kind, puzzle)
        target_key = normalize_group_key(clue.group_kind, clue.group)
        counts = {key: _count(members, assignment, clue.target_status) for key, members in groups.items()}
        if clue.type == "GROUP_MOST":
            return all(counts[target_key] > count for key, count in counts.items() if key != target_key)
        return counts[target_key] == clue.k and all(
            count != clue.k for key, count in counts.items() if key != target_key
        )
    raise PuzzleValidationError(f"Unsupported clue type: {clue.type}")


def is_connected(selected: set[str], puzzle: Puzzle) -> bool:
    """Four-direction connectivity; the empty and singleton sets are connected."""
    if len(selected) <= 1:
        return True
    by_id = {cell.id: cell for cell in puzzle.cells}
    first = next(iter(selected))
    visited = {first}
    queue = deque([first])
    while queue:
        current = by_id[queue.popleft()]
        for candidate in selected - visited:
            other = by_id[candidate]
            if abs(current.row - other.row) + abs(current.column - other.column) == 1:
                visited.add(candidate)
                queue.append(candidate)
    return visited == selected


def clue_referenced_cells(clue: Clue, puzzle: Puzzle | PublicGameState) -> tuple[str, ...]:
    referenced: set[str] = set()
    if clue.person:
        referenced.add(clue.person)
    if clue.other:
        referenced.add(clue.other)
    for region in (clue.region, clue.left, clue.right):
        if region:
            referenced.update(resolve_region(region, puzzle.cells, puzzle.size))
    for child in clue.children:
        referenced.update(clue_referenced_cells(child, puzzle))
    if clue.type in {"GROUP_MOST", "GROUP_ONLY"}:
        groups = resolve_groups(clue.group_kind, puzzle)
        referenced.update(groups[normalize_group_key(clue.group_kind, clue.group)])
    order = {cell.id: index for index, cell in enumerate(puzzle.cells)}
    return tuple(sorted(referenced, key=order.__getitem__))


def clue_neighborhood_centers(clue: Clue) -> tuple[str, ...]:
    """People whose complete neighborhoods help visually review a clue."""
    centers: list[str] = []

    def add(cell_id: str | None) -> None:
        if cell_id and cell_id not in centers:
            centers.append(cell_id)

    def visit_region(region) -> None:
        if region is None:
            return
        if region.type == "NEIGHBORS":
            add(region.center)
        elif region.type == "COMMON_NEIGHBORS":
            add(region.person)
            add(region.other)
        for child_region in region.regions:
            visit_region(child_region)

    for region in (clue.region, clue.left, clue.right):
        visit_region(region)
    for child in clue.children:
        for cell_id in clue_neighborhood_centers(child):
            add(cell_id)
    return tuple(centers)


def clue_review_cells(clue: Clue, puzzle: Puzzle | PublicGameState) -> tuple[str, ...]:
    """Highlight logical references plus full neighborhoods used by a clue."""
    referenced = set(clue_referenced_cells(clue, puzzle))
    for center in clue_neighborhood_centers(clue):
        referenced.add(center)
        referenced.update(resolve_region(
            RegionSpec(type="NEIGHBORS", center=center), puzzle.cells, puzzle.size
        ))
    order = {cell.id: index for index, cell in enumerate(puzzle.cells)}
    return tuple(sorted(referenced, key=order.__getitem__))


def _display_name(cell_id: str | None, puzzle: Puzzle | PublicGameState | None) -> str:
    if puzzle is not None:
        cell = next((item for item in puzzle.cells if item.id == cell_id), None)
        if cell is not None:
            return cell.name
    return str(cell_id)


def _named_references(clue: Clue) -> tuple[str, ...]:
    references: list[str] = []

    def add(cell_id: str | None) -> None:
        if cell_id and cell_id not in references:
            references.append(cell_id)

    add(clue.person)
    add(clue.other)
    for region in (clue.region, clue.left, clue.right):
        if region is None:
            continue
        add(region.center)
        add(region.person)
        add(region.other)
        for child in region.regions:
            add(child.center)
            add(child.person)
            add(child.other)
    for child in clue.children:
        for cell_id in _named_references(child):
            add(cell_id)
    return tuple(references)


def describe_clue_html(clue: Clue, puzzle: Puzzle | PublicGameState) -> str:
    """Natural clue text with clickable links for explicitly named people."""
    rendered = escape(describe_clue(clue, puzzle))
    names = sorted(
        ((_display_name(cell_id, puzzle), cell_id) for cell_id in _named_references(clue)),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for name, cell_id in names:
        safe_name = escape(name)
        rendered = rendered.replace(
            safe_name,
            f'<a href="{escape(cell_id)}" style="color:#7DCBFF;text-decoration:none;font-weight:800;">{safe_name}</a>',
        )
    return rendered


def describe_clue(clue: Clue, puzzle: Puzzle | PublicGameState | None = None) -> str:
    if clue.type == "FACT":
        return f"{_display_name(clue.person, puzzle)} is {clue.status.value.lower()}."  # type: ignore[union-attr]
    if clue.type == "SAME":
        return f"{_display_name(clue.person, puzzle)} and {_display_name(clue.other, puzzle)} have the same status."
    if clue.type == "DIFFERENT":
        return f"{_display_name(clue.person, puzzle)} and {_display_name(clue.other, puzzle)} have different statuses."
    subject = clue.target_status.value.lower() + "s"
    status_word = clue.target_status.value.lower()
    if clue.type in {"EXACTLY", "AT_LEAST", "AT_MOST"}:
        phrase = {"EXACTLY": "Exactly", "AT_LEAST": "At least", "AT_MOST": "At most"}[clue.type]
        if clue.type == "EXACTLY" and clue.region and clue.region.type == "NEIGHBORS":
            return f"{_display_name(clue.region.center, puzzle)} has exactly {clue.k} {status_word} neighbors."
        if clue.type == "EXACTLY" and clue.region and clue.region.type in {"WHOLE", "WHOLE_GRID"}:
            return f"There are {clue.k} {subject} in total."
        count_subject = status_word if clue.k == 1 else subject
        verb = "is" if clue.k == 1 else "are"
        return f"{phrase} {clue.k} {count_subject} {verb} in {describe_region(clue.region, puzzle)}."
    if clue.type == "PARITY":
        return f"An {clue.parity.lower()} number of {subject} are in {describe_region(clue.region, puzzle)}."  # type: ignore[union-attr]
    if clue.type == "INCLUDED_COUNT":
        if clue.region and clue.region.type == "NEIGHBORS":
            return f"{_display_name(clue.person, puzzle)} is one of {_display_name(clue.region.center, puzzle)}'s {clue.k} {status_word} neighbors."
        return f"{_display_name(clue.person, puzzle)} is one of the {clue.k} {subject} in {describe_region(clue.region, puzzle)}."
    if clue.type == "OVERLAP_COUNT":
        if clue.region and clue.region.type == "NEIGHBORS" and clue.left and clue.left.type == "COMMON_NEIGHBORS":
            return f"Exactly {clue.overlap_k} of {_display_name(clue.region.center, puzzle)}'s {clue.k} {status_word} neighbors also neighbor {_display_name(clue.left.other, puzzle)}."
        return f"Exactly {clue.overlap_k} of the {clue.k} {subject} in {describe_region(clue.region, puzzle)} are also in {describe_region(clue.left, puzzle)}."
    if clue.type == "CONNECTED_COUNT":
        return f"The {clue.k} {subject} in {describe_region(clue.region, puzzle)} are connected edge-to-edge."
    if clue.type == "COUNT_COMPARE":
        operators = {"EQ": "equal to", "NE": "different from", "LT": "less than", "LE": "at most", "GT": "more than", "GE": "at least"}
        if clue.left and clue.right and clue.left.type == clue.right.type == "NEIGHBORS":
            neighbor_phrases = {
                "EQ": "the same number of", "NE": "a different number of",
                "LT": "fewer", "LE": "no more", "GT": "more", "GE": "at least as many",
            }
            comparison = neighbor_phrases.get(clue.operator, str(clue.operator))
            connector = "as" if clue.operator in {"EQ", "GE"} else "than"
            return f"{_display_name(clue.left.center, puzzle)} has {comparison} {status_word} neighbors {connector} {_display_name(clue.right.center, puzzle)}."
        return f"The {subject} count in {describe_region(clue.left, puzzle)} is {operators.get(clue.operator, clue.operator)} the count in {describe_region(clue.right, puzzle)}."
    if clue.type == "ALL_OF":
        return " Both statements hold: " + " ".join(f"({describe_clue(child, puzzle)})" for child in clue.children)
    if clue.type == "CONNECTED":
        return f"All {subject} in {describe_region(clue.region, puzzle)} are connected edge-to-edge."
    if clue.type == "GROUP_MOST":
        return f"{clue.group_kind.title()} {clue.group} has strictly the most {subject}."
    if clue.type == "GROUP_ONLY":
        return f"{clue.group_kind.title()} {clue.group} is the only {clue.group_kind.lower()} with exactly {clue.k} {subject}."
    return clue.type


def describe_region(region, puzzle: Puzzle | PublicGameState | None = None) -> str:
    if region.type == "ROW":
        return f"row {region.row}"
    if region.type == "COLUMN":
        return f"column {region.column}"
    if region.type == "NEIGHBORS":
        return f"the neighbors of {_display_name(region.center, puzzle)}"
    if region.type == "EXPLICIT":
        return "{" + ", ".join(region.cells) + "}"
    if region.type in {"WHOLE", "WHOLE_GRID"}:
        return "the whole grid"
    if region.type == "CORNERS":
        return "the corners"
    if region.type == "EDGES":
        return "the outer edge"
    if region.type == "BETWEEN":
        return f"the cells between {_display_name(region.person, puzzle)} and {_display_name(region.other, puzzle)}"
    if region.type == "COMMON_NEIGHBORS":
        return f"the common neighbors of {_display_name(region.person, puzzle)} and {_display_name(region.other, puzzle)}"
    if region.type == "DIRECTIONAL":
        return f"the cell directly {region.direction.lower()} of {_display_name(region.center or region.person, puzzle)}"
    if region.type == "PROFESSION":
        return f"the {region.profession} group"
    if region.type == "UNION" and region.regions and all(child.type == "ROW" for child in region.regions):
        return "rows " + " and ".join(str(child.row) for child in region.regions)
    joiner = " intersected with " if region.type == "INTERSECTION" else " combined with "
    return joiner.join(describe_region(child, puzzle) for child in region.regions)
