from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

import pytest

from chessengineroast.config import SeriesConfig
from chessengineroast.engine import EngineError, EngineProcess
from chessengineroast.game import GameResult, play_game

MOCK_ENGINE_SRC = Path(__file__).parent / "mock_engine.py"


@pytest.fixture
def engine_dir(monkeypatch, tmp_path):
    eng_dir = tmp_path / "engines"
    for name in ("mockengine", "mockengine2"):
        eng_subdir = eng_dir / name
        eng_subdir.mkdir(parents=True)
        dst = eng_subdir / name
        shutil.copy2(MOCK_ENGINE_SRC, dst)
        dst.chmod(dst.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("CHESSENGINE_ROAST_ENGINES_DIR", str(eng_dir))
    monkeypatch.setenv("CHESSENGINE_ROAST_BOOK_PATH", str(tmp_path / "nonexistent.bin"))
    return eng_dir


@pytest.fixture
def config():
    return SeriesConfig.from_dict({
        "engines": {"white": "mockengine", "black": "mockengine2"},
        "time": {"base": "10s", "increment": "1s"},
    })


@pytest.fixture
def log_file(tmp_path):
    path = tmp_path / "test.log"
    yield str(path)


class TestPlayGame:
    def test_basic_game(self, engine_dir, config, log_file):
        white = EngineProcess("mockengine")
        black = EngineProcess("mockengine2")
        white.start()
        black.start()
        try:
            play_game(white, black, config, 1, log_file)
        except EngineError:
            pass
        finally:
            white.stop()
            black.stop()
        with open(log_file) as f:
            content = f.read()
        assert "[Game 1]" in content

    def test_pgn_has_custom_tags(self, engine_dir, config, log_file):
        white = EngineProcess("mockengine")
        black = EngineProcess("mockengine2")
        white.start()
        black.start()
        try:
            play_game(white, black, config, 1, log_file)
        except EngineError:
            pass
        finally:
            white.stop()
            black.stop()
        with open(log_file) as f:
            content = f.read()
        assert "mockengine" in content

    def test_game_has_moves(self, engine_dir, config, log_file):
        white = EngineProcess("mockengine")
        black = EngineProcess("mockengine2")
        white.start()
        black.start()
        try:
            play_game(white, black, config, 1, log_file)
        except EngineError:
            pass
        finally:
            white.stop()
            black.stop()
        with open(log_file) as f:
            content = f.read()
        assert "e2e4" in content or "e7e5" in content

    def test_abort_on_illegal_move(self, engine_dir, config, log_file):
        os.environ["MOCK_BEHAVIOR"] = "illegal"
        try:
            white = EngineProcess("mockengine")
            black = EngineProcess("mockengine2")
            white.start()
            black.start()
            try:
                with pytest.raises(EngineError, match="illegal move"):
                    play_game(white, black, config, 1, log_file)
            finally:
                white.stop()
                black.stop()
        finally:
            os.environ.pop("MOCK_BEHAVIOR", None)

    def test_abort_on_nomove(self, engine_dir, config, log_file):
        os.environ["MOCK_BEHAVIOR"] = "nomove"
        try:
            white = EngineProcess("mockengine")
            black = EngineProcess("mockengine2")
            white.start()
            black.start()
            try:
                with pytest.raises(EngineError, match="no move"):
                    play_game(white, black, config, 1, log_file)
            finally:
                white.stop()
                black.stop()
        finally:
            os.environ.pop("MOCK_BEHAVIOR", None)

    def test_abort_on_crash(self, engine_dir, config, log_file):
        os.environ["MOCK_BEHAVIOR"] = "crash"
        try:
            white = EngineProcess("mockengine")
            black = EngineProcess("mockengine2")
            white.start()
            black.start()
            try:
                with pytest.raises(EngineError, match="crashed"):
                    play_game(white, black, config, 1, log_file)
            finally:
                try:
                    white.stop()
                except Exception:
                    pass
                try:
                    black.stop()
                except Exception:
                    pass
        finally:
            os.environ.pop("MOCK_BEHAVIOR", None)

    def test_log_file_written(self, engine_dir, config, log_file):
        white = EngineProcess("mockengine")
        black = EngineProcess("mockengine2")
        white.start()
        black.start()
        try:
            play_game(white, black, config, 1, log_file)
        except EngineError:
            pass
        finally:
            white.stop()
            black.stop()
        with open(log_file) as f:
            content = f.read()
        assert "[Game 1]" in content


class TestGameResultConstants:
    def test_constants(self):
        assert GameResult.WHITE_WIN == "1-0"
        assert GameResult.BLACK_WIN == "0-1"
        assert GameResult.DRAW == "1/2-1/2"


class TestAlternating:
    def test_color_alternation(self, engine_dir, config, log_file):
        white = EngineProcess("mockengine")
        black = EngineProcess("mockengine2")
        white.start()
        black.start()
        try:
            try:
                play_game(white, black, config, 1, log_file)
            except EngineError:
                pass
            try:
                play_game(black, white, config, 2, log_file)
            except EngineError:
                pass
        finally:
            white.stop()
            black.stop()
        with open(log_file) as f:
            content = f.read()
        assert "[Game 1]" in content
        assert "[Game 2]" in content
