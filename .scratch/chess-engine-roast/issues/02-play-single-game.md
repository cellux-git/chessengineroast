Status: ready-for-agent

# Play a single game

## What to build

`--play` command that parses a minimal TOML config, launches two UCI engines, and plays one game to completion. Writes the PGN to a hardcoded output path.

Config format for this slice (subset of the final schema):

```toml
[engines]
white = "stockfish"
black = "lc0"

[time]
base = "3m"
increment = "2s"

[engine_options.stockfish]
Hash = 128
Threads = 2
```

The engines are launched as subprocesses. Standard UCI startup: `uci` → wait for `uciok` → `setoption` for each configured option → `isready` → `readyok` → `ucinewgame`. Time control is sent via `go wtime X btime Y winc Z binc Z`. Colors alternate each move: White engine receives the position, replies with `bestmove`, position is updated, sent to Black engine, etc.

Game termination uses python-chess to detect checkmate, stalemate, threefold repetition, 50-move rule, and insufficient material. The PGN includes standard tags (Event, Site, Date, Round, White, Black, Result) plus `WhiteEngine`, `BlackEngine`, and `TimeControl`.

This slice intentionally omits: opening book, multi-game series, crash/hang handling, timestamped output, and logging.

## Acceptance criteria

- [ ] Running `chessengineroast --play series.toml` with two valid UCI engines produces a PGN file with one complete game
- [ ] The game reaches a terminal result (checkmate, stalemate, draw, etc.) — does not hang or error
- [ ] PGN output is valid and contains `WhiteEngine`, `BlackEngine`, and `TimeControl` tags
- [ ] Time control is respected (base time + increment passed via UCI `go` command)
- [ ] `[engine_options]` from the config are applied to the correct engine via `setoption`

## Blocked by

- #1 — project scaffold + engine discovery
