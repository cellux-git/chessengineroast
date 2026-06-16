from __future__ import annotations

import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional


class EngineError(Exception):
    pass


class EngineTimeout(EngineError):
    pass


def _engines_dir() -> Path:
    return Path(os.environ.get("CHESSENGINE_ROAST_ENGINES_DIR", "engines"))


def _book_path() -> Path:
    return Path(os.environ.get("CHESSENGINE_ROAST_BOOK_PATH", "books/opening.bin"))


def discover_engines() -> list[str]:
    if not _engines_dir().is_dir():
        return []
    engines: list[str] = []
    for entry in sorted(_engines_dir().iterdir()):
        if not entry.is_dir():
            continue
        binary = entry / entry.name
        if binary.is_file() and os.access(binary, os.X_OK):
            engines.append(entry.name)
    return engines


def resolve_engine_path(name: str) -> Path:
    binary = _engines_dir() / name / name
    if not binary.is_file():
        raise EngineError(
            f"engine '{name}' not found — expected binary at {binary}"
        )
    if not os.access(binary, os.X_OK):
        raise EngineError(
            f"engine binary {binary} is not executable"
        )
    return binary


class EngineProcess:
    def __init__(self, name: str, options: dict[str, str] | None = None):
        self.name = name
        self.path = resolve_engine_path(name)
        self.options = options or {}
        self._proc: subprocess.Popen[str] | None = None
        self._output_queue: queue.Queue[str] = queue.Queue()
        self._reader_thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        self._proc = subprocess.Popen(
            [str(self.path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )
        self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self._reader_thread.start()
        self._running = True

        self._send("uci")
        self._wait_for("uciok")

        for key, value in self.options.items():
            self._send(f"setoption name {key} value {value}")

        self._send("isready")
        self._wait_for("readyok")

        self._send("ucinewgame")

    def stop(self) -> None:
        self._running = False
        if self._proc and self._proc.poll() is None:
            try:
                self._send("quit")
                self._proc.wait(timeout=3)
            except (subprocess.TimeoutExpired, OSError, BrokenPipeError):
                self._proc.kill()
                self._proc.wait(timeout=3)

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def send_command(self, command: str) -> str:
        self._send(command)
        return self._wait_for("bestmove")

    def send_only(self, command: str) -> None:
        self._send(command)

    def send_position(self, fen: str, moves: str = "") -> None:
        if moves:
            self._send(f"position fen {fen} moves {moves}")
        else:
            self._send(f"position fen {fen}")

    def go_with_position(self, board_fen: str, wtime: int, btime: int, winc: int, binc: int, timeout: int = 60) -> str:
        self._send(f"position fen {board_fen}")
        return self.send_go(wtime=wtime, btime=btime, winc=winc, binc=binc, timeout=timeout)

    def send_go(self, wtime: int, btime: int, winc: int, binc: int = 0, timeout: int = 60) -> str:
        cmd = f"go wtime {wtime} btime {btime} winc {winc} binc {binc}"
        self._send(cmd)
        return self._wait_for("bestmove", timeout=timeout)

    def send_go_movetime(self, movetime_ms: int, timeout: int = 30) -> str:
        cmd = f"go movetime {movetime_ms}"
        self._send(cmd)
        return self._wait_for("bestmove", timeout=timeout)

    def send_go_movetime_score(self, movetime_ms: int, timeout: int = 30) -> tuple[str, Optional[int]]:
        cmd = f"go movetime {movetime_ms}"
        self._send(cmd)
        return self._wait_for_with_score("bestmove", timeout=timeout)

    def send_stop(self) -> None:
        self._send("stop")

    def _send(self, command: str) -> None:
        if self._proc and self._proc.stdin:
            try:
                self._proc.stdin.write(command + "\n")
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                raise EngineError(f"failed to send command to engine '{self.name}': {e}")

    def _read_output(self) -> None:
        if self._proc and self._proc.stdout:
            try:
                for line in self._proc.stdout:
                    if not self._running:
                        break
                    line = line.strip()
                    if line:
                        self._output_queue.put(line)
            except (ValueError, OSError):
                pass

    def _read_line(self, timeout: float | None = None) -> Optional[str]:
        try:
            return self._output_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _wait_for(self, token: str, timeout: int = 30) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            line = self._read_line(timeout=min(remaining, 1.0))
            if line is None:
                if not self.is_alive():
                    raise EngineError(f"engine '{self.name}' process exited unexpectedly")
                continue
            if token in line:
                return line
        raise EngineTimeout(f"engine '{self.name}' timed out waiting for '{token}'")

    def _wait_for_with_score(self, token: str, timeout: int = 30) -> tuple[str, Optional[int]]:
        """Wait for token, also capturing the last info score seen."""
        deadline = time.monotonic() + timeout
        last_score: Optional[int] = None
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            line = self._read_line(timeout=min(remaining, 1.0))
            if line is None:
                if not self.is_alive():
                    raise EngineError(f"engine '{self.name}' process exited unexpectedly")
                continue
            score = parse_score(line)
            if score is not None:
                last_score = score
            if token in line:
                return line, last_score
        raise EngineTimeout(f"engine '{self.name}' timed out waiting for '{token}'")

    def _wait_for_ok(self, timeout: int = 30) -> None:
        self._wait_for("ok", timeout=timeout)


def parse_bestmove(line: str) -> str:
    parts = line.strip().split()
    if "bestmove" in parts:
        idx = parts.index("bestmove")
        if idx + 1 < len(parts):
            move = parts[idx + 1]
            if move != "(none)":
                return move
    return ""


def parse_score(line: str) -> Optional[int]:
    parts = line.strip().split()
    try:
        idx = parts.index("score")
        if idx + 2 < len(parts):
            score_type = parts[idx + 1]
            value = int(parts[idx + 2])
            if score_type == "cp":
                return value
            if score_type == "mate":
                return 30000 if value > 0 else -30000
    except (ValueError, IndexError):
        pass
    return None
