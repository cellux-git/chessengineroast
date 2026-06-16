from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest


MOCK_ENGINE_SRC = Path(__file__).parent / "mock_engine.py"


def _setup_engines_in_dir(target_dir: Path) -> None:
    engines_dir = target_dir / "engines"
    engines_dir.mkdir(exist_ok=True)
    for name in ("mockengine", "mockengine2"):
        eng_dir = engines_dir / name
        eng_dir.mkdir(exist_ok=True)
        dst = eng_dir / name
        shutil.copy2(MOCK_ENGINE_SRC, dst)
        dst.chmod(dst.stat().st_mode | stat.S_IEXEC)


def _run(cwd, *args):
    env = os.environ.copy()
    env["CHESSENGINE_ROAST_ENGINES_DIR"] = str(cwd / "engines")
    env["CHESSENGINE_ROAST_BOOK_PATH"] = str(cwd / "nonexistent.bin")
    return subprocess.run(
        [sys.executable, "-m", "chessengineroast", *args],
        capture_output=True, text=True, cwd=str(cwd), env=env, timeout=30,
    )


class TestCliEngines:
    def test_list_engines(self, tmp_path):
        _setup_engines_in_dir(tmp_path)
        env = os.environ.copy()
        env["CHESSENGINE_ROAST_ENGINES_DIR"] = str(tmp_path / "engines")
        result = subprocess.run(
            [sys.executable, "-m", "chessengineroast", "--engines"],
            capture_output=True, text=True, cwd=str(tmp_path), env=env,
        )
        assert "mockengine" in result.stdout
        assert "mockengine2" in result.stdout

    def test_no_engines(self, tmp_path):
        result = subprocess.run(
            [sys.executable, "-m", "chessengineroast", "--engines"],
            capture_output=True, text=True, cwd=str(tmp_path),
        )
        assert "No engines found" in result.stdout

    def test_engines_does_not_require_tag(self, tmp_path):
        _setup_engines_in_dir(tmp_path)
        result = _run(tmp_path, "--engines")
        assert "mockengine" in result.stdout
        assert result.returncode == 0


class TestCliPlay:
    def test_play_creates_tagged_directory(self, tmp_path):
        _setup_engines_in_dir(tmp_path)
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"
""")
        result = _run(tmp_path, "--config", str(config_path), "--play", "--tag", "test1")
        series_dir = tmp_path / "series-test1"
        assert series_dir.is_dir(), f"stdout: {result.stdout}, stderr: {result.stderr}"
        assert (series_dir / "games.pgn").exists()
        assert (series_dir / "games.log").exists()

    def test_play_produces_pgn(self, tmp_path):
        _setup_engines_in_dir(tmp_path)
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"
""")
        result = _run(tmp_path, "--config", str(config_path), "--play", "--tag", "results")
        pgn_path = tmp_path / "series-results" / "games.pgn"
        assert pgn_path.exists(), f"No PGN found, stdout: {result.stdout}, stderr: {result.stderr}"

    def test_play_aborts_if_directory_exists(self, tmp_path):
        _setup_engines_in_dir(tmp_path)
        series_dir = tmp_path / "series-mytag"
        series_dir.mkdir()
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"
""")
        result = _run(tmp_path, "--config", str(config_path), "--play", "--tag", "mytag")
        assert result.returncode != 0
        assert "already exists" in result.stderr

    def test_play_missing_tag(self, tmp_path):
        _setup_engines_in_dir(tmp_path)
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"
""")
        result = _run(tmp_path, "--config", str(config_path), "--play")
        assert result.returncode != 0
        assert "--tag" in result.stderr

    def test_play_missing_engines(self, tmp_path):
        config_path = tmp_path / "bad.toml"
        config_path.write_text("""\
[engines]
white = "nonexistent"
black = "nonexistent2"

[time]
base = "10s"
increment = "1s"
""")
        result = _run(tmp_path, "--config", str(config_path), "--play", "--tag", "bad")
        assert result.returncode != 0

    def test_play_with_options(self, tmp_path):
        _setup_engines_in_dir(tmp_path)
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"

[engine_options.mockengine]
Hash = "64"
""")
        result = _run(tmp_path, "--config", str(config_path), "--play", "--tag", "opts")
        pgn_path = tmp_path / "series-opts" / "games.pgn"
        assert pgn_path.exists(), f"stdout: {result.stdout}, stderr: {result.stderr}"

    def test_log_file_path_printed(self, tmp_path):
        _setup_engines_in_dir(tmp_path)
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"
""")
        result = _run(tmp_path, "--config", str(config_path), "--play", "--tag", "logtest")
        assert "Log:" in (result.stdout + result.stderr)


class TestCliAnalyze:
    def test_analyze_missing_tag(self, tmp_path):
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"
""")
        result = _run(tmp_path, "--config", str(config_path), "--analyze")
        assert result.returncode != 0
        assert "--tag" in result.stderr

    def test_analyze_missing_analysis_section(self, tmp_path):
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"
""")
        result = _run(tmp_path, "--config", str(config_path), "--analyze", "--tag", "test")
        assert result.returncode != 0

    def test_analyze(self, tmp_path):
        _setup_engines_in_dir(tmp_path)
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"

[matches]
games = 1

[analysis]
track_blunders_for = "mockengine"
engine = "mockengine2"
time_per_move = "1s"
""")
        # First play to create the PGN
        play_result = _run(tmp_path, "--config", str(config_path), "--play", "--tag", "analyze-test")

        pgn_path = tmp_path / "series-analyze-test" / "games.pgn"
        assert pgn_path.exists(), f"No PGN found, stdout: {play_result.stdout}, stderr: {play_result.stderr}"

        analyze_result = _run(tmp_path, "--config", str(config_path), "--analyze", "--tag", "analyze-test")
        assert "Analysis complete" in analyze_result.stdout, f"stdout: {analyze_result.stdout}, stderr: {analyze_result.stderr}"
        assert "Log:" in analyze_result.stdout

        csv_path = tmp_path / "series-analyze-test" / "blunders.csv"
        assert csv_path.exists()

        analyzed_pgn_path = tmp_path / "series-analyze-test" / "games-analyzed.pgn"
        assert analyzed_pgn_path.exists()

    def test_analyze_aborts_if_blunders_exists(self, tmp_path):
        _setup_engines_in_dir(tmp_path)
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"

[matches]
games = 1

[analysis]
track_blunders_for = "mockengine"
engine = "mockengine2"
time_per_move = "1s"
""")
        series_dir = tmp_path / "series-blundercheck"
        series_dir.mkdir()
        (series_dir / "games.pgn").touch()
        (series_dir / "blunders.csv").touch()

        result = _run(tmp_path, "--config", str(config_path), "--analyze", "--tag", "blundercheck")
        assert result.returncode != 0
        assert "blunders CSV already exists" in result.stderr

    def test_analyze_pgn_not_found(self, tmp_path):
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"

[analysis]
track_blunders_for = "mockengine"
engine = "mockengine2"
time_per_move = "1s"
""")
        result = _run(tmp_path, "--config", str(config_path), "--analyze", "--tag", "nonexistent")
        assert result.returncode != 0
        assert "PGN file not found" in result.stderr


class TestCliCombined:
    def test_play_and_analyze_together(self, tmp_path):
        _setup_engines_in_dir(tmp_path)
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"

[matches]
games = 1

[analysis]
track_blunders_for = "mockengine"
engine = "mockengine2"
time_per_move = "1s"
""")
        result = _run(tmp_path, "--config", str(config_path), "--play", "--analyze", "--tag", "combined")

        series_dir = tmp_path / "series-combined"
        assert (series_dir / "games.pgn").exists(), f"stdout: {result.stdout}, stderr: {result.stderr}"
        assert (series_dir / "games.log").exists()
        assert (series_dir / "games-analyzed.pgn").exists(), f"stdout: {result.stdout}, stderr: {result.stderr}"
        assert (series_dir / "blunders.csv").exists()

    def test_static_filenames_no_timestamps(self, tmp_path):
        _setup_engines_in_dir(tmp_path)
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"

[matches]
games = 1

[analysis]
track_blunders_for = "mockengine"
engine = "mockengine2"
time_per_move = "1s"
""")
        _run(tmp_path, "--config", str(config_path), "--play", "--analyze", "--tag", "staticnames")

        series_dir = tmp_path / "series-staticnames"
        files = sorted([f.name for f in series_dir.iterdir()])
        assert "games.pgn" in files
        assert "games.log" in files
        assert "games-analyzed.pgn" in files
        assert "blunders.csv" in files
