# Agent validation — 21 November 2026

Environment: Windows, Python 3.13.5, local `.venv`; no third-party test packages.

## Local behavior tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m examples.agent_demo
```

Result after recheck: **64 tests passed**. Demo: synthetic 3×3, nine accepted
deductions, 36 SAT calls, SOLVED. The count includes a consistency check after
each reveal. The demo uses an exhaustive test oracle, not DPLL.

Regression tests cover invalid SAT models, violated query assumptions, reused
mutable solver results, completed-board inconsistencies, extra/missing/mismatched
revealed clues, and immediate contradiction detection at a step limit. An invalid
engine update prevents further play until restart.

The bounded truth-table tests independently compare all small formulas of up to
two clauses over three variables, including an auxiliary variable and permuted
variable mappings: 758 formula/mapping cases and 6,822 public-verdict states.

## Separate compatibility check with real DPLL

Our `agent.py`, `controller.py`, and `contracts.py` were tested with the real
encoder, DPLL, engine, and four puzzle fixtures from
[reference commit 587b04c](https://github.com/hyt2434/Griductive-Solver/tree/587b04cbd56ab2f2835e9ce905e6c98ff5817187).

- `3x3_binary_chain` and `3x3_counting_chain`: unique; SOLVED; eight accepted
  deductions and eight traces each (one initial card was already revealed).
- `4x4_easy_training` and `4x4_medium_links`: unique; SOLVED; fifteen accepted
  deductions and fifteen traces each (one initial card was already revealed).
- Hint left state unchanged. Unknown and contradicted submissions did not reveal
  clues. Inconsistency was detected even for a previously proved cell.

The temporary harness is outside this checkout at
`E:\FAI 2\tmp\reference-compat\run_compat.py`. The only upstream adaptation was
adding the controller's `RunStatus` enum to temporary upstream models.
Reference production code has not been included in this branch. These checks
verify interface compatibility; they are not benchmarks of the team's future
implementation, nor validation of the teammates' as-yet-unwritten modules.
