from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path

import chess
import chess.pgn
import pytest

from chessengineroast.config import ConfigError, SeriesConfig, TimeControl
from chessengineroast.engine import (
    EngineError,
    EngineProcess,
    EngineTimeout,
    discover_engines,
    parse_bestmove,
    parse_score,
    resolve_engine_path,
)

MOCK_ENGINE_SRC = Path(__file__).parent / "mock_engine.py"


@pytest.fixture
def engine_dir(monkeypatch, tmp_path):
    """Create mock engines in a temp dir, set env var."""
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


class TestTimeControl:
    def test_parse_seconds(self):
        assert TimeControl._parse_seconds("3m") == 180
        assert TimeControl._parse_seconds("2s") == 2
        assert TimeControl._parse_seconds("1h") == 3600
        assert TimeControl._parse_seconds("3m 2s") == 182
        assert TimeControl._parse_seconds("300") == 300

    def test_parse_seconds_zero(self):
        with pytest.raises(ConfigError, match="positive"):
            TimeControl._parse_seconds("0s")
        with pytest.raises(ConfigError, match="positive"):
            TimeControl._parse_seconds("0")

    def test_parse_seconds_invalid(self):
        with pytest.raises(ConfigError, match="invalid time value"):
            TimeControl._parse_seconds("abc")

    def test_from_toml(self):
        tc = TimeControl.from_toml({"base": "3m", "increment": "2s"})
        assert tc.base == 180
        assert tc.increment == 2

    def test_from_toml_missing(self):
        with pytest.raises(ConfigError):
            TimeControl.from_toml({})
        with pytest.raises(ConfigError):
            TimeControl.from_toml({"base": "3m"})

    def test_move_timeout(self):
        tc = TimeControl(base=180, increment=2)
        assert tc.move_timeout == 60


class TestSeriesConfig:
    def test_minimal(self):
        data = {
            "engines": {"white": "engine-a", "black": "engine-b"},
            "time": {"base": "3m", "increment": "2s"},
        }
        config = SeriesConfig.from_dict(data)
        assert config.white == "engine-a"
        assert config.black == "engine-b"
        assert config.games == 1
        assert config.output_raw == "engine-a-vs-engine-b.pgn"
        assert config.has_analysis() is False

    def test_full(self):
        data = {
            "engines": {"white": "exp", "black": "stockfish"},
            "time": {"base": "5m", "increment": "3s"},
            "matches": {"games": 10},
            "output": {
                "raw": "series/test.pgn",
                "analyzed": "series/test-analyzed.pgn",
                "blunders": "series/test-blunders.csv",
            },
            "analysis": {
                "track_blunders_for": "exp",
                "engine": "stockfish",
                "time_per_move": "1s",
            },
            "blunder_detection": {"equal_range": 2.0, "blunder_delta": 3.0},
            "engine_options": {
                "stockfish": {"Hash": "128", "Threads": "4"},
                "exp": {"Hash": "64"},
            },
        }
        config = SeriesConfig.from_dict(data)
        assert config.games == 10
        assert config.output_raw == "series/test.pgn"
        assert config.output_analyzed == "series/test-analyzed.pgn"
        assert config.output_blunders == "series/test-blunders.csv"
        assert config.track_blunders_for == "exp"
        assert config.equal_range == 2.0
        assert config.blunder_delta == 3.0
        assert config.has_analysis() is True
        assert config.options_for("stockfish") == {"Hash": "128", "Threads": "4"}
        assert config.options_for("exp") == {"Hash": "64"}
        assert config.options_for("nonexistent") == {}

    def test_missing_engines(self):
        with pytest.raises(ConfigError, match="required"):
            SeriesConfig.from_dict({"time": {"base": "3m", "increment": "2s"}})

    def test_games_less_than_one(self):
        with pytest.raises(ConfigError, match="at least 1"):
            SeriesConfig.from_dict({
                "engines": {"white": "a", "black": "b"},
                "time": {"base": "3m", "increment": "2s"},
                "matches": {"games": 0},
            })

    def test_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""\
[engines]
white = "a"
black = "b"

[time]
base = "3m"
increment = "2s"
""")
            f.flush()
            config = SeriesConfig.from_file(f.name)
        os.unlink(f.name)
        assert config.white == "a"


class TestEngineDiscovery:
    def test_discover_engines(self, engine_dir):
        assert sorted(discover_engines()) == ["mockengine", "mockengine2"]

    def test_discover_skips_non_executable(self, monkeypatch, tmp_path):
        eng_dir = tmp_path / "eng"
        monkeypatch.setenv("CHESSENGINE_ROAST_ENGINES_DIR", str(eng_dir))
        (eng_dir / "broken").mkdir(parents=True)
        (eng_dir / "broken" / "broken").touch(mode=0o644)
        assert discover_engines() == []

    def test_discover_skips_no_matching_binary(self, monkeypatch, tmp_path):
        eng_dir = tmp_path / "eng"
        monkeypatch.setenv("CHESSENGINE_ROAST_ENGINES_DIR", str(eng_dir))
        (eng_dir / "mydir").mkdir(parents=True)
        (eng_dir / "mydir" / "other").touch(mode=0o755)
        assert discover_engines() == []

    def test_resolve_engine_path(self, engine_dir):
        path = resolve_engine_path("mockengine")
        assert path.name == "mockengine"

    def test_resolve_not_found(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CHESSENGINE_ROAST_ENGINES_DIR", str(tmp_path))
        with pytest.raises(EngineError, match="not found"):
            resolve_engine_path("nonexistent")


class TestParseBestmove:
    def test_normal(self):
        assert parse_bestmove("bestmove e2e4 ponder d7d5") == "e2e4"

    def test_no_ponder(self):
        assert parse_bestmove("bestmove e2e4") == "e2e4"

    def test_none_move(self):
        assert parse_bestmove("bestmove (none)") == ""

    def test_no_bestmove(self):
        assert parse_bestmove("info score cp 50") == ""


class TestParseScore:
    def test_cp(self):
        assert parse_score("info score cp 50") == 50
        assert parse_score("info score cp -30") == -30
        assert parse_score("info depth 10 score cp 100 nodes 1000") == 100

    def test_mate(self):
        assert parse_score("info score mate 3") == 30000
        assert parse_score("info score mate -2") == -30000

    def test_no_score(self):
        assert parse_score("info depth 10 nodes 1000") is None


class TestEngineProcess:
    def test_start_stop(self, engine_dir):
        eng = EngineProcess("mockengine")
        eng.start()
        assert eng.is_alive()
        eng.stop()
        assert not eng.is_alive()

    def test_options_passed(self, engine_dir):
        eng = EngineProcess("mockengine", options={"Hash": "256"})
        eng.start()
        eng.stop()

    def test_timeout(self, engine_dir):
        os.environ["MOCK_BEHAVIOR"] = "hang"
        try:
            eng = EngineProcess("mockengine")
            eng.start()
            with pytest.raises(EngineTimeout):
                eng.send_go_movetime(100, timeout=1)
        finally:
            eng.stop()
            os.environ.pop("MOCK_BEHAVIOR", None)

    def test_crash_detected(self, engine_dir):
        os.environ["MOCK_BEHAVIOR"] = "crash"
        try:
            eng = EngineProcess("mockengine")
            eng.start()
            with pytest.raises(EngineError, match="exited"):
                eng.send_go_movetime(100, timeout=2)
        finally:
            os.environ.pop("MOCK_BEHAVIOR", None)
            try:
                eng.stop()
            except Exception:
                pass
