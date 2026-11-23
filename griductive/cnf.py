from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from .clues import normalize_group_key, resolve_groups, validate_clue
from .models import CellInfo, Clue, PublicGameState, PuzzleValidationError, Status
from .regions import resolve_region

Clause = tuple[int, ...]


@dataclass(frozen=True)
class CNFFormula:
    clauses: tuple[Clause, ...]
    primary_variables: dict[str, int]
    auxiliary_variables: dict[str, int]

    @property
    def variable_count(self) -> int:
        return len(self.primary_variables) + len(self.auxiliary_variables)

    @property
    def clause_count(self) -> int:
        return len(self.clauses)


class CNFEncoder:
    """Reusable deterministic encoder for structured Griductive clues."""

    def __init__(self, size: int, cells: tuple[CellInfo, ...]):
        if type(size) is not int or size < 1:
            raise PuzzleValidationError("CNF board size must be a positive integer")
        expected = [f"{chr(65 + column)}{row}" for row in range(1, size + 1) for column in range(size)]
        if [cell.id for cell in cells] != expected:
            raise PuzzleValidationError("CNF cells must use a positive square size and row-major IDs")
        if any(cell.row != index // size + 1 or cell.column != index % size + 1 for index, cell in enumerate(cells)):
            raise PuzzleValidationError("CNF cell coordinates must match their row-major IDs")
        self.size = size
        self.cells = cells
        self.primary = {cell.id: index + 1 for index, cell in enumerate(cells)}
        self.auxiliary: dict[str, int] = {}
        self._cardinality_serial = 0
        self._parity_serial = 0
        self._validation_state = PublicGameState("", size, cells, (), {})

    def _begin_formula(self) -> None:
        """Auxiliaries belong to one formula, not to every formula this instance has built."""
        self.auxiliary = {}
        self._cardinality_serial = 0
        self._parity_serial = 0

    @staticmethod
    def _check_clue_ids(clues: tuple[Clue, ...] | list[Clue]) -> None:
        seen: set[str] = set()

        def visit(clue: Clue) -> None:
            if clue.id in seen:
                raise PuzzleValidationError(f"Duplicate clue id: {clue.id}")
            seen.add(clue.id)
            for child in clue.children:
                visit(child)

        for clue in clues:
            visit(clue)

    def _new_auxiliary(self, name: str) -> int:
        if name in self.auxiliary:
            return self.auxiliary[name]
        variable = len(self.primary) + len(self.auxiliary) + 1
        self.auxiliary[name] = variable
        return variable

    def encode_public_state(self, state: PublicGameState) -> CNFFormula:
        if state.size != self.size or state.cells != self.cells:
            raise PuzzleValidationError("Public state does not match CNF encoder cells")
        for cell_id, status in state.proved.items():
            if cell_id not in self.primary:
                raise PuzzleValidationError(f"Unknown proved cell: {cell_id}")
            if not isinstance(status, Status):
                raise PuzzleValidationError(f"Invalid proved status for {cell_id}")
        self._begin_formula()
        self._check_clue_ids(state.revealed_clues)
        clauses: list[Clause] = []
        for clue in state.revealed_clues:
            clauses.extend(self.encode_clue(clue))
        for cell_id in sorted(state.proved, key=self.primary.__getitem__):
            variable = self.primary[cell_id]
            clauses.append((variable if state.proved[cell_id].boolean else -variable,))
        return CNFFormula(tuple(clauses), dict(self.primary), dict(self.auxiliary))

    def encode_clues(self, clues: tuple[Clue, ...] | list[Clue]) -> CNFFormula:
        self._begin_formula()
        self._check_clue_ids(clues)
        clauses: list[Clause] = []
        for clue in clues:
            clauses.extend(self.encode_clue(clue))
        return CNFFormula(tuple(clauses), dict(self.primary), dict(self.auxiliary))

    def encode_clue(self, clue: Clue) -> list[Clause]:
        validate_clue(clue, self._validation_state)
        self._check_clue_ids((clue,))
        if clue.type == "FACT":
            variable = self._variable(clue.person)
            return [(variable if clue.status and clue.status.boolean else -variable,)]
        if clue.type == "SAME":
            a, b = self._variable(clue.person), self._variable(clue.other)
            return [(-a, b), (a, -b)]
        if clue.type == "DIFFERENT":
            a, b = self._variable(clue.person), self._variable(clue.other)
            return [(a, b), (-a, -b)]
        if clue.type in {"EXACTLY", "AT_LEAST", "AT_MOST"}:
            variables = self._region_literals(clue.region, clue.target_status)
            if clue.type == "EXACTLY":
                return self._cardinality(variables, {clue.k} if clue.k is not None else set())
            if clue.type == "AT_LEAST":
                return self._at_least(variables, clue.k)
            return self._at_most(variables, clue.k)
        if clue.type == "INCLUDED_COUNT":
            variables = self._region_literals(clue.region, clue.target_status)
            person = self._variable(clue.person)
            person_literal = person if clue.target_status is Status.CRIMINAL else -person
            return [(person_literal,)] + self._cardinality(variables, {clue.k} if clue.k is not None else set())
        if clue.type == "OVERLAP_COUNT":
            total = self._region_literals(clue.region, clue.target_status)
            overlap = self._region_literals(clue.left, clue.target_status)
            return self._cardinality(total, {clue.k}) + self._cardinality(overlap, {clue.overlap_k})
        if clue.type == "CONNECTED_COUNT":
            members = resolve_region(clue.region, self.cells, self.size)  # type: ignore[arg-type]
            variables = self._status_literals(members, clue.target_status)
            return self._cardinality(variables, {clue.k}) + self._encode_connected(
                members, clue.target_status, clue.id
            )
        if clue.type == "PARITY":
            variables = self._region_literals(clue.region, clue.target_status)
            return self._encode_parity(variables, clue.parity == "ODD")
        if clue.type == "COUNT_COMPARE":
            left_ids = resolve_region(clue.left, self.cells, self.size)  # type: ignore[arg-type]
            right_ids = resolve_region(clue.right, self.cells, self.size)  # type: ignore[arg-type]
            return self._encode_count_compare(left_ids, right_ids, clue.target_status, clue.operator or "EQ")
        if clue.type == "ALL_OF":
            return [clause for child in clue.children for clause in self.encode_clue(child)]
        if clue.type == "CONNECTED":
            members = resolve_region(clue.region, self.cells, self.size)  # type: ignore[arg-type]
            return self._encode_connected(members, clue.target_status, clue.id)
        if clue.type in {"GROUP_MOST", "GROUP_ONLY"}:
            groups = self._groups(clue.group_kind)
            target_key = self._normalize_group_key(clue.group_kind, clue.group)
            if target_key not in groups:
                raise PuzzleValidationError(f"Unknown target group: {clue.group}")
            target = groups[target_key]
            if clue.type == "GROUP_MOST":
                return [
                    clause
                    for key, members in groups.items() if key != target_key
                    for clause in self._encode_count_compare(target, members, clue.target_status, "GT")
                ]
            clauses = self._cardinality(self._status_literals(target, clue.target_status), {clue.k})
            for key, members in groups.items():
                if key != target_key:
                    literals = self._status_literals(members, clue.target_status)
                    clauses += self._cardinality(literals, set(range(len(literals) + 1)) - {clue.k})
            return clauses
        raise PuzzleValidationError(f"Unsupported clue type: {clue.type}")

    def _variable(self, cell_id: str | None) -> int:
        if cell_id not in self.primary:
            raise PuzzleValidationError(f"Unknown cell: {cell_id}")
        return self.primary[cell_id]

    def _region_literals(self, region, status: Status) -> tuple[int, ...]:
        return self._status_literals(resolve_region(region, self.cells, self.size), status)

    def _status_literals(self, members: tuple[str, ...], status: Status) -> tuple[int, ...]:
        return tuple(
            self.primary[cell_id] if status is Status.CRIMINAL else -self.primary[cell_id]
            for cell_id in members
        )

    def _encode_count_compare(
        self, left_ids: tuple[str, ...], right_ids: tuple[str, ...], status: Status, operator: str
    ) -> list[Clause]:
        if operator not in {"EQ", "NE", "LT", "LE", "GT", "GE"}:
            raise PuzzleValidationError(f"Unsupported count comparison: {operator}")
        left_clauses, left_states = self._count_states(self._status_literals(left_ids, status))
        right_clauses, right_states = self._count_states(self._status_literals(right_ids, status))
        comparisons = {
            "EQ": lambda a, b: a == b, "NE": lambda a, b: a != b,
            "LT": lambda a, b: a < b, "LE": lambda a, b: a <= b,
            "GT": lambda a, b: a > b, "GE": lambda a, b: a >= b,
        }
        allowed = comparisons[operator]
        return left_clauses + right_clauses + [
            (-left_state, -right_state)
            for left_count, left_state in enumerate(left_states)
            for right_count, right_state in enumerate(right_states)
            if not allowed(left_count, right_count)
        ]

    def _encode_parity(self, variables: tuple[int, ...], odd: bool) -> list[Clause]:
        """Chain XOR equivalences; signed literals also count Innocents correctly."""
        self._parity_serial += 1
        clauses: list[Clause] = []
        parity = variables[0]
        for index, literal in enumerate(variables[1:], start=2):
            result = self._new_auxiliary(f"parity:{self._parity_serial}:{index}")
            clauses.extend((
                (parity, literal, -result), (parity, -literal, result),
                (-parity, literal, result), (-parity, -literal, -result),
            ))
            parity = result
        clauses.append((parity if odd else -parity,))
        return clauses

    def _groups(self, kind: str | None) -> dict[str | int, tuple[str, ...]]:
        return resolve_groups(kind, self._validation_state)

    @staticmethod
    def _normalize_group_key(kind: str | None, key) -> str | int:
        return normalize_group_key(kind, key)

    def _encode_connected(self, members: tuple[str, ...], status: Status, clue_id: str) -> list[Clause]:
        """Polynomial four-neighbor reachability encoding with a canonical first root."""
        literals = self._status_literals(members, status)
        by_id = {cell.id: cell for cell in self.cells}
        roots = tuple(self._new_auxiliary(f"{clue_id}:root:{cell_id}") for cell_id in members)
        clauses: list[Clause] = []

        for index, (root, literal) in enumerate(zip(roots, literals)):
            clauses.append((-root, literal))
            for earlier in literals[:index]:
                clauses.append((-root, -earlier))
        for left, right in combinations(roots, 2):
            clauses.append((-left, -right))
        for literal in literals:
            clauses.append((-literal,) + roots)

        previous: list[int] = []
        for index, (cell_id, root) in enumerate(zip(members, roots)):
            reachable = self._new_auxiliary(f"{clue_id}:reach:0:{cell_id}")
            clauses.extend(((-reachable, root), (reachable, -root)))
            previous.append(reachable)

        for depth in range(1, len(members)):
            current: list[int] = []
            for index, cell_id in enumerate(members):
                cell = by_id[cell_id]
                neighbor_indices = [
                    other_index for other_index, other_id in enumerate(members)
                    if abs(cell.row - by_id[other_id].row) + abs(cell.column - by_id[other_id].column) == 1
                ]
                terms: list[int] = []
                for other_index in neighbor_indices:
                    term = self._new_auxiliary(f"{clue_id}:step:{depth}:{cell_id}:{members[other_index]}")
                    literal = literals[index]
                    neighbor_reachable = previous[other_index]
                    clauses.extend((
                        (-term, literal),
                        (-term, neighbor_reachable),
                        (term, -literal, -neighbor_reachable),
                    ))
                    terms.append(term)
                reachable = self._new_auxiliary(f"{clue_id}:reach:{depth}:{cell_id}")
                clauses.append((-previous[index], reachable))
                clauses.extend((-term, reachable) for term in terms)
                clauses.append((-reachable, previous[index], *terms))
                current.append(reachable)
            previous = current
        for literal, reachable in zip(literals, previous):
            clauses.append((-literal, reachable))
        return clauses

    def _at_most(self, variables: tuple[int, ...], k: int | None) -> list[Clause]:
        if k is None:
            raise PuzzleValidationError("Missing cardinality k")
        return self._cardinality(variables, set(range(0, min(k, len(variables)) + 1)))

    def _at_least(self, variables: tuple[int, ...], k: int | None) -> list[Clause]:
        if k is None:
            raise PuzzleValidationError("Missing cardinality k")
        return self._cardinality(variables, set(range(max(0, k), len(variables) + 1)))

    def _cardinality(self, variables: tuple[int, ...], allowed: set[int | None]) -> list[Clause]:
        """Polynomial exact-count automaton supporting signed status literals."""
        n = len(variables)
        valid = sorted(value for value in allowed if isinstance(value, int) and 0 <= value <= n)
        if not valid:
            return [()]
        if len(valid) == n + 1:
            return []

        clauses, final_states = self._count_states(variables)
        clauses.append(tuple(final_states[count] for count in valid))
        return clauses

    def _count_states(self, variables: tuple[int, ...]) -> tuple[list[Clause], tuple[int, ...]]:
        """One-hot exact count after each input; final states can compare two regions."""
        n = len(variables)

        self._cardinality_serial += 1
        prefix = f"card:{self._cardinality_serial}"
        previous = tuple(self._new_auxiliary(f"{prefix}:0:{count}") for count in range(n + 1))
        clauses: list[Clause] = [(previous[0],)]
        clauses.extend((-state,) for state in previous[1:])

        for index, literal in enumerate(variables, start=1):
            current = tuple(self._new_auxiliary(f"{prefix}:{index}:{count}") for count in range(n + 1))
            clauses.append(current)
            clauses.extend((-left, -right) for left, right in combinations(current, 2))
            for count, state in enumerate(previous):
                clauses.append((-state, literal, current[count]))
                if count < n:
                    clauses.append((-state, -literal, current[count + 1]))
                else:
                    clauses.append((-state, -literal))
            previous = current

        return clauses, previous
