# Griductive Experiment Results

Generated at `2026-11-20T08:09:26+00:00`.

## Method

- Experiment: `required_grid_sizes_v1`.
- Description: Fixed comparison set: two 3x3 cases, two 4x4 cases, and one 5x5 stress case.
- Puzzle set: `experiments/puzzle_set.json`.
- Cases: 5.
- Repetitions: 5 measured runs per case.
- Timeout: 60 seconds per run.
- Every comparison uses the same ordered puzzle set.
- Runtime columns report the mean across completed runs; `+/-` is population standard deviation.
- Environment: Python 3.14.7 on Windows-11-10.0.26200-SP0.

## Results

| Puzzle | Size | Runs | Primary | Auxiliary | CNF clauses | SAT calls | Decisions | Propagations | Conflicts | Backtracks | Steps | Solver ms | End-to-end ms | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 3x3_binary_chain.json | 3 | 5/5 | 9 | 0 | 16 | 24 | 0 | 132 | 8 | 0 | 8 | 0.2816 +/- 0.0063 | 0.4899 +/- 0.0185 | SOLVED |
| 3x3_counting_chain.json | 3 | 5/5 | 9 | 66 | 185 | 24 | 0 | 924 | 8 | 0 | 8 | 2.5662 +/- 0.3129 | 3.3811 +/- 0.4617 | SOLVED |
| 4x4_easy_training.json | 4 | 5/5 | 16 | 315 | 1,611 | 93 | 222 | 8,578 | 33 | 18 | 15 | 57.6069 +/- 2.9209 | 61.9681 +/- 3.1558 | SOLVED |
| 4x4_medium_links.json | 4 | 5/5 | 16 | 681 | 4,838 | 153 | 813 | 31,737 | 173 | 295 | 15 | 348.6541 +/- 3.9386 | 370.9804 +/- 4.2702 | SOLVED |
| 5x5_deep_inference.json | 5 | 5/5 | 25 | 1,442 | 13,493 | 268 | 5,658 | 176,415 | 3,831 | 7,086 | 24 | 5,682.1659 +/- 161.3123 | 5,734.0662 +/- 162.0978 | SOLVED |

## Failures and timeouts

No failures or timeouts occurred in this experiment run.

## Observations

- 5/5 cases completed successfully; 0 failure or timeout outcome(s) were recorded.
- `5x5_deep_inference.json` had the highest mean end-to-end runtime (5,734.0662 ms).
- `5x5_deep_inference.json` generated the largest CNF (13,493 clauses and 1,442 auxiliary variables).
- Search effort grows with clue structure as well as board size: counting and connectivity encodings introduce auxiliary state beyond the primary character variables.

## Measurement notes and limitations

- Solver runtime is accumulated DPLL time; end-to-end runtime measures the progressive auto-solve loop. Loading and full-CNF size inspection are excluded.
- Primary, auxiliary, clause, SAT-call, decision, propagation, backtrack, and step counts are deterministic for the current solver and puzzle set.
- Failed or timed-out cases remain in every output with empty unavailable metrics; they are never silently removed.
- Runtime is machine- and load-dependent; repeated-run statistics reduce but do not eliminate that variation.
- The suite contains five curated puzzles and evaluates one deterministic DPLL configuration; it is not a universal SAT benchmark.
