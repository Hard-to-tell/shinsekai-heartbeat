"""Plugin lifecycle and host input bindings."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from sdk.logging import get_logger

from .config import ConfigStore, PLUGIN_ID
from .scheduler import HEARTBEAT_MARKER, HeartbeatScheduler


logger = get_logger(__name__, plugin_id=PLUGIN_ID)
_lock = threading.Lock()
_config_store: ConfigStore | None = None
_scheduler: HeartbeatScheduler | None = None


def configure(plugin_root: Path) -> None:
    global _config_store
    store = ConfigStore(Path(plugin_root) / "config.json")
    config = store.initialize()
    with _lock:
        _config_store = store
    logger.info(
        "Heartbeat Companion initialized",
        extra={
            "event": "heartbeat.initialized",
            "enabled": config.enabled,
            "interval_minutes_range": config.interval_minutes_range,
        },
    )


def bind_emit(emit_user_text: Callable[[str], None]) -> None:
    global _scheduler
    with _lock:
        store = _config_store
        previous = _scheduler
        _scheduler = None
    if previous is not None:
        previous.stop()
    if store is None:
        raise RuntimeError("Heartbeat Companion has not been configured")

    scheduler = HeartbeatScheduler(store, emit_user_text)
    with _lock:
        _scheduler = scheduler
    scheduler.start()


def process_user_input(text: str) -> str:
    if not text.startswith(HEARTBEAT_MARKER):
        with _lock:
            scheduler = _scheduler
        if scheduler is not None:
            scheduler.note_user_activity()
    return text


def shutdown() -> None:
    global _scheduler
    with _lock:
        scheduler = _scheduler
        _scheduler = None
    if scheduler is not None:
        scheduler.stop()
