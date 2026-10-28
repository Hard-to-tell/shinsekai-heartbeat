"""Plugin lifecycle and host input bindings."""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sdk.logging import get_logger

from .config import ConfigStore, PLUGIN_ID
from . import status
from .scheduler import HEARTBEAT_MARKER, HeartbeatScheduler


logger = get_logger(__name__, plugin_id=PLUGIN_ID)
_lock = threading.Lock()
_config_store: ConfigStore | None = None
_scheduler: HeartbeatScheduler | None = None
_reply_tracking_bound = False
_ui_disconnects: list[Callable[[], None]] = []

_STUDY_START_PHRASES = (
    "我要学习请监督我",
    "我要学习监督我",
    "开始学习请监督我",
    "请监督我学习",
    "监督我学习",
    "开启学习模式",
    "打开学习模式",
    "开始专注",
    "继续专注",
    "开启专注模式",
    "陪我学习",
    "继续学习",
    "继续监督",
    "再来一轮学习",
)
_STUDY_STOP_PHRASES = (
    "停止监督",
    "结束监督",
    "不用监督",
    "不要监督",
    "别监督",
    "关闭学习模式",
    "退出学习模式",
    "暂停学习模式",
    "结束学习",
    "停止学习",
    "退出专注",
    "结束专注",
    "先休息一下",
    "我要休息",
)
_STUDY_CONFIRM_PHRASES = (
    "没分心",
    "没有分心",
    "你看错了",
    "我在学习",
    "这是学习内容",
    "这也是学习",
)


def configure(plugin_root: Path) -> ConfigStore:
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
    return store


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

    scheduler = HeartbeatScheduler(
        store, emit_user_text,
        status_callback=lambda message: status.publish(store.path.parent, message),
    )
    with _lock:
        _scheduler = scheduler
        reply_tracking_bound = _reply_tracking_bound
    scheduler.enable_reply_tracking(reply_tracking_bound)
    scheduler.start()


def process_user_input(text: str) -> str:
    is_heartbeat = text.startswith(HEARTBEAT_MARKER)
    original_text = text
    with _lock:
        scheduler = _scheduler
    if not is_heartbeat:
        if scheduler is not None:
            command = detect_study_command(text)
            if command == "start":
                focus_minutes = scheduler.start_study_session()
                if focus_minutes is None:
                    text = f"{text}\n[学习监督功能当前已关闭，本轮未启动。]"
                else:
                    text = (
                        f"{text}\n[学习监督已开启：本轮实际专注时长为 {focus_minutes:g} 分钟。"
                        "请按这个时长简短确认，不要自行改用其他时长。]"
                    )
            elif command == "stop":
                scheduler.stop_study_session()
            elif is_study_confirmation(text):
                scheduler.trust_study_once()
            scheduler.note_user_activity(original_text)
    return text


def detect_study_command(text: str) -> str | None:
    """Recognize explicit Chinese natural-language study mode commands."""
    compact = re.sub(r"[\W_]+", "", str(text).lower(), flags=re.UNICODE)
    if re.search(r"(?:不要|不用|别|不想|无需)(?:开启|打开|启动|开始)(?:学习|专注)(?:模式)?", compact):
        return "stop"
    if any(phrase in compact for phrase in _STUDY_STOP_PHRASES):
        return "stop"
    if any(phrase in compact for phrase in _STUDY_START_PHRASES):
        return "start"
    return None


def is_study_confirmation(text: str) -> bool:
    """Recognize a simple correction when screen supervision guessed wrong."""
    compact = re.sub(r"[\W_]+", "", str(text).lower(), flags=re.UNICODE)
    return any(phrase in compact for phrase in _STUDY_CONFIRM_PHRASES)


def bind_chat_ui(context: Any) -> None:
    global _reply_tracking_bound, _ui_disconnects
    with _lock:
        previous_disconnects = _ui_disconnects
        _ui_disconnects = []
    for disconnect in previous_disconnects:
        disconnect()

    disconnects = [
        context.on_llm_reply_finished(_on_reply_finished),
    ]
    with _lock:
        _ui_disconnects = disconnects
        _reply_tracking_bound = True
        scheduler = _scheduler
    if scheduler is not None:
        scheduler.enable_reply_tracking(True)


def _on_reply_finished() -> None:
    with _lock:
        scheduler = _scheduler
    if scheduler is not None:
        scheduler.note_reply_finished()


def shutdown() -> None:
    global _config_store, _scheduler, _reply_tracking_bound, _ui_disconnects
    with _lock:
        scheduler = _scheduler
        _config_store = None
        _scheduler = None
        disconnects = _ui_disconnects
        _ui_disconnects = []
        _reply_tracking_bound = False
    for disconnect in disconnects:
        disconnect()
    if scheduler is not None:
        scheduler.enable_reply_tracking(False)
        scheduler.stop()
