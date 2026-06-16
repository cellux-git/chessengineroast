from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    pass


@dataclass
class TimeControl:
    base: int
    increment: int

    @classmethod
    def from_toml(cls, data: dict[str, Any]) -> TimeControl:
        raw_base = data.get("base", "")
        raw_inc = data.get("increment", "")
        if not raw_base or not raw_inc:
            raise ConfigError(
                "time.base and time.increment are required (e.g. base = '3m', increment = '2s')"
            )
        return cls(base=cls._parse_seconds(raw_base), increment=cls._parse_seconds(raw_inc))

    @staticmethod
    def _parse_seconds(raw: str) -> int:
        raw = raw.strip().lower()
        total = 0
        for chunk in raw.split():
            if chunk.endswith("h"):
                total += int(chunk[:-1]) * 3600
            elif chunk.endswith("m"):
                total += int(chunk[:-1]) * 60
            elif chunk.endswith("s"):
                total += int(chunk[:-1])
            else:
                try:
                    total += int(chunk)
                except ValueError:
                    raise ConfigError(
                        f"invalid time value '{chunk}' — use suffixes h, m, s (e.g. '3m', '2s')"
                    )
        if total <= 0:
            raise ConfigError(f"time value must be positive, got {total}s from '{raw}'")
        return total

    @property
    def move_timeout(self) -> int:
        return self.base // 3


@dataclass
class SeriesConfig:
    white: str
    black: str
    time_control: TimeControl
    games: int
    output_raw: str
    output_analyzed: str | None
    output_blunders: str | None
    analysis_engine: str | None
    analysis_time_per_move: str | None
    track_blunders_for: str | None
    equal_range: float
    blunder_delta: float
    engine_options: dict[str, dict[str, str]] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str | Path) -> SeriesConfig:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SeriesConfig:
        engines = data.get("engines", {})
        white = engines.get("white", "").strip()
        black = engines.get("black", "").strip()
        if not white or not black:
            raise ConfigError("engines.white and engines.black are required")

        time = TimeControl.from_toml(data.get("time", {}))

        matches = data.get("matches", {})
        games = matches.get("games", 1)
        if games < 1:
            raise ConfigError("matches.games must be at least 1")

        output = data.get("output", {})
        output_raw = output.get("raw", f"{white}-vs-{black}.pgn")
        output_analyzed = output.get("analyzed")
        output_blunders = output.get("blunders")

        analysis = data.get("analysis", {})
        analysis_engine = analysis.get("engine")
        analysis_time_per_move = analysis.get("time_per_move")
        track = analysis.get("track_blunders_for")

        blunder = data.get("blunder_detection", {})
        equal_range = float(blunder.get("equal_range", 1.5))
        blunder_delta = float(blunder.get("blunder_delta", 2.0))

        engine_options: dict[str, dict[str, str]] = {}
        for key, value in data.get("engine_options", {}).items():
            if isinstance(value, dict):
                engine_options[key] = {str(k): str(v) for k, v in value.items()}

        return cls(
            white=white,
            black=black,
            time_control=time,
            games=games,
            output_raw=output_raw,
            output_analyzed=output_analyzed,
            output_blunders=output_blunders,
            analysis_engine=analysis_engine,
            analysis_time_per_move=analysis_time_per_move,
            track_blunders_for=track,
            equal_range=equal_range,
            blunder_delta=blunder_delta,
            engine_options=engine_options,
        )

    def options_for(self, engine_name: str) -> dict[str, str]:
        return self.engine_options.get(engine_name, {})

    def has_analysis(self) -> bool:
        return self.analysis_engine is not None and self.analysis_time_per_move is not None
