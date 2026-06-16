Status: ready-for-agent

# Post-match analysis + blunder detection

## What to build

`--analyze` command that reads a completed series PGN, runs the analysis engine over each game, detects blunders made by the subject engine, and produces an annotated PGN plus a blunder CSV.

Config additions:

```toml
[analysis]
track_blunders_for = "my-experimental-engine"
engine = "stockfish"
time_per_move = "1s"

[blunder_detection]
equal_range = 1.5
blunder_delta = 2.0
```

Behavior:

- **One game at a time**: analysis runs sequentially — game 1 is fully analyzed before game 2 starts.
- **Skip book positions**: positions where both engines played book moves (still in the opening book) are skipped — no analysis evaluation is requested. Analysis begins at the first position where at least one engine is out of book.
- **Blunder detection**: for each position after the book exit, the analysis engine evaluates the position *before* the subject engine's move and *after*. A blunder is recorded when `eval_before` is within `±equal_range` (near-equal) and the post-move eval drops by at least `blunder_delta` in the direction against the subject engine. Both values are in engine centipawns.
- **Analyzed PGN**: the raw PGN is annotated with position evaluations, written to the timestamped `output.analyzed` path. When `analysis` section is present and `output.analyzed` is specified, analysis is performed.
- **Blunder CSV**: written to the timestamped `output.blunders` path. Columns: `fen`, `blunder_move`, `eval_before`, `eval_after`, `eval_delta`.
- **Logging**: appends to the same log file — one line per blunder found, one line per game completed.

Edge cases:

- The analysis engine and subject engine may be the same engine (e.g. `track_blunders_for = "my-engine"` and `analysis.engine = "my-engine"`) — the tool allows this without warning.
- The analysis engine can be the same as the opponent engine. Allowed without warning.

## Acceptance criteria

- [ ] Running `chessengineroast --analyze series.toml` on a completed series PGN produces an annotated PGN and a blunder CSV
- [ ] Book positions are skipped — no analysis engine invocations for in-book positions
- [ ] A blunder is correctly detected: eval within ±1.5 before the move, drops by ≥2.0 after (configurable)
- [ ] Blunder CSV contains `fen`, `blunder_move`, `eval_before`, `eval_after`, `eval_delta` columns
- [ ] Only the subject engine's blunders are recorded; opponent blunders are ignored
- [ ] Output files are timestamped to prevent overwrites
- [ ] Log file is appended with blunder and game-completion entries

## Blocked by

- #3 — series play
