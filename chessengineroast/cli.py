from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from chessengineroast.config import SeriesConfig
from chessengineroast.engine import EngineError, EngineProcess, discover_engines
from chessengineroast.game import play_game, log
from chessengineroast.analysis import analyze_series


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="chessengineroast",
        description="UCI chess engine match runner and blunder analyzer",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--play", type=str, metavar="CONFIG", help="Play a series from a TOML config file")
    group.add_argument("--analyze", type=str, metavar="CONFIG", help="Analyze a completed series from a TOML config file")
    group.add_argument("--engines", action="store_true", help="List discovered engines")
    args = parser.parse_args()

    if args.engines:
        engines = discover_engines()
        if engines:
            for name in engines:
                print(name)
        else:
            print("No engines found. Place UCI engine binaries in engines/<name>/<name>.")
        return

    if args.play:
        _run_play(args.play)
        return

    if args.analyze:
        _run_analyze(args.analyze)
        return

    parser.print_help()


def _run_play(config_path: str) -> None:
    config = SeriesConfig.from_file(config_path)

    log_file = f"{config.output_raw}.log"
    log(f"Series started: {config.white} vs {config.black}, {config.games} games", log_file)

    output_path = _timestamp_path(config.output_raw)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    white_engine = EngineProcess(config.white, options=config.options_for(config.white))
    black_engine = EngineProcess(config.black, options=config.options_for(config.black))

    try:
        white_engine.start()
        black_engine.start()
    except EngineError as e:
        print(f"Error starting engines: {e}", file=sys.stderr)
        log(f"Error starting engines: {e}", log_file)
        sys.exit(1)

    games_written = 0
    try:
        with open(output_path, "w") as pgn_file:
            for game_num in range(1, config.games + 1):
                if game_num % 2 == 1:
                    w, b = white_engine, black_engine
                else:
                    w, b = black_engine, white_engine

                record = play_game(w, b, config, game_num, log_file)
                print(record.pgn, file=pgn_file, end="\n\n")
                games_written += 1

    except EngineError as e:
        print(f"Error during play: {e}", file=sys.stderr)
        log(f"Error during play: {e}", log_file)
        sys.exit(1)
    finally:
        white_engine.stop()
        black_engine.stop()

    print(f"Series complete. {games_written}/{config.games} games played. PGN: {output_path}")
    log(f"Series complete. {games_written}/{config.games} games played. PGN: {output_path}", log_file)


def _run_analyze(config_path: str) -> None:
    config = SeriesConfig.from_file(config_path)

    if not config.has_analysis():
        print("Error: analysis section missing engine and time_per_move in config", file=sys.stderr)
        sys.exit(1)

    output_path = _find_latest_output(config.output_raw)
    if output_path is None:
        print(f"Error: PGN file not found for pattern: {config.output_raw}", file=sys.stderr)
        sys.exit(1)

    log_file = f"{config.output_raw}.log"
    log(f"Analysis started for {output_path}", log_file)

    try:
        analyze_series(config, str(output_path), log_file)
    except EngineError as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        log(f"Error during analysis: {e}", log_file)
        sys.exit(1)

    print(f"Analysis complete.")
    log("Analysis complete.", log_file)


def _timestamp_path(raw_path: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = Path(raw_path)
    return path.parent / f"{path.stem}-{timestamp}{path.suffix}"


def _find_latest_output(raw_path: str) -> Path | None:
    path = Path(raw_path)
    pattern = f"{path.stem}-*.pgn"
    matches = sorted(path.parent.glob(pattern))
    if not matches:
        matches = sorted(path.parent.glob(f"{path.stem}*.pgn"))
    return matches[-1] if matches else None
