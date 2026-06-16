Status: ready-for-agent

# Series play + opening book + robustness

## What to build

Extend single-game play to the full series workflow. This adds multi-game support, the opening book, proper output handling, logging, and engine failure recovery.

Full config for this slice:

```toml
[engines]
white = "my-experimental-engine"
black = "stockfish"

[time]
base = "3m"
increment = "2s"

[matches]
games = 10

[output]
raw = "series/my-engine-vs-stockfish.pgn"

[engine_options.stockfish]
Hash = 128
Threads = 2
OwnBook = "true"
BookFile = "books/opening.bin"

[engine_options.my-experimental-engine]
Hash = 64
Threads = 1
OwnBook = "true"
BookFile = "books/opening.bin"
```

Key additions:

- **Multi-game**: plays `matches.games` games with alternating colors (game 1: white=first engine, game 2: white=second engine, repeat).
- **Opening book**: the bundled `books/opening.bin` (Polyglot format) is passed to both engines via `OwnBook`/`BookFile` UCI options. The tool does not manage book moves — engines consume the book themselves.
- **Timestamped output**: `output.raw` path gets `-YYYYMMDD-HHMMSS` appended before the extension.
- **Logging**: a single append log file records game starts, moves, and outcomes. Analysis log entries (blunders found, games analyzed) will be appended by a later slice.
- **Crash handling**: if an engine process exits unexpectedly, the game is scored as a forfeit (win for the opponent), and the series continues with the next game.
- **Hang handling**: if an engine fails to respond within `base_seconds / 3` per move, the series is aborted with an error message.
- **Game termination**: inherited from slice #2 — all 5 rules via python-chess.

## Acceptance criteria

- [ ] A 10-game series completes with both engines getting equal White/Black games
- [ ] Engines consume the bundled opening book (no forced book-exit logic in the tool)
- [ ] Output PGN is timestamped and contains all 10 games
- [ ] Log file records game starts, moves, and outcomes
- [ ] Killing an engine mid-game causes a forfeit for that game; the remaining games continue
- [ ] An engine that hangs (no response for > base/3 seconds) aborts the entire series with an error
- [ ] PGN tags include `WhiteEngine`, `BlackEngine`, and `TimeControl` for each game

## Blocked by

- #2 — play a single game
