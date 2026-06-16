# Engine binary discovery by directory convention

Engines live under `engines/<name>/` and the binary must match the directory name (`engines/<name>/<name>`). No auto-detection of executables, no per-engine JSON config with an explicit binary path. The tool rejects any engine directory that doesn't contain an executable file matching the directory name.

We chose convention over two alternatives:
- **Auto-detect**: scan the directory and use any executable found. Rejected because it's fragile — extra files (scripts, configs, old versions) produce ambiguous results.
- **Explicit JSON**: an `engine.json` in each directory with a `binary` field. Rejected because it adds a file the user must maintain for every engine, and the directory name already carries the logical engine name.

Convention keeps engine installation dead simple: one directory, one binary, one name. The cost is that the binary filename is constrained — but in practice, UCI engine binaries are already named after the engine.
