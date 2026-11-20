# Griductive Solver · Football Mystery

A playable, no-guess implementation of Griductive for CSC14003 Project 2. The
application represents revealed clues in propositional logic, converts them to
CNF, and proves verdicts with a DPLL SAT solver implemented in this repository.

## Features

- Local browser tactics board with FC-style shield cards, player portraits, pitch
  and roster views, public clue inspection, deduction trace and live SAT telemetry.
- Fixed 25-player master roster. The standard and diagnostic boards use the
  same size-specific squad in alphabetical, row-major order.
- Manual `CRIMINAL` / `INNOCENT` calls with distinct `NOT_PROVABLE` and
  `CONTRADICTED` responses.
- Clickable clues that highlight referenced or counted cells.
- Load, Restart, Hint and animated Auto Solve controls.
- Strict separation between the secret-owning `GameEngine` and the
  public-state-only `LogicAgent`.
- Six required clue templates: `FACT`, `SAME`, `DIFFERENT`, `EXACTLY`,
  `AT_LEAST`, and `AT_MOST`.
- Extended constraints: `PARITY`, `COUNT_COMPARE`, `ALL_OF`, `CONNECTED`,
  `CONNECTED_COUNT`, `INCLUDED_COUNT`, `OVERLAP_COUNT`, `GROUP_MOST`, and
  `GROUP_ONLY`.
- Criminal or Innocent counting through the reusable `target_status` selector.
- Composable regions: row, column, neighbors, explicit list, whole grid,
  corners, edges, cells between two people, common neighbors, directional
  cells, profession groups, intersections and unions.
- Automatic CNF generation, deterministic variable mapping and clause counts.
- Custom DPLL with unit propagation, conflicts, deterministic branching,
  backtracking, complete models and runtime metrics.
- Deduction trace, full-clue uniqueness checking and progressive-solvability
  validation.
- Five curated cases across the required experiment sizes: two 3x3 training
  cases, two 4x4 cases, and the original-style 5x5 Deep Inference stress case.

## Run on Windows

Extract the ZIP, open the folder containing `main.py` in VS Code and run:

```powershell
python main.py
```

Python 3.11 or newer is recommended. The game uses the standard library and
works offline. The launcher opens `http://127.0.0.1:8765/` in the default
browser, or prints and opens another loopback URL if that port is occupied.
Keep the Python terminal running while you play. If a tab disconnects, restart
`python main.py` and use the URL printed in that terminal. Ctrl+C stops the
server. For a specific case, run
`python main.py puzzles/5x5_deep_inference.json`.

Click a card or a roster row. The inspection panel shows its public metadata
and either the two verdict buttons or the revealed clue and its region.
Hint shows a forced move, Step plays it, and Auto solve advances until paused
or until no move can be proved. Instant completes all currently forced moves.
Check uniqueness inspects the full clue set as a separate administrative action.

## Squads and portraits

`griductive/roster.py` defines all 25 cards. Bundled puzzles select the squads
with `"roster": "football"`. The 3×3 and 4×4 selections are fixed subsets.
A 5×5 board starts at A1 Alisson and ends at E5 Vinicius. Legacy custom
puzzles can still define their own cells, names and professions.

Put portraits in `assets/players/` and refresh the board. The local endpoint
`/assets/players/<slug>` resolves PNG, WebP, JPG and JPEG, in that order,
regardless of filename casing. For example, `MESSI.PNG` overrides `messi.jpg`.
Only available files are requested. A missing or undecodable image displays
the player's club-coloured SVG kit. The full filename checklist is in
`assets/players/README.txt`. See `assets/CREDITS.md` for photo sources and licenses.

The Diagnostic puzzles group contains a 3×3 ambiguous case and a 3×3
inconsistent case. Both intentionally stop with unresolved cards. These
fixtures live under `puzzles/diagnostics/` outside the five-case benchmark.

## CLI and experiments

```bash
python main.py solve puzzles/4x4_medium_links.json
python main.py validate puzzles
python main.py experiments --manifest experiments/puzzle_set.json --runs 5 --timeout 60 \
  --csv results/benchmark_results.csv \
  --json results/benchmark_results.json \
  --markdown results/EXPERIMENTS.md
```

`validate` performs schema/semantic checks, verifies that the complete clue set
has exactly one model, and confirms that the public reveal sequence can be
solved without guessing. It returns a non-zero exit code when any of those
conditions fails. `experiments` records every case, including `FAILED` and
`TIMEOUT` outcomes; runtime columns contain the mean, minimum, maximum, and
population standard deviation across completed runs. Use `--timeout 0` to
disable the per-run timeout. The manifest locks the ordered comparison set so
every run uses the same two 3x3, two 4x4, and one 5x5 stress case. The Markdown
output is a report-ready table with an explicit failure/timeout section and
environment metadata.

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

The core encoding tests exhaustively enumerate every complete 2x2 assignment and
compare each CNF encoding with its independent direct semantic evaluator. DPLL
is also tested separately for SAT, UNSAT, assumptions and backtracking.

## Project structure

```text
main.py                     GUI/CLI entry point
griductive/models.py        Puzzle, public-state and verdict data models
griductive/regions.py       Region resolution
griductive/clues.py         Validation, semantics and descriptions
griductive/cnf.py           Automatic CNF encoder
griductive/dpll.py          Instrumented DPLL SAT solver
griductive/agent.py         Entailment, hint and uniqueness logic
griductive/engine.py        Secret engine and game controller
griductive/gui.py           Browser launcher
griductive/web/             Local HTTP server, public game API and web UI
griductive/roster.py        Fixed master roster and board selections
assets/players/             Local player photos and filename checklist
griductive/cli.py           Validation and solver commands
griductive/experiments.py   Reproducible benchmark runner
puzzles/                    Structured JSON puzzle files
tests/                      Unit and end-to-end tests
```

## Logical protocol

For an unresolved cell `i`, Criminal is proved exactly when `KB & not Ci` is
UNSAT; Innocent is proved exactly when `KB & Ci` is UNSAT. If both assumptions
are satisfiable, the result is `UNKNOWN` and no card is revealed. The knowledge
base contains only revealed clues and unit clauses for previously proved
verdicts. Hidden labels and face-down clues never enter hint or deduction code.

Cardinality constraints use a polynomial finite-state counter, allowing global
counts on a 5x5 board without combinatorial clause growth. Parity, count
comparison, and group ranking use truth-table blocking over their local groups.
Connectivity uses a polynomial reachability encoding with deterministic
auxiliary variables; auxiliary counts are reported separately from primary
character variables.

## Puzzle format

Each JSON file specifies `size`, `solution`, `initially_revealed`, and one
structured clue per cell. Optional `names` and `professions` maps customize the
display. Cell order is row-major (`A1`, `B1`, ..., `A2`, ...). The bundled
cases are `3x3_binary_chain.json`, `3x3_counting_chain.json`,
`4x4_easy_training.json`, `4x4_medium_links.json`, and
`5x5_deep_inference.json`. Rookie Training remains the default GUI puzzle.
