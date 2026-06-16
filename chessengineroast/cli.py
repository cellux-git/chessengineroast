from __future__ import annotations

import argparse
import sys
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
    parser.add_argument("--config", type=str, metavar="CONFIG", help="TOML config file for the series")
    parser.add_argument("--play", action="store_true", help="Play a series")
    parser.add_argument("--analyze", action="store_true", help="Analyze a completed series")
    parser.add_argument("--engines", action="store_true", help="List discovered engines")
    parser.add_argument("--tag", type=str, help="Tag for series directory (series-{tag}/)")
    args = parser.parse_args()

    if args.engines:
        engines = discover_engines()
        if engines:
            for name in engines:
                print(name)
        else:
            print("No engines found. Place UCI engine binaries in engines/<name>/<name>.")
        return

    ran_something = False
    had_error = False

    if args.play or args.analyze:
        if not args.config:
            print("Error: --config is required when using --play or --analyze", file=sys.stderr)
            sys.exit(1)
        if not args.tag:
            print("Error: --tag is required when using --play or --analyze", file=sys.stderr)
            sys.exit(1)
        ran_something = True

    if args.play:
        if not _run_play(args.config, args.tag):
            had_error = True

    if args.analyze:
        if not _run_analyze(args.config, args.tag):
            had_error = True

    if not ran_something:
        parser.print_help()

    if had_error:
        sys.exit(1)


def _tag_paths(tag: str) -> dict[str, Path]:
    base = Path(f"series-{tag}")
    return {
        "dir": base,
        "pgn": base / "games.pgn",
        "log": base / "games.log",
        "analyzed_pgn": base / "games-analyzed.pgn",
        "blunders_csv": base / "blunders.csv",
    }


def _run_play(config_path: str, tag: str) -> bool:
    config = SeriesConfig.from_file(config_path)
    paths = _tag_paths(tag)

    if paths["dir"].exists():
        print(f"Error: series-{tag}/ already exists. Choose a different tag or delete the directory.", file=sys.stderr)
        return False

    paths["dir"].mkdir(parents=True)

    log_file = str(paths["log"])
    print(f"Log: {paths['log'].resolve()}")
    log(f"Series started: {config.white} vs {config.black}, {config.games} games", log_file)

    output_path = paths["pgn"]

    white_engine = EngineProcess(config.white, options=config.options_for(config.white))
    black_engine = EngineProcess(config.black, options=config.options_for(config.black))

    success = False

    try:
        white_engine.start()
        black_engine.start()
    except EngineError as e:
        print(f"Error starting engines: {e}", file=sys.stderr)
        log(f"Error starting engines: {e}", log_file)
        return False

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

        success = True
    except EngineError as e:
        print(f"Error during play: {e}", file=sys.stderr)
        log(f"Error during play: {e}", log_file)
    finally:
        white_engine.stop()
        black_engine.stop()

    if success:
        print(f"Series complete. {games_written}/{config.games} games played.")
        log(f"Series complete. {games_written}/{config.games} games played. PGN: {output_path}", log_file)
    return success


def _run_analyze(config_path: str, tag: str) -> bool:
    config = SeriesConfig.from_file(config_path)

    if not config.has_analysis():
        print("Error: analysis section missing engine and time_per_move in config", file=sys.stderr)
        return False

    paths = _tag_paths(tag)

    pgn_path = paths["pgn"]
    if not pgn_path.exists():
        print(f"Error: PGN file not found: {pgn_path}", file=sys.stderr)
        return False

    blunders_csv = paths["blunders_csv"]
    if blunders_csv.exists():
        print(f"Error: blunders CSV already exists: {blunders_csv}", file=sys.stderr)
        return False

    log_file = str(paths["log"])
    print(f"Log: {paths['log'].resolve()}")
    log(f"Analysis started for {pgn_path}", log_file)

    try:
        analyze_series(config, str(pgn_path), log_file, str(blunders_csv), str(paths["analyzed_pgn"]))
    except EngineError as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        log(f"Error during analysis: {e}", log_file)
        return False

    print("Analysis complete.")
    log("Analysis complete.", log_file)
    return True
