from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"solve", "validate", "experiments"}:
        from griductive.cli import run_cli
        return run_cli(sys.argv[1:])
    from griductive.gui import run_gui
    default = Path(__file__).resolve().parent / "puzzles/4x4_easy_training.json"
    return run_gui(Path(sys.argv[1]) if len(sys.argv) > 1 else default)


if __name__ == "__main__":
    raise SystemExit(main())
