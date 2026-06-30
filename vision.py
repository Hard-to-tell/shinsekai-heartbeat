"""Optional integration with the Moondream Vision plugin."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from sdk.logging import get_logger

from .config import HeartbeatConfig, PLUGIN_ID


logger = get_logger(__name__, plugin_id=PLUGIN_ID)
MAX_SCREEN_SUMMARY_CHARS = 300

ToolEntry = tuple[Callable[..., Any], str | None, str | None, str | None, str | None]


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
