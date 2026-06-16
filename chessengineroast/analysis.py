from __future__ import annotations

import csv
from pathlib import Path

import chess
import chess.pgn
import chess.polyglot

from chessengineroast.config import SeriesConfig
from chessengineroast.engine import (
    EngineProcess,
    _book_path,
    parse_bestmove,
)
from chessengineroast.game import log


def _parse_time_per_move(raw: str) -> int:
    raw = raw.strip().lower()
    if raw.endswith("ms"):
        return int(raw[:-2])
    if raw.endswith("s"):
        return int(float(raw[:-1]) * 1000)
    try:
        return int(raw)
    except ValueError:
        return 1000


def analyze_series(config: SeriesConfig, pgn_path: str, log_file: str,
                   blunders_csv_path: str, analyzed_pgn_path: str) -> None:
    if not config.has_analysis():
        raise ValueError("analysis section missing engine and time_per_move in config")

    movetime_ms = _parse_time_per_move(config.analysis_time_per_move)

    analysis_engine = EngineProcess(
        config.analysis_engine,
        options=config.options_for(config.analysis_engine),
    )
    analysis_engine.start()

    csv_path = Path(blunders_csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_file = open(csv_path, "w", newline="")
    csv_writer = csv.DictWriter(
        csv_file,
        fieldnames=["fen", "blunder_move", "eval_before", "eval_after", "eval_delta"],
    )
    csv_writer.writeheader()
    csv_file.flush()

    try:
        book = None
        try:
            book = chess.polyglot.open_reader(_book_path())
        except (FileNotFoundError, OSError):
            pass

        blunders: list[dict] = []
        analyzed_games: list[chess.pgn.Game] = []

        with open(pgn_path) as f:
            game_number = 0
            while True:
                game = chess.pgn.read_game(f)
                if game is None:
                    break
                game_number += 1
                analysis_engine.send_only("ucinewgame")

                blunders_in_game, annotated_game = _analyze_game(
                    game, game_number, config, analysis_engine, movetime_ms, book, log_file,
                    csv_writer=csv_writer,
                )
                blunders.extend(blunders_in_game)
                analyzed_games.append(annotated_game)
                csv_file.flush()
                log(f"analysis: game {game_number} analyzed, {len(blunders_in_game)} blunders found", log_file)

        if book:
            book.close()

    finally:
        csv_file.close()
        analysis_engine.stop()

    _write_analyzed_pgn(analyzed_pgn_path, analyzed_games)


def _analyze_game(
    game: chess.pgn.Game,
    game_number: int,
    config: SeriesConfig,
    analysis_engine: EngineProcess,
    movetime_ms: int,
    book: chess.polyglot.MemoryMappedReader | None,
    log_file: str,
    csv_writer=None,
) -> tuple[list[dict], chess.pgn.Game]:
    board = game.board()
    blunders: list[dict] = []
    moves = list(game.mainline_moves())
    annotated_game = chess.pgn.Game()
    for k, v in game.headers.items():
        annotated_game.headers[k] = v
    annotated_game.headers["AnalyzedBy"] = config.analysis_engine
    annotated_game.headers["AnalysisTimePerMove"] = config.analysis_time_per_move

    node = annotated_game

    subject_is_white = (
        config.track_blunders_for
        and config.track_blunders_for == game.headers.get("White", "")
    )
    subject_is_black = (
        config.track_blunders_for
        and config.track_blunders_for == game.headers.get("Black", "")
    )

    for i, move in enumerate(moves):
        in_book = _is_in_book(board, book)

        if not in_book:
            engine_fen = board.fen()
            analysis_engine.send_position(engine_fen)

            _, score_before = analysis_engine.send_go_movetime_score(movetime_ms)
            # Engine outputs cp from side-to-move perspective; normalise to White POV
            if score_before is not None and board.turn == chess.BLACK:
                score_before = -score_before

            if score_before is not None:
                hopeless = (
                    (subject_is_white and board.turn == chess.WHITE and score_before < -config.equal_range * 100)
                    or (subject_is_black and board.turn == chess.BLACK and score_before > config.equal_range * 100)
                )
                if hopeless:
                    log(
                        f"stopped: game {game_number}, {move.uci()}, "
                        f"eval {score_before/100:.2f} beyond {config.equal_range} range for subject",
                        log_file,
                    )
                    eval_comment = f"[{score_before/100:+.2f} analysis truncated]"
                    node.comment = eval_comment
                    board.push(move)
                    node = node.add_variation(move)
                    break

            board.push(move)

            analysis_engine.send_position(board.fen())
            _, score_after = analysis_engine.send_go_movetime_score(movetime_ms)
            if score_after is not None and board.turn == chess.BLACK:
                score_after = -score_after

            is_blunder, score_diff = detect_blunder(
                score_before=score_before,
                score_after=score_after,
                board_turn_after_move=board.turn,
                equal_range=config.equal_range,
                blunder_delta=config.blunder_delta,
            )

            current_player = "white" if board.turn == chess.BLACK else "black"

            is_subject = (
                config.track_blunders_for
                and current_player == "white"
                and config.track_blunders_for == game.headers.get("White", "")
            ) or (
                config.track_blunders_for
                and current_player == "black"
                and config.track_blunders_for == game.headers.get("Black", "")
            )

            if is_subject and is_blunder:
                blunders.append({
                    "fen": engine_fen,
                    "blunder_move": move.uci(),
                    "eval_before": score_before / 100 if score_before is not None else 0.0,
                    "eval_after": score_after / 100 if score_after is not None else 0.0,
                    "eval_delta": score_diff / 100,
                })
                if csv_writer is not None:
                    csv_writer.writerow(blunders[-1])
                log(
                    f"blunder: game {game_number}, {move.uci()}, "
                    f"fen {engine_fen}, "
                    f"eval {score_before/100:.2f} -> {score_after/100:.2f} "
                    f"(delta {score_diff/100:.2f})",
                    log_file,
                )
            elif is_subject and score_before is not None and score_after is not None:
                log(
                    f"no blunder: game {game_number}, {move.uci()}, "
                    f"eval {score_before/100:.2f} -> {score_after/100:.2f} "
                    f"(delta {score_diff/100:.2f}, near_equal={abs(score_before) <= config.equal_range * 100}, "
                    f"big_swing={score_diff >= config.blunder_delta * 100}, "
                    f"player={current_player}, subject={'White' if config.track_blunders_for == game.headers.get('White', '') else 'Black' if config.track_blunders_for == game.headers.get('Black', '') else '?'})",
                    log_file,
                )

            eval_comment = f"[{score_before/100:+.2f}]" if score_before is not None else ""
            node.comment = eval_comment

            board.pop()
        else:
            eval_comment = "[book]"
            node.comment = eval_comment

        board.push(move)
        node = node.add_variation(move)

    annotated_game.headers["Result"] = game.headers.get("Result", "*")
    return blunders, annotated_game


def _is_in_book(board: chess.Board, book: chess.polyglot.MemoryMappedReader | None) -> bool:
    if book is None:
        return False
    try:
        return book.find(board) is not None
    except (IndexError, OSError):
        return False


def detect_blunder(
    score_before: int | None,
    score_after: int | None,
    board_turn_after_move: chess.Color,
    equal_range: float,
    blunder_delta: float,
) -> tuple[bool, int]:
    """Detect if a single move is a blunder.

    UCI scores are always from White's perspective in centipawns.
    After board.push(move), board_turn_after_move is the *opponent* of
    whoever just moved.

    A blunder means the eval swung against the player who moved:
    - White moved (board.turn == BLACK): score_after < score_before
    - Black moved (board.turn == WHITE): score_after > score_before
    """
    if score_before is None or score_after is None:
        return False, 0

    if board_turn_after_move == chess.BLACK:
        score_diff = score_before - score_after
    else:
        score_diff = score_after - score_before

    near_equal = abs(score_before) <= equal_range * 100
    big_swing = score_diff >= blunder_delta * 100

    return near_equal and big_swing, score_diff


def _write_analyzed_pgn(output_path: str, games: list[chess.pgn.Game]) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for game in games:
            print(game, file=f, end="\n\n")
