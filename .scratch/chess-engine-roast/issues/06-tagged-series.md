Status: completed

# Tagged series directories, combined play+analysis flow, and static file names

## What to build

A mandatory `--tag` parameter for `--play` and `--analyze` that scopes output to a dedicated `series-{tag}/` directory. Running `--play` and `--analyze` together (both flags) in one invocation runs play then analysis in sequence.

### 1. Mandatory `--tag` parameter

Both `--play` and `--analyze` gain a required `--tag TAG` argument. The output directory becomes `series-{tag}/` instead of `series/`.

```bash
chessengineroast --play series.toml --tag my-experiment
# Output goes to series-my-experiment/
```

### 2. Play: abort if `series-{tag}/` already exists

When `--play` is used, check whether `series-{tag}/` already exists. If it does, print an error and exit (do not overwrite or append to existing results). The user must pick a new tag or delete the directory manually.

### 3. Analysis: abort if blunder file already present

When `--analyze` is used, check whether the blunder CSV file already exists inside `series-{tag}/`. If it does, print an error and exit. This prevents re-running analysis and overwriting previous results.

### 4. Static file names inside `series-{tag}/`

Files inside `series-{tag}/` use static names — no timestamps. The directory scope (tag) provides uniqueness.

| File | Name |
|------|------|
| Raw PGN | `games.pgn` |
| Log file | `games.log` |
| Analyzed PGN | `games-analyzed.pgn` |
| Blunder CSV | `blunders.csv` |

### 5. Combined `--play --analyze` invocation

Both flags can be specified together in a single invocation to run play then analysis sequentially:

```bash
chessengineroast --play series.toml --analyze series.toml --tag my-experiment
# Runs play, then analysis on the same tag
```

The play step creates `series-{tag}/` and populates it with `games.pgn` and `games.log`. The analysis step reads `games.pgn` from the same directory and produces `games-analyzed.pgn` and `blunders.csv`. Analysis appends to the same log file.

### 6. Print log file path

After execution (play, analysis, or combined), print the full path to the log file to stdout so the user knows where to find it.

### Config changes

The `[output]` section in series.toml is ignored — filenames are always static with simple descriptive names (`games.pgn`, `games-analyzed.pgn`, `blunders.csv`, `games.log`), scoped to `series-{tag}/`. The `tag` is mandatory for both `--play` and `--analyze`.

### Edge cases

- `--tag` is required for both `--play` and `--analyze`; missing `--tag` prints an error.
- `--engines` (list engines) does not require `--tag`.
- If `--play` succeeds but the user forgets the tag when running `--analyze`, the tool cannot find `series-{tag}/games.pgn` because the tag is mandatory — this is intentional.

## Acceptance criteria

- [ ] `--play series.toml --tag my-test` creates `series-my-test/` with `games.pgn` and `games.log`
- [ ] Running `--play` again with the same tag aborts with an error (directory exists)
- [ ] `--analyze series.toml --tag my-test` reads `series-my-test/games.pgn`, writes `series-my-test/games-analyzed.pgn` and `series-my-test/blunders.csv`
- [ ] Running `--analyze` again with the same tag aborts if `blunders.csv` already exists
- [ ] `--play series.toml --analyze series.toml --tag my-test` runs play then analysis, producing all four output files
- [ ] All file names inside `series-{tag}/` are static (no timestamps)
- [ ] Log file path is printed to stdout on completion
- [ ] `--play` and `--analyze` both reject invocation without `--tag`
- [ ] `--engines` still works without `--tag`
- [ ] README documents output files, their static names, and usage examples for `--play`, `--analyze`, and combined invocation


