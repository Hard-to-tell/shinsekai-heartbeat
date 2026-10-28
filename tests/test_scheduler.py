from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from plugins.heartbeat_companion.config import ConfigStore
from plugins.heartbeat_companion.scheduler import HeartbeatScheduler


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def make_store(tmp: str, values: dict) -> ConfigStore:
    path = Path(tmp) / "config.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    store = ConfigStore(path)
    store.initialize()
    return store


class SchedulerTests(unittest.TestCase):
    def test_disabling_study_keeps_ordinary_heartbeats_running(self) -> None:
        for starts_in_study in (False, True):
            with self.subTest(starts_in_study=starts_in_study):
                with tempfile.TemporaryDirectory() as tmp:
                    store = make_store(tmp, {"interval_minutes": 0.1})
                    clock = FakeClock()
                    emitted: list[str] = []
                    scheduler = HeartbeatScheduler(
                        store, emitted.append, clock=clock, poll_seconds=999,
                        screen_reader=lambda config: None,
                    )
                    scheduler.start()
                    try:
                        if starts_in_study:
                            scheduler.start_study_session()
                        store.save(replace(store.get(), study_supervision_enabled=False))
                        self.assertFalse(scheduler.tick())
                        self.assertFalse(scheduler.study_active)
                        for _ in range(5):
                            clock.advance(1)
                            self.assertFalse(scheduler.tick())
                        clock.advance(1)
                        self.assertTrue(scheduler.tick())
                        self.assertEqual(len(emitted), 1)
                    finally:
                        scheduler.stop()

    def test_heartbeat_waits_for_interval_and_restarts_timer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "interval_minutes": 10,
                    "mode_weights": {"screen": 0, "monologue": 1, "question": 0},
                },
            )
            clock = FakeClock()
            emitted: list[str] = []
            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                clock=clock,
                wall_clock=lambda: datetime(2026, 6, 30, 23, 40),
                poll_seconds=999,
            )
            scheduler.start()
            try:
                clock.advance(599)
                self.assertFalse(scheduler.tick())
                clock.advance(1)
                self.assertTrue(scheduler.tick())
                self.assertIn("[心跳·自言自语 23:40", emitted[0])
                self.assertFalse(scheduler.tick())
            finally:
                scheduler.stop()

    def test_user_activity_delays_due_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(tmp, {"interval_minutes": 10})
            clock = FakeClock()
            emitted: list[str] = []
            scheduler = HeartbeatScheduler(store, emitted.append, clock=clock, poll_seconds=999)
            scheduler.start()
            try:
                clock.advance(590)
                scheduler.note_user_activity()
                clock.advance(20)
                self.assertFalse(scheduler.tick())
                clock.advance(580)
                self.assertTrue(scheduler.tick())
            finally:
                scheduler.stop()

    def test_missing_screen_reader_falls_back_to_question(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "interval_minutes": 0.1,
                    "mode_weights": {"screen": 1, "monologue": 0, "question": 1},
                },
            )
            clock = FakeClock()
            emitted: list[str] = []

            class ScreenFirstRandom:
                def choices(self, modes, *, weights, k):
                    _ = weights, k
                    return ["screen" if "screen" in modes else "question"]

                def uniform(self, low, high):
                    _ = high
                    return low

                def randint(self, low, high):
                    _ = high
                    return low

                def random(self):
                    return 1.0

                def choice(self, values):
                    return values[0]

            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                screen_reader=lambda config: None,
                clock=clock,
                rng=ScreenFirstRandom(),
                poll_seconds=999,
            )
            scheduler.start()
            try:
                clock.advance(6)
                self.assertTrue(scheduler.tick())
                self.assertIn("心跳·主动提问", emitted[0])
            finally:
                scheduler.stop()

    def test_random_interval_length_fixed_question_and_expression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "interval_minutes_range": [5, 15],
                    "mode_weights": {"screen": 0, "monologue": 0, "question": 1},
                    "reply_sentence_range": [1, 4],
                    "fixed_question_chance": 1,
                    "fixed_questions": ["这么晚了，为什么还不睡？"],
                    "expression_chance": 1,
                    "common_expressions": ["（打哈欠）"],
                },
            )
            clock = FakeClock()
            emitted: list[str] = []

            class MaximumRandom:
                def uniform(self, low, high):
                    _ = low
                    return high

                def choices(self, modes, *, weights, k):
                    _ = weights, k
                    return [modes[-1]]

                def randint(self, low, high):
                    _ = low
                    return high

                def random(self):
                    return 0.0

                def choice(self, values):
                    return values[0]

            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                clock=clock,
                rng=MaximumRandom(),
                poll_seconds=999,
            )
            scheduler.start()
            try:
                clock.advance(899)
                self.assertFalse(scheduler.tick())
                clock.advance(1)
                self.assertTrue(scheduler.tick())
                self.assertIn("这么晚了，为什么还不睡？", emitted[0])
                self.assertIn("大约说 4 句", emitted[0])
                self.assertIn("（打哈欠）", emitted[0])
            finally:
                scheduler.stop()

    def test_user_activity_during_screen_query_cancels_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "interval_minutes": 0.1,
                    "mode_weights": {"screen": 1, "monologue": 0, "question": 0},
                },
            )
            clock = FakeClock()
            emitted: list[str] = []
            scheduler: HeartbeatScheduler

            def screen_reader(config):
                _ = config
                scheduler.note_user_activity()
                return "The user is editing a document."

            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                screen_reader=screen_reader,
                clock=clock,
                poll_seconds=999,
            )
            scheduler.start()
            try:
                clock.advance(6)
                self.assertFalse(scheduler.tick())
                self.assertEqual(emitted, [])
            finally:
                scheduler.stop()

    def test_user_activity_during_message_build_cancels_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "interval_minutes": 0.1,
                    "mode_weights": {"screen": 0, "monologue": 1, "question": 0},
                },
            )
            clock = FakeClock()
            emitted: list[str] = []
            scheduler = HeartbeatScheduler(
                store, emitted.append, clock=clock, poll_seconds=999
            )
            scheduler.start()
            original_build_message = scheduler._build_message

            def build_message(*args, **kwargs):
                scheduler.note_user_activity("late user input")
                return original_build_message(*args, **kwargs)

            scheduler._build_message = build_message
            try:
                clock.advance(6)
                self.assertFalse(scheduler.tick())
                self.assertEqual(emitted, [])
            finally:
                scheduler.stop()

    def test_stop_during_message_build_cancels_heartbeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "interval_minutes": 0.1,
                    "mode_weights": {"screen": 0, "monologue": 1, "question": 0},
                },
            )
            clock = FakeClock()
            emitted: list[str] = []
            scheduler = HeartbeatScheduler(
                store, emitted.append, clock=clock, poll_seconds=999
            )
            scheduler.start()
            original_build_message = scheduler._build_message

            def build_message(*args, **kwargs):
                scheduler.stop(timeout=0)
                return original_build_message(*args, **kwargs)

            scheduler._build_message = build_message
            clock.advance(6)

            self.assertFalse(scheduler.tick())
            self.assertEqual(emitted, [])

    def test_short_idle_continues_recent_user_inputs_without_screen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "interval_minutes": 0.1,
                    "mode_weights": {"screen": 1, "monologue": 1, "question": 0},
                    "monologue_instruction": "Continue naturally.",
                },
            )
            clock = FakeClock()
            emitted: list[str] = []

            class FirstWeightedRandom:
                def uniform(self, low, high):
                    _ = high
                    return low

                def choices(self, modes, *, weights, k):
                    _ = k
                    return [next(mode for mode, weight in zip(modes, weights) if weight > 0)]

                def randint(self, low, high):
                    _ = high
                    return low

                def random(self):
                    return 1.0

                def choice(self, values):
                    return values[0]

            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                screen_reader=lambda config: "screen should not be used",
                clock=clock,
                rng=FirstWeightedRandom(),
                poll_seconds=999,
            )
            scheduler.start()
            try:
                scheduler.note_user_activity("first")
                scheduler.note_user_activity("second")
                scheduler.note_user_activity("third")
                scheduler.note_user_activity("x" * 200)
                clock.advance(6)

                self.assertTrue(scheduler.tick())
                self.assertIn("心跳·自言自语", emitted[0])
                self.assertIn("空闲时间很短", emitted[0])
                self.assertNotIn("first", emitted[0])
                self.assertIn("second", emitted[0])
                self.assertIn("third", emitted[0])
                self.assertIn(("x" * 120) + "...", emitted[0])
            finally:
                scheduler.stop()

    def test_adaptive_idle_policy_can_be_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "interval_minutes": 0.1,
                    "adaptive_idle_policy": False,
                    "mode_weights": {"screen": 1, "monologue": 1, "question": 0},
                },
            )
            clock = FakeClock()
            emitted: list[str] = []

            class FirstModeRandom:
                def uniform(self, low, high):
                    _ = high
                    return low

                def choices(self, modes, *, weights, k):
                    _ = k
                    return [next(mode for mode, weight in zip(modes, weights) if weight > 0)]

                def randint(self, low, high):
                    _ = high
                    return low

                def random(self):
                    return 1.0

            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                screen_reader=lambda config: "The user is reading.",
                clock=clock,
                rng=FirstModeRandom(),
                poll_seconds=999,
            )
            scheduler.start()
            try:
                clock.advance(6)
                self.assertTrue(scheduler.tick())
                self.assertIn("心跳·识屏", emitted[0])
            finally:
                scheduler.stop()

    def test_long_idle_boosts_screen_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "interval_minutes": 10,
                    "mode_weights": {"screen": 1, "monologue": 1, "question": 0},
                },
            )
            clock = FakeClock()
            emitted: list[str] = []

            class HighestWeightRandom:
                def uniform(self, low, high):
                    _ = high
                    return low

                def choices(self, modes, *, weights, k):
                    _ = k
                    return [max(zip(modes, weights), key=lambda item: item[1])[0]]

                def randint(self, low, high):
                    _ = high
                    return low

                def random(self):
                    return 1.0

                def choice(self, values):
                    return values[0]

            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                screen_reader=lambda config: "The user is editing code.",
                clock=clock,
                rng=HighestWeightRandom(),
                poll_seconds=999,
            )
            scheduler.start()
            try:
                clock.advance(600)

                self.assertTrue(scheduler.tick())
                self.assertIn("心跳·识屏", emitted[0])
                self.assertIn("用户已经安静较久", emitted[0])
            finally:
                scheduler.stop()

    def test_long_idle_raises_fixed_question_chance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "interval_minutes": 10,
                    "mode_weights": {"screen": 0, "monologue": 0, "question": 1},
                    "fixed_question_chance": 0.1,
                    "fixed_questions": ["还在忙刚才那件事吗？"],
                },
            )
            clock = FakeClock()
            emitted: list[str] = []

            class HalfRandom:
                def uniform(self, low, high):
                    _ = high
                    return low

                def choices(self, modes, *, weights, k):
                    _ = weights, k
                    return [modes[-1]]

                def randint(self, low, high):
                    _ = high
                    return low

                def random(self):
                    return 0.5

                def choice(self, values):
                    return values[0]

            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                clock=clock,
                rng=HalfRandom(),
                poll_seconds=999,
            )
            scheduler.start()
            try:
                clock.advance(600)

                self.assertTrue(scheduler.tick())
                self.assertIn("还在忙刚才那件事吗？", emitted[0])
            finally:
                scheduler.stop()

    def test_reply_tracking_blocks_until_reply_and_tts_finish(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "interval_minutes": 0.1,
                    "mode_weights": {"screen": 0, "monologue": 1, "question": 0},
                },
            )
            clock = FakeClock()
            emitted: list[str] = []
            scheduler = HeartbeatScheduler(
                store, emitted.append, clock=clock, poll_seconds=999
            )
            scheduler.enable_reply_tracking(True)
            scheduler.start()
            try:
                clock.advance(6)
                self.assertTrue(scheduler.tick())

                clock.advance(60)
                self.assertFalse(scheduler.tick())
                self.assertEqual(len(emitted), 1)

                scheduler.note_reply_finished()
                clock.advance(5)
                self.assertFalse(scheduler.tick())
                clock.advance(1)
                self.assertTrue(scheduler.tick())
                self.assertEqual(len(emitted), 2)
            finally:
                scheduler.stop()

    def test_reply_tracking_waits_for_all_pending_replies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "interval_minutes": 0.1,
                    "mode_weights": {"screen": 0, "monologue": 1, "question": 0},
                },
            )
            clock = FakeClock()
            emitted: list[str] = []
            scheduler = HeartbeatScheduler(
                store, emitted.append, clock=clock, poll_seconds=999
            )
            scheduler.enable_reply_tracking(True)
            scheduler.start()
            try:
                scheduler.note_user_activity("first")
                scheduler.note_user_activity("second")
                scheduler.note_reply_finished()

                clock.advance(60)
                self.assertFalse(scheduler.tick())

                scheduler.note_reply_finished()
                clock.advance(5)
                self.assertFalse(scheduler.tick())
                clock.advance(1)
                self.assertTrue(scheduler.tick())
                self.assertEqual(len(emitted), 1)
            finally:
                scheduler.stop()

    def test_consecutive_modes_questions_and_expressions_do_not_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "interval_minutes": 0.1,
                    "mode_weights": {"screen": 0, "monologue": 1, "question": 1},
                    "fixed_question_chance": 1,
                    "fixed_questions": ["问题甲", "问题乙"],
                    "expression_chance": 1,
                    "common_expressions": ["表情甲", "表情乙"],
                },
            )
            clock = FakeClock()
            emitted: list[str] = []

            class FirstAvailableRandom:
                def uniform(self, low, high):
                    _ = high
                    return low

                def choices(self, modes, *, weights, k):
                    _ = k
                    return [next(mode for mode, weight in zip(modes, weights) if weight > 0)]

                def randint(self, low, high):
                    _ = high
                    return low

                def random(self):
                    return 0.0

                def choice(self, values):
                    return values[0]

            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                clock=clock,
                rng=FirstAvailableRandom(),
                poll_seconds=999,
            )
            scheduler.start()
            try:
                for _ in range(4):
                    clock.advance(6)
                    self.assertTrue(scheduler.tick())

                self.assertIn("心跳·自言自语", emitted[0])
                self.assertIn("心跳·主动提问", emitted[1])
                self.assertIn("心跳·自言自语", emitted[2])
                self.assertIn("心跳·主动提问", emitted[3])
                self.assertIn("问题甲", emitted[1])
                self.assertIn("问题乙", emitted[3])
                self.assertIn("表情甲", emitted[0])
                self.assertIn("表情乙", emitted[1])
                self.assertIn("表情甲", emitted[2])
                self.assertIn("表情乙", emitted[3])
            finally:
                scheduler.stop()

    def test_study_mode_is_silent_while_user_is_studying(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "interval_minutes": 0.1,
                    "study_check_interval_minutes": 1,
                    "study_focus_minutes": 25,
                },
            )
            clock = FakeClock()
            emitted: list[str] = []
            checks: list[bool] = []

            def study_reader(config):
                _ = config
                checks.append(True)
                return ("study", "STUDY - writing a report")

            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                study_screen_reader=study_reader,
                clock=clock,
                poll_seconds=999,
            )
            scheduler.start()
            try:
                scheduler.start_study_session()
                clock.advance(6)
                self.assertFalse(scheduler.tick())
                self.assertEqual(checks, [])

                clock.advance(54)
                self.assertFalse(scheduler.tick())
                self.assertEqual(checks, [True])
                self.assertEqual(emitted, [])
            finally:
                scheduler.stop()

    def test_user_correction_skips_one_check_and_resets_escalation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "study_check_interval_minutes": 1,
                    "study_focus_minutes": 25,
                },
            )
            clock = FakeClock()
            emitted: list[str] = []
            checks: list[bool] = []

            def study_reader(config):
                _ = config
                checks.append(True)
                return ("distracted", "DISTRACTED - unrelated game")

            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                study_screen_reader=study_reader,
                clock=clock,
                poll_seconds=999,
            )
            scheduler.start()
            try:
                scheduler.start_study_session()
                clock.advance(60)
                self.assertTrue(scheduler.tick())

                self.assertTrue(scheduler.trust_study_once())
                clock.advance(60)
                self.assertFalse(scheduler.tick())
                self.assertEqual(len(checks), 1)

                clock.advance(60)
                self.assertTrue(scheduler.tick())
                self.assertIn("第 1 次分心", emitted[-1])
            finally:
                scheduler.stop()

    def test_repeated_distraction_reminders_escalate_without_abuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "study_check_interval_minutes": 1,
                    "study_focus_minutes": 25,
                },
            )
            clock = FakeClock()
            emitted: list[str] = []
            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                study_screen_reader=lambda config: (
                    "distracted",
                    "DISTRACTED - watching unrelated short videos",
                ),
                clock=clock,
                poll_seconds=999,
            )
            scheduler.start()
            try:
                scheduler.start_study_session()
                for _ in range(4):
                    clock.advance(60)
                    self.assertTrue(scheduler.tick())

                self.assertIn("第 1 次分心", emitted[0])
                self.assertIn("温和但明确", emitted[0])
                self.assertIn("默认只说 1 句", emitted[0])
                self.assertIn("最多 2 句", emitted[0])
                self.assertIn("第 2 次分心", emitted[1])
                self.assertIn("略带不满", emitted[1])
                self.assertIn("轻微气话", emitted[2])
                self.assertIn("不要辱骂或贬低", emitted[2])
                self.assertIn("真的生气一点", emitted[3])
                self.assertIn("不得人身攻击", emitted[3])
            finally:
                scheduler.stop()

    def test_focus_completion_reminds_break_and_ends_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "study_check_interval_minutes": 5,
                    "study_focus_minutes": 25,
                },
            )
            clock = FakeClock()
            emitted: list[str] = []
            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                study_screen_reader=lambda config: (_ for _ in ()).throw(
                    AssertionError("completion should win over the due screen check")
                ),
                clock=clock,
                poll_seconds=999,
            )
            scheduler.start()
            try:
                scheduler.start_study_session()
                clock.advance(25 * 60)

                self.assertTrue(scheduler.tick())
                self.assertFalse(scheduler.study_active)
                self.assertEqual(len(emitted), 1)
                self.assertIn("心跳·学习完成", emitted[0])
                self.assertIn("休息 5 分钟", emitted[0])
            finally:
                scheduler.stop()

    def test_disabled_study_supervision_does_not_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(tmp, {"study_supervision_enabled": False})
            scheduler = HeartbeatScheduler(store, lambda message: None, poll_seconds=999)
            scheduler.start()
            try:
                self.assertIsNone(scheduler.start_study_session())
                self.assertFalse(scheduler.study_active)
            finally:
                scheduler.stop()

    def test_completed_session_can_start_again(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "study_check_interval_minutes": 1,
                    "study_focus_minutes": 3,
                },
            )
            clock = FakeClock()
            emitted: list[str] = []
            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                study_screen_reader=lambda config: (
                    "distracted",
                    "DISTRACTED",
                ),
                clock=clock,
                poll_seconds=999,
            )
            scheduler.start()
            try:
                scheduler.start_study_session()
                clock.advance(3 * 60)
                self.assertTrue(scheduler.tick())
                self.assertFalse(scheduler.study_active)

                scheduler.start_study_session()
                clock.advance(60)
                self.assertTrue(scheduler.tick())
                self.assertTrue(scheduler.study_active)
                self.assertIn("第 1 次分心", emitted[-1])
            finally:
                scheduler.stop()

    def test_stopping_during_study_screen_check_cancels_reminder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(
                tmp,
                {
                    "study_check_interval_minutes": 1,
                    "study_focus_minutes": 25,
                },
            )
            clock = FakeClock()
            emitted: list[str] = []
            scheduler: HeartbeatScheduler

            def study_reader(config):
                _ = config
                scheduler.stop_study_session()
                return ("distracted", "DISTRACTED - social feed")

            scheduler = HeartbeatScheduler(
                store,
                emitted.append,
                study_screen_reader=study_reader,
                clock=clock,
                poll_seconds=999,
            )
            scheduler.start()
            try:
                scheduler.start_study_session()
                clock.advance(60)

                self.assertFalse(scheduler.tick())
                self.assertFalse(scheduler.study_active)
                self.assertEqual(emitted, [])
            finally:
                scheduler.stop()


if __name__ == "__main__":
    unittest.main()
