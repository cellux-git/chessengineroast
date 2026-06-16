Status: ready-for-agent

# Project scaffold + engine discovery

## What to build

Set up the Python project so the CLI is installable and the `--engines` command works end-to-end.

A `pyproject.toml` defines the `chessengineroast` entry point and dependencies. `pip install -e .` makes the CLI available globally. The `--engines` command scans the `engines/` directory and prints any engines found using the name convention: `engines/<name>/<name>` must be an executable binary. Invalid or missing directories are silently skipped.

## Acceptance criteria

- [ ] `pip install -e .` succeeds and makes `chessengineroast` available on PATH
- [ ] `chessengineroast --engines` prints nothing when `engines/` is empty
- [ ] Placing an executable at `engines/stockfish/stockfish` causes `chessengineroast --engines` to print `stockfish`
- [ ] A directory with no matching executable binary (e.g. `engines/broken/some-other-file`) is silently skipped

## Blocked by

None — can start immediately
