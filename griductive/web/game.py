from dataclasses import asdict
import json
from pathlib import Path
from threading import RLock
from uuid import uuid4

from ..clues import clue_review_cells, describe_clue
from ..engine import GameController, GameEngine
from ..models import Puzzle, Status
from ..regions import resolve_region
from .portraits import portrait_index

ROOT = Path(__file__).resolve().parents[2]
PUZZLES = ROOT / "puzzles"
SCANDAL = PUZZLES / "diagnostics/3x3_inconsistent_scandal.json"


def public_clue(clue, state):
    groups = {}
    for key in ("left", "right", "region"):
        region = getattr(clue, key)
        if region:
            groups[key] = resolve_region(region, state.cells, state.size)

    def compact(record):
        return {k: (compact(v) if isinstance(v, dict) else v)
                for k, v in record.items() if v is not None and v != ()}

    return {"id": clue.id, "text": describe_clue(clue, state),
            "formula": compact(asdict(clue)), "targets": clue_review_cells(clue, state),
            "groups": groups}


class Match:
    def __init__(self, initial: Path, portraits: Path = ROOT / "assets/players"):
        self.lock = RLock()
        self.session = uuid4().hex
        self.portraits = portraits
        self.paths = {p.relative_to(PUZZLES).as_posix(): p for p in sorted(PUZZLES.rglob("*.json"))}
        initial = initial.resolve()
        self.current = next((key for key, p in self.paths.items() if p == initial), initial.name)
        self.paths[self.current] = initial
        self.load(self.current)

    def catalog(self):
        items = []
        for key, path in self.paths.items():
            with path.open(encoding="utf-8") as src:
                data = json.load(src)
            items.append({"id": key, "title": data["title"], "size": data["size"],
                          "diagnostic": path.parent == SCANDAL.parent})
        return items

    def load(self, key):
        path = self.paths[key]
        controller = GameController(GameEngine(Puzzle.load(path), inconsistent_demo=path == SCANDAL))
        self.current, self.controller = key, controller

    def snapshot(self):
        game = self.controller
        state = game.engine.public_state
        revealed = iter(state.revealed_clues)
        portraits = portrait_index(self.portraits)
        cards = []
        for cell in state.cells:
            status = state.proved.get(cell.id)
            clue = public_clue(next(revealed), state) if status else None
            path = portraits.get(cell.slug)
            url = None
            if path:
                try:
                    url = f"/assets/players/{cell.slug}?v={path.stat().st_mtime_ns}"
                except FileNotFoundError:
                    pass
            cards.append({**asdict(cell), "status": status or "UNKNOWN", "clue": clue,
                          "portrait": url})
        formula = game.agent.build_kb(state)
        return {
            "session": self.session,
            "puzzle": self.current, "title": state.title, "size": state.size, "cards": cards,
            "solved": len(state.proved), "total": len(cards),
            "trace": [asdict(step) for step in game.trace],
            "metrics": {"primary": len(formula.primary_variables), "aux": len(formula.auxiliary_variables),
                        "clauses": formula.clause_count, "calls": game.agent.stats.sat_calls,
                        **asdict(game.agent.stats.solver)},
            "clause_preview": formula.clauses[:30],
        }

    def action(self, action, data):
        game = self.controller
        state = game.engine.public_state
        outcome = {}
        if action == "load":
            self.load(data["puzzle"])
        elif action == "restart":
            game.restart()
        elif action in ("verdict", "clue-highlight"):
            cell = data["cell"]
            if cell not in {c.id for c in state.cells}:
                raise ValueError("Unknown board coordinate")
            if action == "verdict":
                verdict = game.submit(cell, Status(data["status"]))
                outcome = {"result": verdict.result, "cell": cell, "message": verdict.message}
            else:
                cards = self.snapshot()["cards"]
                clue = next(c["clue"] for c in cards if c["id"] == cell)
                outcome = {"cell": cell, "clue": clue}
        elif action == "hint":
            hint = game.hint()
            if hint:
                cell, classification = hint
                outcome = {"cell": cell, "result": "INCONSISTENT" if classification.inconsistent else "HINT",
                           "status": classification.status, "queries": classification.queries,
                           "active": list(state.proved)}
            else:
                outcome = {"result": "SOLVED" if game.engine.solved else "NOT_PROVABLE"}
        elif action in ("step", "solve"):
            if action == "step":
                move = game.auto_step()
            else:
                moves = game.auto_solve()
                move = moves[-1] if moves else None
            if game.engine.solved:
                result = "SOLVED"
            elif move and action == "step":
                result = "ACCEPTED"
            else:
                hint = game.hint()
                result = "INCONSISTENT" if hint and hint[1].inconsistent else "NOT_PROVABLE"
            outcome = {"result": result, "cell": move.cell_id if move else None}
        elif action == "uniqueness":
            sat, unique = game.agent.check_uniqueness(state, game.engine.all_clues_for_validation())
            outcome = {"satisfiable": sat, "unique": unique,
                       "result": "UNIQUE" if unique else ("AMBIGUOUS" if sat else "INCONSISTENT")}
        else:
            raise KeyError(action)
        return {"state": self.snapshot(), **outcome}
