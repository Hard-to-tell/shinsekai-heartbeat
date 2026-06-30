"""JSON configuration for Heartbeat Companion."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from sdk.logging import get_logger


PLUGIN_ID = "io.github.hard_to_tell.heartbeat_companion"
logger = get_logger(__name__, plugin_id=PLUGIN_ID)


@dataclass(frozen=True)
class HeartbeatConfig:
    enabled: bool = True
    interval_minutes: float = 10.0
    mode_weights: dict[str, float] = field(
        default_factory=lambda: {"screen": 50.0, "monologue": 25.0, "question": 25.0}
    )
    monitor_index: int = -1
    screen_question: str = (
        "In one short sentence, describe what the user appears to be doing on screen."
    )
    monologue_instruction: str = (
        "Keep the current character persona and naturally say one or two short sentences."
    )
    question_instruction: str = (
        "Considering the current local time, naturally ask the user one short question."
    )

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "HeartbeatConfig":
        defaults = cls()
        interval = _finite_float(raw.get("interval_minutes"), defaults.interval_minutes)
        interval = max(0.1, min(1440.0, interval))

        raw_weights = raw.get("mode_weights")
        if not isinstance(raw_weights, Mapping):
            raw_weights = {}
        weights = {
            mode: max(0.0, _finite_float(raw_weights.get(mode), default))
            for mode, default in defaults.mode_weights.items()
        }
        if not any(weights.values()):
            weights["monologue"] = 1.0

        monitor_index = _integer(raw.get("monitor_index"), defaults.monitor_index)
        monitor_index = max(-1, min(32, monitor_index))

        return cls(
            enabled=(
                raw.get("enabled")
                if isinstance(raw.get("enabled"), bool)
                else defaults.enabled
            ),
            interval_minutes=interval,
            mode_weights=weights,
            monitor_index=monitor_index,
            screen_question=_text_or_default(
                raw.get("screen_question"), defaults.screen_question
            ),
            monologue_instruction=_text_or_default(
                raw.get("monologue_instruction"), defaults.monologue_instruction
            ),
            question_instruction=_text_or_default(
                raw.get("question_instruction"), defaults.question_instruction
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finite_float(value: object, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if math.isfinite(number) else float(default)


def _integer(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _text_or_default(value: object, default: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return default
    return value.strip()


class ConfigStore:
    """Create and hot-reload the plugin's JSON configuration."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._current = HeartbeatConfig()
        self._last_text: str | None = None

    @property
    def current(self) -> HeartbeatConfig:
        return self._current

    def initialize(self) -> HeartbeatConfig:
        if not self.path.is_file():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self._current.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return self.get(force=True)

    def get(self, *, force: bool = False) -> HeartbeatConfig:
        try:
            text = self.path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return self._current

        if not force and self._last_text == text:
            return self._current
        self._last_text = text

        try:
            raw = json.loads(text)
            if not isinstance(raw, dict):
                raise ValueError("configuration root must be a JSON object")
            self._current = HeartbeatConfig.from_mapping(raw)
        except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError) as exc:
            logger.warning(
                "Keeping the last valid heartbeat configuration: %s",
                exc,
                extra={"event": "heartbeat.config.invalid"},
            )
        return self._current
