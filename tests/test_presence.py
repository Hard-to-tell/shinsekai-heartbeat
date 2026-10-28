import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tests import _bootstrap
from tests.test_scheduler import make_store, FakeClock
from plugins.heartbeat_companion import status
from plugins.heartbeat_companion.scheduler import HeartbeatScheduler
from plugins.heartbeat_companion.runtime import detect_study_command


class PresenceTests(unittest.TestCase):
    def test_negative_start_does_not_enable_study(self):
        for text in ("不要开启学习模式", "别打开专注模式", "不想开始学习"):
            self.assertEqual(detect_study_command(text), "stop")

    def test_rejected_heartbeat_is_not_counted_as_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(tmp, {"interval_minutes": 0.5})
            clock = FakeClock()
            scheduler = HeartbeatScheduler(store, lambda _: False, clock=clock)
            scheduler._active = True
            scheduler.tick()
            clock.advance(30)
            with self.assertLogs(level="ERROR"):
                self.assertFalse(scheduler.tick())
            self.assertEqual(scheduler._unanswered_heartbeats, 0)

    def test_correction_discards_inflight_study_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(tmp, {"study_check_interval_minutes": 1})
            clock = FakeClock()
            emitted = []
            def screen(config):
                scheduler.trust_study_once()
                scheduler.note_user_activity("没分心，你看错了")
                return ("distracted", "DISTRACTED: video game")
            scheduler = HeartbeatScheduler(store, emitted.append, clock=clock, study_screen_reader=screen)
            scheduler._active = True
            scheduler.start_study_session()
            clock.advance(60)
            self.assertFalse(scheduler.tick())
            self.assertEqual(emitted, [])
            self.assertEqual(scheduler._study_distractions, 0)

    def test_random_wait_is_bounded_and_recovers_after_user_input(self):
        class MidpointRandom:
            def uniform(self, low, high):
                return (low + high) / 2
        with tempfile.TemporaryDirectory() as tmp:
            store = make_store(tmp, {"interval_minutes_range": [5, 15]})
            scheduler = HeartbeatScheduler(store, lambda _: None, clock=FakeClock(), rng=MidpointRandom())
            waits = []
            for count in (0, 1, 2, 3, 100):
                scheduler._unanswered_heartbeats = count
                scheduler._needs_reschedule = True
                scheduler._ensure_schedule(store.get())
                waits.append(scheduler._next_due_at / 60)
            self.assertTrue(all(5 <= wait <= 15 for wait in waits))
            self.assertLess(waits[0], 10)
            self.assertEqual(waits, sorted(waits))
            self.assertEqual(waits[-1], waits[-2])
            scheduler.note_user_activity("hello")
            scheduler._ensure_schedule(store.get())
            self.assertEqual(scheduler._next_due_at / 60, waits[0])

    def test_status_expires_without_claiming_chat_is_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(status.time, "time", return_value=100):
                status.publish(root, "学习中")
                self.assertEqual(status.read(root), "学习中")
            with patch.object(status.time, "time", return_value=121):
                self.assertIn("暂未刷新", status.read(root))
            (root / "status.json").write_text("broken")
            self.assertIn("尚未收到", status.read(root))
