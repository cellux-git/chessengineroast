#!/usr/bin/env python3
"""Mock UCI engine for testing chessengineroast."""

import os
import sys


MOCK_NAME = os.environ.get("MOCK_ENGINE_NAME", "MockEngine")
MOCK_AUTHOR = os.environ.get("MOCK_ENGINE_AUTHOR", "Test")
BEHAVIOR = os.environ.get("MOCK_BEHAVIOR", "normal")
MOCK_SCORE = os.environ.get("MOCK_SCORE", "")
MOCK_SCORES = os.environ.get("MOCK_SCORES", "")

WHITE_MOVES = [
    "e2e4", "g1f3", "f1c4", "e1g1", "d2d4", "b1c3", "c1g5", "d1d2",
    "a1e1", "f1e1", "h2h3", "a2a3", "b2b3", "c2c3", "f2f3", "g2g3",
    "d4d5", "c3b5", "c4b3", "f3g5", "f3h4", "f3d2", "g5f6", "g5e3",
    "d2d3", "f2f4", "c4d3", "c4e2", "b3c4", "c4b5",
]

BLACK_MOVES = [
    "e7e5", "b8c6", "g8f6", "f8c5", "d7d5", "c7c5", "d7d6", "c8g4",
    "f8e7", "e8g8", "h7h6", "a7a6", "b7b6", "c7c6", "f7f6", "g7g6",
    "d5e4", "c6b4", "f6e4", "c5b4", "a7a5", "b7b5", "c8e6", "c8f5",
    "d8d7", "f6g4", "f8d6", "f8b4", "e5d4", "c5d4",
]


def respond(line: str) -> None:
    print(line, flush=True)


def _pick_score(score_index: int) -> str:
    if MOCK_SCORES:
        parts = [s.strip() for s in MOCK_SCORES.split(",")]
        return parts[score_index % len(parts)]
    return MOCK_SCORE


def main() -> None:
    move_index = 0
    score_index = 0

    while True:
        try:
            line = sys.stdin.readline()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            break
        line = line.strip()

        if line == "uci":
            respond(f"id name {MOCK_NAME}")
            respond(f"id author {MOCK_AUTHOR}")
            respond("option name Hash type spin default 128 min 1 max 65536")
            respond("option name Threads type spin default 1 min 1 max 256")
            respond("option name OwnBook type check default false")
            respond("option name BookFile type string default <empty>")
            respond("uciok")

        elif line == "isready":
            respond("readyok")

        elif line == "ucinewgame":
            move_index = 0
            score_index = 0

        elif line.startswith("setoption"):
            pass

        elif BEHAVIOR == "crash" and "go" in line:
            sys.stderr.flush()
            sys.stdout.flush()
            os._exit(1)

        elif BEHAVIOR == "hang" and "go" in line:
            import time
            time.sleep(600)

        elif line.startswith("position"):
            pass

        elif line.startswith("go"):
            if BEHAVIOR == "illegal":
                respond("bestmove e2e9")
            elif BEHAVIOR == "nomove":
                respond("bestmove (none)")
            elif BEHAVIOR == "score_cp50":
                respond("info score cp 50")
                respond("bestmove e7e5")
            elif BEHAVIOR == "score_blunder":
                respond("info score cp -300")
                respond("bestmove d7d5")
            elif "mockengine2" in sys.argv[0]:
                score_val = _pick_score(score_index)
                if score_val:
                    respond(f"info score cp {score_val}")
                    score_index += 1
                move = BLACK_MOVES[move_index % len(BLACK_MOVES)]
                respond(f"bestmove {move}")
                move_index += 1
            else:
                score_val = _pick_score(score_index)
                if score_val:
                    respond(f"info score cp {score_val}")
                    score_index += 1
                move = WHITE_MOVES[move_index % len(WHITE_MOVES)]
                respond(f"bestmove {move}")
                move_index += 1

        elif line.startswith("stop"):
            respond("bestmove e2e4")

        elif line == "quit":
            break


if __name__ == "__main__":
    main()
