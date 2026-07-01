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
    interval_minutes_range: tuple[float, float] = (5.0, 15.0)
    mode_weights: dict[str, float] = field(
        default_factory=lambda: {"screen": 50.0, "monologue": 25.0, "question": 25.0}
    )
    reply_sentence_range: tuple[int, int] = (1, 4)
    monitor_index: int = -1
    screen_question: str = (
        "In one short sentence, describe what the user appears to be doing on screen."
    )
    monologue_instruction: str = (
        "Keep the current character persona and say something naturally."
    )
    question_instruction: str = (
        "Considering the current local time, naturally ask the user a question."
    )
    fixed_question_chance: float = 0.45
    fixed_questions: tuple[str, ...] = (
        "这么晚了，为什么还不睡？",
        "今天过得怎么样？",
        "忙了这么久，要不要休息一下？",
    )
    expression_chance: float = 0.35
    common_expressions: tuple[str, ...] = (
        "唔……",
        "嗯哼～",
        "（轻轻叹气）",
        "😊",
    )

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "HeartbeatConfig":
        defaults = cls()
        raw_interval_range = raw.get("interval_minutes_range")
        if raw_interval_range is None and "interval_minutes" in raw:
            legacy_interval = _finite_float(raw.get("interval_minutes"), 10.0)
            raw_interval_range = [legacy_interval, legacy_interval]
        interval_range = _float_range(
            raw_interval_range,
            defaults.interval_minutes_range,
            minimum=0.1,
            maximum=1440.0,
        )

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
            interval_minutes_range=interval_range,
            mode_weights=weights,
            reply_sentence_range=_int_range(
                raw.get("reply_sentence_range"),
                defaults.reply_sentence_range,
                minimum=1,
                maximum=8,
            ),
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
            fixed_question_chance=_probability(
                raw.get("fixed_question_chance"), defaults.fixed_question_chance
            ),
            fixed_questions=_text_list(
                raw.get("fixed_questions"), defaults.fixed_questions
            ),
            expression_chance=_probability(
                raw.get("expression_chance"), defaults.expression_chance
            ),
            common_expressions=_text_list(
                raw.get("common_expressions"), defaults.common_expressions
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def to_frontend_values(config: HeartbeatConfig) -> dict[str, Any]:
    interval_min, interval_max = config.interval_minutes_range
    reply_min, reply_max = config.reply_sentence_range
    return {
        "enabled": config.enabled,
        "interval_min_minutes": interval_min,
        "interval_max_minutes": interval_max,
        "screen_weight": config.mode_weights.get("screen", 0.0),
        "monologue_weight": config.mode_weights.get("monologue", 0.0),
        "question_weight": config.mode_weights.get("question", 0.0),
        "reply_min_sentences": reply_min,
        "reply_max_sentences": reply_max,
        "monitor_index": config.monitor_index,
        "screen_question": config.screen_question,
        "monologue_instruction": config.monologue_instruction,
        "question_instruction": config.question_instruction,
        "fixed_question_chance_percent": config.fixed_question_chance * 100.0,
        "fixed_questions_text": "\n".join(config.fixed_questions),
        "expression_chance_percent": config.expression_chance * 100.0,
        "common_expressions_text": "\n".join(config.common_expressions),
    }


def from_frontend_values(values: Mapping[str, Any]) -> HeartbeatConfig:
    if "interval_min_minutes" not in values and "fixed_questions_text" not in values:
        return HeartbeatConfig.from_mapping(values)

    defaults = HeartbeatConfig()
    raw = {
        "enabled": values.get("enabled", defaults.enabled),
        "interval_minutes_range": [
            _finite_float(
                values.get("interval_min_minutes"),
                defaults.interval_minutes_range[0],
            ),
            _finite_float(
                values.get("interval_max_minutes"),
                defaults.interval_minutes_range[1],
            ),
        ],
        "mode_weights": {
            "screen": _finite_float(
                values.get("screen_weight"), defaults.mode_weights["screen"]
            ),
            "monologue": _finite_float(
                values.get("monologue_weight"), defaults.mode_weights["monologue"]
            ),
            "question": _finite_float(
                values.get("question_weight"), defaults.mode_weights["question"]
            ),
        },
        "reply_sentence_range": [
            _integer(
                values.get("reply_min_sentences"), defaults.reply_sentence_range[0]
            ),
            _integer(
                values.get("reply_max_sentences"), defaults.reply_sentence_range[1]
            ),
        ],
        "monitor_index": values.get("monitor_index", defaults.monitor_index),
        "screen_question": values.get("screen_question", defaults.screen_question),
        "monologue_instruction": values.get(
            "monologue_instruction", defaults.monologue_instruction
        ),
        "question_instruction": values.get(
            "question_instruction", defaults.question_instruction
        ),
        "fixed_question_chance": _finite_float(
            values.get("fixed_question_chance_percent"),
            defaults.fixed_question_chance * 100.0,
        )
        / 100.0,
        "fixed_questions": _lines_from_text(
            values.get("fixed_questions_text"), defaults.fixed_questions
        ),
        "expression_chance": _finite_float(
            values.get("expression_chance_percent"),
            defaults.expression_chance * 100.0,
        )
        / 100.0,
        "common_expressions": _lines_from_text(
            values.get("common_expressions_text"), defaults.common_expressions
        ),
    }
    return HeartbeatConfig.from_mapping(raw)


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


def _float_range(
    value: object,
    default: tuple[float, float],
    *,
    minimum: float,
    maximum: float,
) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return default
    low = max(minimum, min(maximum, _finite_float(value[0], default[0])))
    high = max(minimum, min(maximum, _finite_float(value[1], default[1])))
    return (min(low, high), max(low, high))


def _int_range(
    value: object,
    default: tuple[int, int],
    *,
    minimum: int,
    maximum: int,
) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return default
    low = max(minimum, min(maximum, _integer(value[0], default[0])))
    high = max(minimum, min(maximum, _integer(value[1], default[1])))
    return (min(low, high), max(low, high))


def _probability(value: object, default: float) -> float:
    return max(0.0, min(1.0, _finite_float(value, default)))


def _text_list(value: object, default: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(value, list):
        return default
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _text_or_default(value: object, default: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return default
    return value.strip()


def _lines_from_text(value: object, default: tuple[str, ...]) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return list(default)


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
            self.save(self._current)
        return self.get(force=True)

    def save(self, config: HeartbeatConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(config.to_dict(), ensure_ascii=False, indent=2) + "\n"
        self.path.write_text(text, encoding="utf-8")
        self._current = config
        self._last_text = text

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
