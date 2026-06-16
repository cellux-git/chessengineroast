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

[engine_options.stockfish]
Hash = 64
Threads = 2

[engine_options.my-experimental-engine]
Hash = 64
Threads = 2
```

### 3. Play matches

Pass `--config` with your TOML file, `--play`, and a `--tag`:

```bash
chessengineroast --config series.toml --tag my-test --play
```

This creates `series-my-test/` with a static `games.pgn` and `games.log`.

### 4. Analyze for blunders

Add an analysis section to your config:

```toml
[analysis]
track_blunders_for = "my-experimental-engine"
engine = "stockfish"
time_per_move = "1s"

[blunder_detection]
equal_range = 1.5
blunder_delta = 2.0
```

Run analysis on the same tag:

```bash
chessengineroast --config series.toml --tag my-test --analyze
```

Produces `games-analyzed.pgn` and `blunders.csv` inside `series-my-test/`.

### 5. Combined play and analysis

Pass both `--play` and `--analyze` with a single `--config`:

```bash
chessengineroast --config series.toml --tag my-test --play --analyze
```

## Tag-based output directories

The `--tag` parameter is mandatory for `--play` and `--analyze`. All output goes into `series-{tag}/` with static filenames:

| File | Description |
|------|-------------|
| `games.pgn` | Raw PGN with all games |
| `games.log` | Play and analysis log |
| `games-analyzed.pgn` | Annotated PGN with position evaluations |
| `blunders.csv` | Detected blunders |

**Play** aborts if `series-{tag}/` already exists. Choose a different tag or delete the directory to re-run.

**Analysis** aborts if `blunders.csv` already exists in the directory (analysis already completed).

## Blunder CSV Format

The blunder CSV is the primary output of the analysis. Each row represents one blunder made by the tracked engine.

```
fen,blunder_move,eval_before,eval_after,eval_delta
rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1,e7e5,0.15,2.87,2.72
rn1qkbnr/ppp1pppp/8/3p4/5b2/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3,g1f3,-0.30,-3.00,2.70
```

### Column definitions

| Column | Description |
|--------|-------------|
| `fen` | FEN of the position *before* the blunder move |
| `blunder_move` | The move played, in UCI notation (e.g. `e2e4`) |
| `eval_before` | Engine evaluation before the move, in centipawns |
| `eval_after` | Engine evaluation after the move, in centipawns |
| `eval_delta` | How much the eval swung against the player (always positive for blunders) |

### Interpreting eval scores

All eval scores are from **White's perspective**. A positive value means White is ahead, negative means Black is ahead. For example:

- `eval_before = 0.15` — position was roughly equal, White slightly ahead
- `eval_after = 2.87` — after the blunder, Black swung to a ~2.9 advantage
- `eval_delta = 2.72` — the move cost ~2.7 centipawns

The `eval_delta` is always positive when a blunder is recorded, meaning the evaluation shifted *against* the engine that made the move. The magnitude tells you how bad the blunder was.

### Blunder detection criteria

A move is flagged as a blunder when both conditions are met:

1. **Near-equal position**: `|eval_before| ≤ equal_range` (default 1.5 centipawns) — the position before the move was close to equal
2. **Big swing**: `eval_delta ≥ blunder_delta` (default 2.0 centipawns) — the eval dropped significantly against the player

Positions where the tracked engine was already winning or losing by more than `equal_range` are excluded — those are considered "already decided" rather than blunders.

## Configuration Reference

| Section | Key | Description | Default |
|---------|-----|-------------|---------|
| `[engines]` | `white` | White engine name (required) | — |
| | `black` | Black engine name (required) | — |
| `[time]` | `base` | Base time per game, e.g. `"3m"` (required) | — |
| | `increment` | Increment per move, e.g. `"2s"` (required) | — |
| `[matches]` | `games` | Number of games to play | `1` |
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

A log file (`series-{tag}/games.log`) records all games and analysis progress. The log file path is printed to stdout after every run.

## Running Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/
```
