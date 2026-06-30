"""Plugin lifecycle and host input bindings."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sdk.logging import get_logger

from .config import ConfigStore, PLUGIN_ID
from .scheduler import HEARTBEAT_MARKER, HeartbeatScheduler


logger = get_logger(__name__, plugin_id=PLUGIN_ID)
_lock = threading.Lock()
_config_store: ConfigStore | None = None
_scheduler: HeartbeatScheduler | None = None
_reply_tracking_bound = False
_ui_disconnects: list[Callable[[], None]] = []
_reply_pending = False
_character_dialog_seen = False


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
        reply_tracking_bound = _reply_tracking_bound
    scheduler.enable_reply_tracking(reply_tracking_bound)
    scheduler.start()


def process_user_input(text: str) -> str:
    global _reply_pending, _character_dialog_seen
    is_heartbeat = text.startswith(HEARTBEAT_MARKER)
    with _lock:
        _reply_pending = True
        _character_dialog_seen = False
        scheduler = _scheduler
    if not is_heartbeat:
        if scheduler is not None:
            scheduler.note_user_activity()
    return text


def bind_chat_ui(context: Any) -> None:
    global _reply_tracking_bound, _ui_disconnects
    with _lock:
        previous_disconnects = _ui_disconnects
        _ui_disconnects = []
    for disconnect in previous_disconnects:
        disconnect()

    disconnects = [
        context.on_llm_reply_finished(_on_reply_finished),
        context.on_display_words_changed(_on_display_words_changed),
        context.on_dialog_typing_finished(_on_dialog_typing_finished),
        context.on_skip_speech_signal(_on_reply_finished),
    ]
    with _lock:
        _ui_disconnects = disconnects
        _reply_tracking_bound = True
        scheduler = _scheduler
    if scheduler is not None:
        scheduler.enable_reply_tracking(True)


def _on_reply_finished() -> None:
    global _reply_pending, _character_dialog_seen
    with _lock:
        _reply_pending = False
        _character_dialog_seen = False
        scheduler = _scheduler
    if scheduler is not None:
        scheduler.note_reply_finished()


def _on_display_words_changed(text: str) -> None:
    global _character_dialog_seen
    normalized = str(text or "").lstrip()
    with _lock:
        if _reply_pending and normalized and not normalized.startswith("<b>你</b>"):
            _character_dialog_seen = True


def _on_dialog_typing_finished() -> None:
    with _lock:
        character_dialog_seen = _character_dialog_seen
    if character_dialog_seen:
        _on_reply_finished()


def shutdown() -> None:
    global _scheduler, _reply_tracking_bound, _ui_disconnects
    global _reply_pending, _character_dialog_seen
    with _lock:
        scheduler = _scheduler
        _scheduler = None
        disconnects = _ui_disconnects
        _ui_disconnects = []
        _reply_tracking_bound = False
        _reply_pending = False
        _character_dialog_seen = False
    for disconnect in disconnects:
        disconnect()
    if scheduler is not None:
        scheduler.enable_reply_tracking(False)
        scheduler.stop()
