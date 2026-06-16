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


class TestCliPlay:
    def test_play_single_game(self, tmp_path):
        _setup_engines_in_dir(tmp_path)
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"

[output]
raw = "test_output.pgn"
""")
        result = _run(tmp_path, "--play", str(config_path))
        log_files = list(tmp_path.glob("test_output*.log"))
        assert len(log_files) > 0, f"stdout: {result.stdout}, stderr: {result.stderr}"
        with open(log_files[0]) as f:
            content = f.read()
        assert "[Game 1]" in content

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

[output]
raw = "results.pgn"
""")
        result = _run(tmp_path, "--play", str(config_path))
        pgn_files = list(tmp_path.glob("results*.pgn"))
        assert len(pgn_files) > 0, f"No PGN found, stdout: {result.stdout}, stderr: {result.stderr}"

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
        result = _run(tmp_path, "--play", str(config_path))
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

[output]
raw = "results2.pgn"

[engine_options.mockengine]
Hash = "64"
""")
        result = _run(tmp_path, "--play", str(config_path))
        pgn_files = list(tmp_path.glob("results2*.pgn"))
        assert len(pgn_files) > 0, f"stdout: {result.stdout}, stderr: {result.stderr}"


class TestCliAnalyze:
    def test_analyze_missing_analysis_section(self, tmp_path):
        config_path = tmp_path / "test.toml"
        config_path.write_text("""\
[engines]
white = "mockengine"
black = "mockengine2"

[time]
base = "10s"
increment = "1s"

[output]
raw = "results3.pgn"
""")
        result = _run(tmp_path, "--analyze", str(config_path))
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

[output]
raw = "analyze_test.pgn"
analyzed = "analyze_test_annotated.pgn"
blunders = "analyze_test_blunders.csv"

[analysis]
track_blunders_for = "mockengine"
engine = "mockengine2"
time_per_move = "1s"
""")
        play_result = _run(tmp_path, "--play", str(config_path))

        pgn_files = list(tmp_path.glob("analyze_test*.pgn"))
        assert len(pgn_files) > 0, f"No PGN found, stdout: {play_result.stdout}, stderr: {play_result.stderr}"

        analyze_result = _run(tmp_path, "--analyze", str(config_path))
        assert "Analysis complete" in analyze_result.stdout
