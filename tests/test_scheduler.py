from __future__ import annotations

import json
import tempfile
import unittest
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


if __name__ == "__main__":
    unittest.main()
