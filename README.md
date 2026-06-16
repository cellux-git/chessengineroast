# Chess Engine Roast

CLI tool for running UCI chess engine matches and analyzing games for blunders.

## Installation

```bash
git clone https://github.com/cellux-git/chessengineroast.git
cd chessengineroast
pip install -e .
```

Requires Python 3.11+.

## Quick Start

### 1. Install engines

Place UCI engine binaries in `engines/<name>/<name>`. The binary filename must match the directory name.

```
engines/
  stockfish/
    stockfish        # executable
  my-experimental-engine/
    my-experimental-engine  # executable
```

List installed engines:

```bash
chessengineroast --engines
```

### 2. Create a series config

Write a TOML config file:

```toml
# series.toml
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
Hash = 64
Threads = 2

[engine_options.my-experimental-engine]
Hash = 64
Threads = 2
```

### 3. Play matches

```bash
chessengineroast --play series.toml
```

Output is a timestamped PGN: `series/my-engine-vs-stockfish-20260615-143021.pgn`

### 4. Analyze for blunders

Add an analysis section to your config:

```toml
[output]
raw = "series/my-engine-vs-stockfish.pgn"
analyzed = "series/my-engine-vs-stockfish-analyzed.pgn"
blunders = "series/blunders.csv"

[analysis]
track_blunders_for = "my-experimental-engine"
engine = "stockfish"
time_per_move = "1s"

[blunder_detection]
equal_range = 1.5
blunder_delta = 2.0
```

Run analysis:

```bash
chessengineroast --analyze series.toml
```

Produces an annotated PGN and a blunder CSV with columns:
`fen`, `blunder_move`, `eval_before`, `eval_after`, `eval_delta`

## Configuration Reference

| Section | Key | Description | Default |
|---------|-----|-------------|---------|
| `[engines]` | `white` | White engine name (required) | — |
| | `black` | Black engine name (required) | — |
| `[time]` | `base` | Base time per game, e.g. `"3m"` (required) | — |
| | `increment` | Increment per move, e.g. `"2s"` (required) | — |
| `[matches]` | `games` | Number of games to play | `1` |
| `[output]` | `raw` | PGN output path | `{white}-vs-{black}.pgn` |
| | `analyzed` | Annotated PGN output path | — |
| | `blunders` | Blunder CSV output path | — |
| `[analysis]` | `track_blunders_for` | Engine whose blunders to detect | — |
| | `engine` | Analysis engine name | — |
| | `time_per_move` | Think time per move, e.g. `"1s"` | — |
| `[blunder_detection]` | `equal_range` | Max pre-move eval for "near-equal" (centipawns) | `1.5` |
| | `blunder_delta` | Min eval drop to flag (centipawns) | `2.0` |
| `[engine_options.<name>]` | — | UCI options passed to engine `<name>` | — |

## Opening Book

A bundled Polyglot opening book (`books/opening.bin`) provides varied starting positions. Engines consume the book via `OwnBook`/`BookFile` UCI options. Book positions are skipped during analysis.

## Match Behavior

- Colors alternate each game (equal White/Black exposure)
- Engine crash: series aborts with error report
- Engine hang (no response for `base_time / 3` seconds): series aborts with error report
- Illegal move or no-move response: series aborts with error report
- All 5 draw rules enforced (checkmate, stalemate, threefold repetition, 50-move rule, insufficient material)

## Logging

A log file (`<output>.log`) records all games and analysis progress.

## Running Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/
```
