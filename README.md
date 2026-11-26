# Griductive Solver · Football Mystery

A playable, no-guess version of Griductive for CSC14003 Project 2. It converts
revealed clues to CNF and uses a DPLL SAT solver to prove verdicts.

## Run the game

Use Python 3.11 or newer. From the folder containing `main.py`, run

```powershell
python main.py
```

The game uses only the Python standard library. It opens **4×4 Rookie Training**
in your browser and prints the local URL. Keep the terminal open while playing
and press `Ctrl+C` to stop the server.

## Play

- Use **Load puzzle** to choose a board. The project includes two 3×3 boards,
  two 4×4 boards, and one 5×5 stress case. The diagnostic cases illustrate
  ambiguity and inconsistency.
- Select a player and choose **CRIMINAL** or **INNOCENT**. A proved verdict
  opens the player's clue. `NOT_PROVABLE` means either verdict is possible.
  `CONTRADICTED` means the opposite verdict is already forced.
- Select an opened clue to see its highlighted cells. **Hint** suggests a
  forced move, **Step** plays one move, and **Auto solve** plays successive
  moves. **Restart** resets the board.
- **Trace** shows the proof queries and newly revealed clues. **Check uniqueness**
  checks the complete clue set.

## Command line and experiments

```powershell
python main.py solve puzzles/3x3_counting_chain.json
python main.py validate puzzles
python main.py experiments --manifest experiments/puzzle_set.json --runs 5 --timeout 60
```

`solve` prints the deduction trace. `validate` checks that each standard board
has a unique solution and can be solved from the clues revealed during play.
The benchmark uses a [fixed set of boards](experiments/puzzle_set.json) and
records CNF sizes, SAT calls, search statistics, deduction steps, runtimes,
failures and timeouts. Use `--csv`, `--json`, or `--markdown` with an output
path to save results.

## Tests

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
```

## How it works

[GameEngine](griductive/engine.py) holds the complete puzzle. During play,
[LogicAgent](griductive/agent.py) receives the revealed clues and proved verdicts.
The [CNF encoder](griductive/cnf.py) converts those facts into clauses, and the
[DPLL solver](griductive/dpll.py) checks whether the opposite verdict is possible.
[GameController](griductive/controller.py) opens a card after the Agent proves its verdict.

See the [project report](Report.pdf) for the algorithms and results,
the [VS Code guide](docs/VSCODE_GUIDE.md) and [integration guide](docs/TEAM_INTEGRATION.md)
for development, and the [image credits](assets/CREDITS.md) for photo sources and licenses.
