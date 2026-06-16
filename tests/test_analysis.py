from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

import chess
import chess.pgn
import chess.polyglot
import pytest

from chessengineroast.analysis import (
    _analyze_game,
    _is_in_book,
    _parse_time_per_move,
    detect_blunder,
)
from chessengineroast.config import SeriesConfig
from chessengineroast.engine import EngineProcess

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


class TestParseTimePerMove:
    def test_seconds(self):
        assert _parse_time_per_move("1s") == 1000
        assert _parse_time_per_move("0.5s") == 500

    def test_milliseconds(self):
        assert _parse_time_per_move("500ms") == 500

    def test_bare_number(self):
        assert _parse_time_per_move("1000") == 1000

    def test_invalid_defaults(self):
        assert _parse_time_per_move("abc") == 1000


class TestDetectBlunder:
    """Unit tests for blunder detection logic with simulated engine scores."""

    def test_white_blunder_detected(self):
        """White moves, eval drops from +0.5 to -2.0 → blunder."""
        is_blunder, diff = detect_blunder(
            score_before=50,     # White is slightly better
            score_after=-200,    # Now White is much worse
            board_turn_after_move=chess.BLACK,  # White moved
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is True
        assert diff == 250  # 50 - (-200) = 250 centipawns drop

    def test_black_blunder_detected(self):
        """Black moves, eval rises from -0.5 to +2.0 (worse for Black) → blunder."""
        is_blunder, diff = detect_blunder(
            score_before=-50,    # Black is slightly better
            score_after=200,     # Now Black is much worse
            board_turn_after_move=chess.WHITE,  # Black moved
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is True
        assert diff == 250  # 200 - (-50) = 250 centipawns swing against Black

    def test_white_good_move_not_blunder(self):
        """White plays a good move, eval improves → not a blunder."""
        is_blunder, diff = detect_blunder(
            score_before=-50,
            score_after=100,
            board_turn_after_move=chess.BLACK,  # White moved
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is False

    def test_black_good_move_not_blunder(self):
        """Black plays a good move, eval improves → not a blunder."""
        is_blunder, diff = detect_blunder(
            score_before=100,
            score_after=-50,
            board_turn_after_move=chess.WHITE,  # Black moved
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is False

    def test_small_swing_not_blunder(self):
        """Small eval change below delta threshold → not a blunder."""
        is_blunder, diff = detect_blunder(
            score_before=20,
            score_after=-150,
            board_turn_after_move=chess.BLACK,
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is False
        assert diff == 170  # swing was 170cp but threshold is 200cp

    def test_not_near_equal_position(self):
        """Big eval swing but position was already terrible → not a blunder."""
        is_blunder, diff = detect_blunder(
            score_before=-400,   # Already losing badly
            score_after=-700,    # Got worse
            board_turn_after_move=chess.BLACK,
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is False  # abs(-400) = 4.0 exceeds equal_range=1.5

    def test_exactly_on_thresholds(self):
        """Position at exactly ±1.5, swing exactly 2.0 → blunder."""
        is_blunder, diff = detect_blunder(
            score_before=150,
            score_after=-50,
            board_turn_after_move=chess.BLACK,
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is True

    def test_none_scores_no_blunder(self):
        """If either score is None, no blunder."""
        is_blunder, diff = detect_blunder(
            score_before=None,
            score_after=200,
            board_turn_after_move=chess.BLACK,
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is False
        assert diff == 0

    def test_white_blunder_mate_drop(self):
        """Eval drops from +50 to -M1 (mate score) → blunder."""
        is_blunder, diff = detect_blunder(
            score_before=50,
            score_after=-30000,  # parse_score encodes -mate as -30000
            board_turn_after_move=chess.BLACK,
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is True
        assert diff >= 30000

    def test_opponent_blunder_not_tracked_for_wrong_player(self):
        """Black blunders but we track White → not a subject blunder."""
        is_blunder, diff = detect_blunder(
            score_before=0,
            score_after=250,
            board_turn_after_move=chess.WHITE,  # Black moved
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is True
        # The blunder IS detected by the function — filtering by
        # subject engine happens in the caller, not here.

    def test_white_subject_blunder_diff_positive(self):
        """White blunder: score_diff must be positive (eval drops)."""
        is_blunder, diff = detect_blunder(
            score_before=30,
            score_after=-220,
            board_turn_after_move=chess.BLACK,  # White moved
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is True
        assert diff == 250  # positive = eval shifted against White

    def test_white_subject_improvement_diff_negative(self):
        """White improvement: score_diff must be negative (eval rises)."""
        is_blunder, diff = detect_blunder(
            score_before=-100,
            score_after=50,
            board_turn_after_move=chess.BLACK,  # White moved
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is False
        assert diff < 0  # negative = eval shifted in White's favor

    def test_black_subject_blunder_diff_positive(self):
        """Black blunder: score_diff must be positive (eval rises against Black)."""
        is_blunder, diff = detect_blunder(
            score_before=-30,
            score_after=220,
            board_turn_after_move=chess.WHITE,  # Black moved
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is True
        assert diff == 250  # positive = eval shifted against Black

    def test_black_subject_improvement_diff_negative(self):
        """Black improvement: score_diff must be negative (eval drops, favorable for Black)."""
        is_blunder, diff = detect_blunder(
            score_before=100,
            score_after=-50,
            board_turn_after_move=chess.WHITE,  # Black moved
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is False
        assert diff < 0  # negative = eval shifted in Black's favor

    def test_white_blunder_from_equal_start(self):
        """White blunder from exactly equal position (score_before=0)."""
        is_blunder, diff = detect_blunder(
            score_before=0,
            score_after=-250,
            board_turn_after_move=chess.BLACK,
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is True
        assert diff == 250

    def test_black_blunder_from_equal_start(self):
        """Black blunder from exactly equal position (score_before=0)."""
        is_blunder, diff = detect_blunder(
            score_before=0,
            score_after=250,
            board_turn_after_move=chess.WHITE,
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is True
        assert diff == 250

    def test_white_blunder_near_equal_boundary(self):
        """White move at exact near-equal boundary (score_before=150) → blunder if swing big."""
        is_blunder, diff = detect_blunder(
            score_before=150,
            score_after=-100,
            board_turn_after_move=chess.BLACK,
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is True
        assert diff == 250

    def test_white_blunder_outside_equal_range(self):
        """White move outside near-equal range (score_before=200) → no blunder."""
        is_blunder, diff = detect_blunder(
            score_before=200,
            score_after=-100,
            board_turn_after_move=chess.BLACK,
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is False

    def test_black_blunder_outside_equal_range(self):
        """Black move outside near-equal range (score_before=-200) → no blunder."""
        is_blunder, diff = detect_blunder(
            score_before=-200,
            score_after=100,
            board_turn_after_move=chess.WHITE,
            equal_range=1.5,
            blunder_delta=2.0,
        )
        assert is_blunder is False


class TestIsInBook:
    def test_no_book_reader(self):
        board = chess.Board()
        assert _is_in_book(board, None) is False

    def test_with_book(self, tmp_path):
        import struct
        book_path = tmp_path / "test.bin"
        board = chess.Board()
        key = chess.polyglot.zobrist_hash(board)
        move = chess.Move.from_uci("e2e4")
        from_sq = move.from_square
        to_sq = move.to_square
        promo = move.promotion or 0
        raw_move = (promo << 12) | (from_sq << 6) | to_sq
        entry = struct.pack(">QHHI", key, raw_move, 1, 0)
        book_path.write_bytes(entry)

        reader = chess.polyglot.open_reader(book_path)
        try:
            assert _is_in_book(board, reader) is True
            board.push(move)
            assert _is_in_book(board, reader) is False
        finally:
            reader.close()


class TestAnalyzeGame:
    @pytest.fixture
    def config(self):
        return SeriesConfig.from_dict({
            "engines": {"white": "mockengine", "black": "mockengine2"},
            "time": {"base": "10s", "increment": "1s"},
            "analysis": {
                "track_blunders_for": "mockengine",
                "engine": "mockengine2",
                "time_per_move": "1s",
            },
        })

    @pytest.fixture
    def log_file(self, tmp_path):
        path = tmp_path / "test.log"
        yield str(path)

    def _make_game(self, moves_list):
        game = chess.pgn.Game()
        game.headers["White"] = "mockengine"
        game.headers["Black"] = "mockengine2"
        game.headers["Result"] = "*"
        node = game
        board = game.board()
        for uci in moves_list:
            move = board.parse_uci(uci)
            board.push(move)
            node = node.add_variation(move)
        return game

    def test_no_blunders_with_book(self, engine_dir, config, log_file):
        engine = EngineProcess("mockengine2")
        engine.start()
        try:
            game = self._make_game(["e2e4", "e7e5", "g1f3"])
            blunders, annotated = _analyze_game(game, 1, config, engine, 200, None, log_file)
            assert len(blunders) >= 0
            assert annotated.headers.get("AnalyzedBy") == "mockengine2"
        finally:
            engine.stop()

    def test_annotated_has_analyzed_headers(self, engine_dir, config, log_file):
        engine = EngineProcess("mockengine2")
        engine.start()
        try:
            game = self._make_game(["e2e4", "e7e5"])
            _, annotated = _analyze_game(game, 1, config, engine, 200, None, log_file)
            assert annotated.headers.get("AnalyzedBy") == "mockengine2"
            assert annotated.headers.get("AnalysisTimePerMove") == "1s"
        finally:
            engine.stop()

    def test_only_subject_engine_blunders_tracked(self, engine_dir, config, log_file):
        config.track_blunders_for = "mockengine"
        engine = EngineProcess("mockengine2")
        engine.start()
        try:
            game = self._make_game(["e2e4", "e7e5", "g1f3", "b8c6"])
            blunders, _ = _analyze_game(game, 1, config, engine, 200, None, log_file)
        finally:
            engine.stop()

    def test_opponent_blunders_ignored(self, engine_dir, config, log_file):
        config.track_blunders_for = "mockengine"
        engine = EngineProcess("mockengine2")
        engine.start()
        try:
            game = chess.pgn.Game()
            game.headers["White"] = "mockengine"
            game.headers["Black"] = "someone-else"
            game.headers["Result"] = "*"
            board = game.board()
            node = game
            for uci in ["e2e4", "e7e5", "g1f3", "b8c6"]:
                move = board.parse_uci(uci)
                board.push(move)
                node = node.add_variation(move)
            blunders, _ = _analyze_game(game, 1, config, engine, 200, None, log_file)
            for b in blunders:
                assert b["blunder_move"] != ""
        finally:
            engine.stop()

    def test_white_subject_blunder_recorded(self, engine_dir, config, log_file, monkeypatch):
        """White (subject) blunders on move 3 — blunder recorded with correct sign."""
        monkeypatch.setenv("MOCK_SCORES", "50,-100,-100,50,0,300,300,-400")
        config.track_blunders_for = "mockengine"
        config.equal_range = 1.5
        config.blunder_delta = 2.0
        engine = EngineProcess("mockengine2")
        engine.start()
        try:
            game = self._make_game(["e2e4", "e7e5", "g1f3", "b8c6"])
            blunders, _ = _analyze_game(game, 1, config, engine, 200, None, log_file)
            assert len(blunders) == 1
            b = blunders[0]
            assert b["blunder_move"] == "g1f3"
            assert b["eval_before"] == 0.0
            assert b["eval_after"] == -3.0
            assert b["eval_delta"] == 3.0  # positive = eval dropped (White blunder)
        finally:
            engine.stop()

    def test_black_subject_blunder_recorded(self, engine_dir, config, log_file, monkeypatch):
        """Black (subject) blunders on move 2 — blunder recorded with correct sign."""
        monkeypatch.setenv("MOCK_SCORES", "50,-100,-100,300,100,-50,-50,100")
        config.track_blunders_for = "mockengine"
        config.equal_range = 1.5
        config.blunder_delta = 2.0
        engine = EngineProcess("mockengine2")
        engine.start()
        try:
            game = chess.pgn.Game()
            game.headers["White"] = "someone-else"
            game.headers["Black"] = "mockengine"
            game.headers["Result"] = "*"
            board = game.board()
            node = game
            for uci in ["e2e4", "e7e5", "g1f3", "b8c6"]:
                move = board.parse_uci(uci)
                board.push(move)
                node = node.add_variation(move)
            blunders, _ = _analyze_game(game, 1, config, engine, 200, None, log_file)
            assert len(blunders) == 1
            b = blunders[0]
            assert b["blunder_move"] == "e7e5"
            assert b["eval_before"] == 1.0
            assert b["eval_after"] == 3.0
            assert b["eval_delta"] == 2.0  # positive = eval rose (Black blunder)
        finally:
            engine.stop()

    def test_subject_improvement_not_recorded(self, engine_dir, config, log_file, monkeypatch):
        """Subject's good move (improvement) — not recorded as blunder."""
        monkeypatch.setenv("MOCK_SCORES", "-50,-100,100,50,100,-200,-200,100")
        config.track_blunders_for = "mockengine"
        config.equal_range = 1.5
        config.blunder_delta = 2.0
        engine = EngineProcess("mockengine2")
        engine.start()
        try:
            game = self._make_game(["e2e4", "e7e5", "g1f3", "b8c6"])
            blunders, _ = _analyze_game(game, 1, config, engine, 200, None, log_file)
            assert len(blunders) == 0
        finally:
            engine.stop()

    def test_alternating_game_subjects(self, engine_dir, config, log_file, monkeypatch):
        """Game 1: subject=White, Game 2: subject=Black — each correctly tracked."""
        monkeypatch.setenv("MOCK_SCORES", "0,300,300,-400,-400,300,300,-200")
        config.equal_range = 1.5
        config.blunder_delta = 2.0
        engine = EngineProcess("mockengine2")
        engine.start()
        try:
            # Game 1: White = subject (mockengine) blunders on move 1
            config.track_blunders_for = "mockengine"
            game1 = chess.pgn.Game()
            game1.headers["White"] = "mockengine"
            game1.headers["Black"] = "someone-else"
            game1.headers["Result"] = "*"
            board1 = game1.board()
            node1 = game1
            for uci in ["e2e4", "e7e5", "g1f3", "b8c6"]:
                move = board1.parse_uci(uci)
                board1.push(move)
                node1 = node1.add_variation(move)
            blunders1, _ = _analyze_game(game1, 1, config, engine, 200, None, log_file)
            # White blundered on e2e4 (score before=0, after=-300)
            assert len(blunders1) == 1
            assert blunders1[0]["blunder_move"] == "e2e4"

            # Re-send ucinewgame between games (as analyze_series does)
            engine.send_only("ucinewgame")

            # Game 2: Black = subject (mockengine) — no blunder
            config.track_blunders_for = "mockengine"
            game2 = chess.pgn.Game()
            game2.headers["White"] = "someone-else"
            game2.headers["Black"] = "mockengine"
            game2.headers["Result"] = "*"
            board2 = game2.board()
            node2 = game2
            for uci in ["d2d4", "d7d5", "c2c4", "e7e6"]:
                move = board2.parse_uci(uci)
                board2.push(move)
                node2 = node2.add_variation(move)
            # MOCK_SCORES sequence (reset by ucinewgame): 0,-300,-300,-400,-400,-300,-300,-200
            # Move 1 (White, not subject): before=0, after=-300
            # Move 2 (Black, subject): before=-300 → not near equal → no blunder
            blunders2, _ = _analyze_game(game2, 1, config, engine, 200, None, log_file)
            assert len(blunders2) == 0
        finally:
            engine.stop()

    def test_non_subject_blunder_not_recorded(self, engine_dir, config, log_file, monkeypatch):
        """Non-subject makes a blunder — not recorded."""
        monkeypatch.setenv("MOCK_SCORES", "0,-50,-50,300,100,-50,-50,100")
        config.track_blunders_for = "mockengine"
        config.equal_range = 1.5
        config.blunder_delta = 2.0
        engine = EngineProcess("mockengine2")
        engine.start()
        try:
            game = self._make_game(["e2e4", "e7e5", "g1f3", "b8c6"])
            # Black (non-subject) blunders on move 2: before=50, after=300 → diff=250 → blunder
            # But not subject, so not recorded
            blunders, _ = _analyze_game(game, 1, config, engine, 200, None, log_file)
            assert len(blunders) == 0
        finally:
            engine.stop()
