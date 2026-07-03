"""Idle-based heartbeat scheduler."""

from __future__ import annotations

import random
import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import datetime

from sdk.logging import get_logger

from .config import ConfigStore, HeartbeatConfig, PLUGIN_ID
from .vision import query_screen


logger = get_logger(__name__, plugin_id=PLUGIN_ID)
HEARTBEAT_MARKER = "[心跳·"
BUSY_TIMEOUT_SECONDS = 30.0 * 60.0
SHORT_IDLE_SECONDS = 5.0 * 60.0
LONG_IDLE_SECONDS = 10.0 * 60.0
RECENT_USER_INPUT_LIMIT = 3
RECENT_USER_INPUT_CHARS = 120


class HeartbeatScheduler:
    def __init__(
        self,
        config_store: ConfigStore,
        emit_user_text: Callable[[str], None],
        *,
        screen_reader: Callable[[HeartbeatConfig], str | None] = query_screen,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = datetime.now,
        rng: random.Random | None = None,
        poll_seconds: float = 1.0,
    ) -> None:
        self._config_store = config_store
        self._emit_user_text = emit_user_text
        self._screen_reader = screen_reader
        self._clock = clock
        self._wall_clock = wall_clock
        self._rng = rng or random.Random()
        self._poll_seconds = max(0.05, float(poll_seconds))

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._active = False
        self._last_activity_at = self._clock()
        self._activity_generation = 0
        self._was_enabled: bool | None = None
        self._needs_reschedule = True
        self._scheduled_range: tuple[float, float] | None = None
        self._next_due_at: float | None = None
        self._reply_tracking = False
        self._busy = False
        self._busy_since: float | None = None
        self._last_mode: str | None = None
        self._last_fixed_question: str | None = None
        self._last_expression: str | None = None
        self._recent_user_inputs: deque[str] = deque(maxlen=RECENT_USER_INPUT_LIMIT)

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._active = True
            self._last_activity_at = self._clock()
            self._needs_reschedule = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="heartbeat_companion_loop",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        with self._lock:
            self._active = False
            thread = self._thread
            self._thread = None
            self._stop_event.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)

    def note_user_activity(self, text: str | None = None) -> None:
        with self._lock:
            now = self._clock()
            self._last_activity_at = now
            self._activity_generation += 1
            self._needs_reschedule = True
            cleaned = _clean_recent_user_input(text)
            if cleaned:
                self._recent_user_inputs.append(cleaned)
            if self._reply_tracking:
                self._busy = True
                self._busy_since = now

    def enable_reply_tracking(self, enabled: bool = True) -> None:
        with self._lock:
            self._reply_tracking = bool(enabled)
            if not self._reply_tracking:
                self._busy = False
                self._busy_since = None

    def note_reply_finished(self) -> None:
        with self._lock:
            if not self._reply_tracking:
                return
            self._busy = False
            self._busy_since = None
            self._last_activity_at = self._clock()
            self._activity_generation += 1
            self._needs_reschedule = True

    def tick(self) -> bool:
        """Run one scheduler check; returns True when a heartbeat was emitted."""
        config = self._config_store.get()
        now = self._clock()

        if not config.enabled:
            self._was_enabled = False
            return False

        with self._lock:
            if not self._active:
                return False
            busy = self._busy
            busy_since = self._busy_since
        if busy:
            if busy_since is None or now - busy_since < BUSY_TIMEOUT_SECONDS:
                return False
            with self._lock:
                self._busy = False
                self._busy_since = None
                self._last_activity_at = now
                self._activity_generation += 1
                self._needs_reschedule = True
            logger.warning(
                "Heartbeat busy state timed out and was released",
                extra={"event": "heartbeat.busy.timeout"},
            )
            return False
        if self._was_enabled is False:
            with self._lock:
                self._last_activity_at = now
                self._needs_reschedule = True
            self._was_enabled = True
            return False
        self._was_enabled = True

        self._ensure_schedule(config)

        with self._lock:
            if not self._active:
                return False
            activity_at = self._last_activity_at
            generation = self._activity_generation
            next_due_at = self._next_due_at
            recent_user_inputs = tuple(self._recent_user_inputs)

        idle_seconds = max(0.0, now - activity_at)
        if next_due_at is None or now < next_due_at:
            return False

        idle_policy = _idle_policy(idle_seconds)
        mode = self._choose_mode(config, idle_policy=idle_policy)
        screen_summary: str | None = None
        if mode == "screen":
            screen_summary = self._screen_reader(config)
            if screen_summary is None:
                mode = self._choose_mode(
                    config,
                    allow_screen=False,
                    idle_policy=idle_policy,
                )

        with self._lock:
            if not self._active or generation != self._activity_generation:
                return False
            if activity_at != self._last_activity_at:
                return False

        message, fixed_question, expression = self._build_message(
            config,
            mode=mode,
            screen_summary=screen_summary,
            idle_seconds=idle_seconds,
            idle_policy=idle_policy,
            recent_user_inputs=recent_user_inputs,
            sentence_count=self._rng.randint(*config.reply_sentence_range),
        )
        with self._lock:
            if self._reply_tracking:
                self._busy = True
                self._busy_since = now
        try:
            self._emit_user_text(message)
        except Exception:
            with self._lock:
                self._busy = False
                self._busy_since = None
                self._last_activity_at = now
                self._needs_reschedule = True
            logger.exception(
                "Heartbeat input emission failed",
                extra={"event": "heartbeat.emit.failed"},
            )
            return False

        with self._lock:
            self._last_activity_at = max(self._last_activity_at, now)
            self._needs_reschedule = True
        self._last_mode = mode
        if fixed_question is not None:
            self._last_fixed_question = fixed_question
        if expression is not None:
            self._last_expression = expression
        logger.info(
            "Heartbeat emitted",
            extra={"event": "heartbeat.emitted", "mode": mode},
        )
        return True

    def _run(self) -> None:
        while not self._stop_event.wait(self._poll_seconds):
            try:
                self.tick()
            except Exception:
                logger.exception(
                    "Heartbeat scheduler check failed",
                    extra={"event": "heartbeat.scheduler.failed"},
                )

    def _choose_mode(
        self,
        config: HeartbeatConfig,
        *,
        allow_screen: bool = True,
        idle_policy: str = "medium",
    ) -> str:
        modes = ["screen", "monologue", "question"] if allow_screen else ["monologue", "question"]
        weights_by_mode = _policy_mode_weights(config, idle_policy)
        weights = [weights_by_mode.get(mode, 0.0) for mode in modes]
        if not any(weights):
            return "monologue"
        if sum(weight > 0 for weight in weights) > 1 and self._last_mode in modes:
            weights[modes.index(self._last_mode)] = 0.0
        return self._rng.choices(modes, weights=weights, k=1)[0]

    def _ensure_schedule(self, config: HeartbeatConfig) -> None:
        with self._lock:
            if (
                not self._needs_reschedule
                and self._scheduled_range == config.interval_minutes_range
            ):
                return
            low, high = config.interval_minutes_range
            interval = self._rng.uniform(low, high)
            self._next_due_at = self._last_activity_at + interval * 60.0
            self._scheduled_range = config.interval_minutes_range
            self._needs_reschedule = False
        logger.info(
            "Next heartbeat scheduled",
            extra={
                "event": "heartbeat.scheduled",
                "interval_minutes": round(interval, 3),
            },
        )

    def _build_message(
        self,
        config: HeartbeatConfig,
        *,
        mode: str,
        screen_summary: str | None,
        idle_seconds: float,
        idle_policy: str,
        recent_user_inputs: tuple[str, ...],
        sentence_count: int,
    ) -> tuple[str, str | None, str | None]:
        local_time = self._wall_clock().strftime("%H:%M")
        idle_minutes = _format_minutes(idle_seconds / 60.0)
        prefix = f"[心跳·{_mode_label(mode)} {local_time}，已安静 {idle_minutes} 分钟]"
        context_hint = _recent_context_hint(recent_user_inputs)
        policy_hint = _policy_instruction(idle_policy)
        ending = (
            f"请保持当前角色设定，用当前对话语言自然回应；这次大约说 {sentence_count} 句，"
            "自然优先，不要解释心跳机制。"
        )

        expression_hint = ""
        expression: str | None = None
        if config.common_expressions and self._rng.random() < config.expression_chance:
            expression = self._choose_without_repeat(
                config.common_expressions, self._last_expression
            )
            expression_hint = f" 可以自然融入这个表达或表情：{expression}；不要生硬堆砌。"

        if mode == "screen" and screen_summary:
            return (
                f"{prefix} 屏幕摘要：{screen_summary}。{context_hint}{policy_hint}{ending}{expression_hint}",
                None,
                expression,
            )
        fixed_question: str | None = None
        if mode == "question":
            fixed_question_chance = _policy_fixed_question_chance(config, idle_policy)
            if config.fixed_questions and self._rng.random() < fixed_question_chance:
                fixed_question = self._choose_without_repeat(
                    config.fixed_questions, self._last_fixed_question
                )
                instruction = (
                    "请按当前角色口吻自然地问用户这个问题，可以适当改写："
                    f"{fixed_question}"
                )
            else:
                instruction = config.question_instruction
        else:
            instruction = config.monologue_instruction
        return (
            f"{prefix} {context_hint}{policy_hint}{instruction} {ending}{expression_hint}",
            fixed_question,
            expression,
        )

    def _choose_without_repeat(self, values: tuple[str, ...], previous: str | None) -> str:
        candidates = [value for value in values if value != previous]
        return self._rng.choice(candidates or list(values))


def _mode_label(mode: str) -> str:
    return {"screen": "识屏", "question": "主动提问", "monologue": "自言自语"}.get(
        mode, "自言自语"
    )


def _format_minutes(minutes: float) -> str:
    if minutes < 1.0:
        return f"{minutes:.1f}"
    return str(int(minutes))


def _idle_policy(idle_seconds: float) -> str:
    if idle_seconds < SHORT_IDLE_SECONDS:
        return "short"
    if idle_seconds >= LONG_IDLE_SECONDS:
        return "long"
    return "medium"


def _policy_mode_weights(config: HeartbeatConfig, idle_policy: str) -> dict[str, float]:
    weights = {mode: max(0.0, config.mode_weights.get(mode, 0.0)) for mode in config.mode_weights}
    screen = weights.get("screen", 0.0)
    monologue = weights.get("monologue", 0.0)
    question = weights.get("question", 0.0)

    if idle_policy == "short":
        if monologue > 0.0 or question > 0.0:
            weights["screen"] = 0.0
        weights["monologue"] = monologue * 1.15
        weights["question"] = question * 1.1
    elif idle_policy == "long":
        weights["screen"] = screen * 1.8
        weights["monologue"] = monologue * 0.75
        weights["question"] = question * 1.25
    return weights


def _policy_fixed_question_chance(config: HeartbeatConfig, idle_policy: str) -> float:
    chance = config.fixed_question_chance
    if chance <= 0.0:
        return 0.0
    if idle_policy == "short":
        return min(chance, 0.15)
    if idle_policy == "long" and config.fixed_questions:
        return max(chance, 0.65)
    return chance


def _policy_instruction(idle_policy: str) -> str:
    if idle_policy == "short":
        return (
            "这次空闲时间很短，优先延续最近话题；不要突然换到无关寒暄、作息提醒"
            "或新的大问题。可以顺着刚才内容追问一句、补一句感受，或轻声自言自语。"
        )
    if idle_policy == "long":
        return (
            "用户已经安静较久，可以更主动地重新观察当前状态；如果没有明确上下文，"
            "可以自然使用预设问题或关心用户正在做什么。"
        )
    return "如果最近话题还清楚，优先自然承接；否则再轻度开启新话题。"


def _recent_context_hint(recent_user_inputs: tuple[str, ...]) -> str:
    if not recent_user_inputs:
        return ""
    joined = "；".join(
        f"{index}. {text}" for index, text in enumerate(recent_user_inputs, start=1)
    )
    return f"最近几次用户输入（从旧到新）：{joined}。"


def _clean_recent_user_input(text: str | None) -> str:
    if text is None:
        return ""
    cleaned = " ".join(str(text).split())
    if not cleaned:
        return ""
    if len(cleaned) <= RECENT_USER_INPUT_CHARS:
        return cleaned
    return cleaned[:RECENT_USER_INPUT_CHARS].rstrip() + "..."
