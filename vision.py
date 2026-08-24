"""Optional integration with the Moondream Vision plugin."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace
from typing import Any

from sdk.logging import get_logger

from .config import HeartbeatConfig, PLUGIN_ID


logger = get_logger(__name__, plugin_id=PLUGIN_ID)
MAX_SCREEN_SUMMARY_CHARS = 300
STUDY = "study"
DISTRACTED = "distracted"
UNCERTAIN = "uncertain"
CLEAR_DISTRACTION_CUES = (
    "active game",
    "playing a game",
    "video game",
    "unrelated entertainment",
    "social feed",
    "short videos",
    "comedy clip",
    "游戏",
    "娱乐视频",
    "刷视频",
    "刷帖",
)

ToolEntry = tuple[Callable[..., Any], str | None, str | None, str | None, str | None]
StudyScreenResult = tuple[str, str]


def query_screen(
    config: HeartbeatConfig,
    *,
    entries: Iterable[ToolEntry] | None = None,
) -> str | None:
    """Call Moondream's registered screen tool, returning a short summary."""
    if entries is None:
        try:
            from sdk.tool_registry import registered_tool_entries

            entries = registered_tool_entries()
        except Exception as exc:
            logger.info(
                "Moondream tool registry is unavailable: %s",
                exc,
                extra={"event": "heartbeat.vision.unavailable"},
            )
            return None

    tool_fn: Callable[..., Any] | None = None
    for fn, name, _description, _group, _risk in entries:
        if (name or getattr(fn, "__name__", "")) == "moondream_query_screen":
            tool_fn = fn
            break

    if tool_fn is None:
        logger.info(
            "Moondream screen tool is not installed",
            extra={"event": "heartbeat.vision.missing"},
        )
        return None

    try:
        result = tool_fn(
            question=config.screen_question,
            monitor_index=config.monitor_index,
        )
    except Exception as exc:
        event = (
            "heartbeat.vision.loading"
            if exc.__class__.__name__ == "ToolNotReady"
            else "heartbeat.vision.failed"
        )
        logger.info("Moondream screen query did not complete: %s", exc, extra={"event": event})
        return None

    if not isinstance(result, dict):
        return None
    answer = result.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        error = result.get("error")
        if error:
            logger.info(
                "Moondream screen query returned an error: %s",
                error,
                extra={"event": "heartbeat.vision.failed"},
            )
        return None

    summary = " ".join(answer.split())
    return summary[:MAX_SCREEN_SUMMARY_CHARS]


def query_study_screen(
    config: HeartbeatConfig,
    *,
    entries: Iterable[ToolEntry] | None = None,
) -> StudyScreenResult | None:
    """Classify the visible activity for study mode using the same local screen tool."""
    question = config.study_screen_question
    if config.study_safe_words:
        safe_words = ", ".join(config.study_safe_words)
        question = (
            f"{question} Study-safe hints: {safe_words}. If the visible activity "
            "matches one of these hints and is not clearly recreational, use STUDY."
        )
    summary = query_screen(
        replace(config, screen_question=question),
        entries=entries,
    )
    if summary is None:
        return None
    return classify_study_screen(summary, config.study_safe_words), summary


def classify_study_screen(
    summary: str, safe_words: Iterable[str] = ()
) -> str:
    """Remind only for an explicit distraction; ambiguous results stay silent."""
    folded_summary = summary.casefold()
    has_safe_word = any(
        word.strip() and word.strip().casefold() in folded_summary
        for word in safe_words
    )
    has_clear_distraction = any(
        cue.casefold() in folded_summary for cue in CLEAR_DISTRACTION_CUES
    )
    if has_safe_word and not has_clear_distraction:
        return STUDY
    prefix = summary.strip().lstrip("`*#[]()：: -").upper()
    if prefix.startswith("STUDY") or prefix.startswith("学习") or prefix.startswith("专注"):
        return STUDY
    if prefix.startswith("DISTRACTED") or prefix.startswith("分心"):
        return DISTRACTED
    return UNCERTAIN
