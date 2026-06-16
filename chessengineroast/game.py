from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import chess
import chess.engine
import chess.pgn
import chess.polyglot

from chessengineroast.config import SeriesConfig
from chessengineroast.engine import (
    EngineError,
    EngineProcess,
    EngineTimeout,
    _book_path,
    parse_bestmove,
)


class GameResult:
    WHITE_WIN = "1-0"
    BLACK_WIN = "0-1"
    DRAW = "1/2-1/2"
    FORFEIT_WHITE = "0-1"
    FORFEIT_BLACK = "1-0"


@dataclass
class GameRecord:
    board: chess.Board
    pgn: chess.pgn.Game
    moves: list[str] = field(default_factory=list)
    book_exit_ply: int = -1
    result: str = "*"
    forfeit: bool = False
    crash_reason: str = ""
    engine_score: int = 0


def play_game(
    white_engine: EngineProcess,
    black_engine: EngineProcess,
    config: SeriesConfig,
    game_number: int,
    log_file: str,
) -> GameRecord:
    board = chess.Board()
    pgn_game = chess.pgn.Game()
    pgn_game.headers["Event"] = "Engine Match"
    pgn_game.headers["Site"] = "Local"
    pgn_game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
    pgn_game.headers["Round"] = str(game_number)
    pgn_game.headers["White"] = white_engine.name
    pgn_game.headers["Black"] = black_engine.name
    pgn_game.headers["WhiteEngine"] = white_engine.name
    pgn_game.headers["BlackEngine"] = black_engine.name
    pgn_game.headers["TimeControl"] = f"{config.time_control.base}+{config.time_control.increment}"

    record = GameRecord(board=board, pgn=pgn_game)

    log(f"[Game {game_number}] {white_engine.name} (White) vs {black_engine.name} (Black) - started", log_file)

    white_engine.send_only("ucinewgame")
    black_engine.send_only("ucinewgame")

    white_time = config.time_control.base * 1000
    black_time = config.time_control.base * 1000
    increment = config.time_control.increment * 1000
    move_timeout = config.time_control.move_timeout

    book_exit_found = False
    book = None
    try:
        book = chess.polyglot.open_reader(_book_path())
    except (FileNotFoundError, OSError):
        pass

    engine = white_engine if board.turn == chess.WHITE else black_engine

    while not board.is_game_over(claim_draw=True):
        current_engine = white_engine if board.turn == chess.WHITE else black_engine
        current_time = white_time if board.turn == chess.WHITE else black_time
        opponent_time = black_time if board.turn == chess.WHITE else white_time
        turn_color = "White" if board.turn == chess.WHITE else "Black"

        if book and not book_exit_found:
            try:
                book_entry = book.find(board)
                if book_entry is None:
                    book_exit_found = True
                    record.book_exit_ply = board.ply()
            except IndexError:
                book_exit_found = True
                record.book_exit_ply = board.ply()

        start_time = time.time()
        try:
            response = current_engine.go_with_position(
                board_fen=board.fen(),
                wtime=white_time,
                btime=black_time,
                winc=increment,
                binc=increment,
                timeout=move_timeout,
            )
        except EngineTimeout:
            raise EngineError(f"engine '{current_engine.name}' hung — no response for {move_timeout}s")
        except EngineError as e:
            if not current_engine.is_alive():
                loser = current_engine.name
                log(f"[Game {game_number}] {loser} crashed — aborting series", log_file)
                raise EngineError(f"engine '{loser}' crashed during game {game_number} — {e}")
            raise

        elapsed_ms = int((time.time() - start_time) * 1000)
        if board.turn == chess.WHITE:
            white_time -= elapsed_ms
            white_time += increment
        else:
            black_time -= elapsed_ms
            black_time += increment

        move_uci = parse_bestmove(response)
        if not move_uci:
            log(f"[Game {game_number}] {turn_color} engine returned no move — aborting series", log_file)
            raise EngineError(f"engine '{current_engine.name}' returned no move in game {game_number}")

        try:
            move = board.parse_uci(move_uci)
        except ValueError:
            log(f"[Game {game_number}] {turn_color} engine played illegal move {move_uci} — aborting series", log_file)
            raise EngineError(f"engine '{current_engine.name}' played illegal move {move_uci} in game {game_number}")

        board.push(move)
        record.moves.append(move_uci)
        log(f"[Game {game_number}] {turn_color}: {move_uci} | fen: {board.fen()}", log_file)

        pgn_game = _update_pgn_game(pgn_game, board)
        record.pgn = pgn_game

    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        result_str = "*"
    elif outcome.winner == chess.WHITE:
        result_str = GameResult.WHITE_WIN
    elif outcome.winner == chess.BLACK:
        result_str = GameResult.BLACK_WIN
    else:
        result_str = GameResult.DRAW

    record.result = result_str
    pgn_game.headers["Result"] = result_str
    record.pgn = pgn_game
    log(f"[Game {game_number}] Result: {result_str}", log_file)

    if book:
        book.close()

    return record


def _update_pgn_game(old_game: chess.pgn.Game, board: chess.Board) -> chess.pgn.Game:
    new_game = chess.pgn.Game.from_board(board)
    for key, value in old_game.headers.items():
        new_game.headers[key] = value
    return new_game


def log(message: str, log_file: str) -> None:
    from pathlib import Path
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}\n"
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a") as f:
        f.write(line)
