from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from plugins.heartbeat_companion import runtime


class FakeScheduler:
    def __init__(self) -> None:
        self.activity_count = 0
        self.activity_texts: list[str | None] = []
        self.reply_finished_count = 0
        self.reply_tracking: list[bool] = []
        self.study_start_count = 0
        self.study_stop_count = 0
        self.study_was_active = True
        self.study_focus_minutes: float | None = 25.0
        self.study_trust_count = 0

    def note_user_activity(self, text: str | None = None) -> None:
        self.activity_count += 1
        self.activity_texts.append(text)

    def note_reply_finished(self) -> None:
        self.reply_finished_count += 1

    def enable_reply_tracking(self, enabled: bool = True) -> None:
        self.reply_tracking.append(enabled)

    def start_study_session(self) -> float | None:
        self.study_start_count += 1
        return self.study_focus_minutes

    def stop_study_session(self) -> bool:
        self.study_stop_count += 1
        return self.study_was_active

    def trust_study_once(self) -> bool:
        self.study_trust_count += 1
        return True

    def stop(self) -> None:
        pass


class FakeChatUIContext:
    def __init__(self) -> None:
        self.reply_handler = None
        self.disconnect_count = 0

    def on_llm_reply_finished(self, handler):
        self.reply_handler = handler

        return self._disconnect

    def _disconnect(self) -> None:
        self.disconnect_count += 1


class RuntimeTests(unittest.TestCase):
    def tearDown(self) -> None:
        runtime.shutdown()

    def test_own_heartbeat_does_not_count_as_user_activity(self) -> None:
        scheduler = FakeScheduler()
        with runtime._lock:
            runtime._scheduler = scheduler

        runtime.process_user_input("[心跳·自言自语 10:00] test")
        runtime.process_user_input("hello")

        self.assertEqual(scheduler.activity_count, 1)
        self.assertEqual(scheduler.activity_texts, ["hello"])

    def test_configure_returns_the_runtime_config_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = runtime.configure(Path(tmp))

            with runtime._lock:
                self.assertIs(runtime._config_store, store)

    def test_natural_language_starts_study_supervision(self) -> None:
        scheduler = FakeScheduler()
        scheduler.study_focus_minutes = 3.0
        with runtime._lock:
            runtime._scheduler = scheduler

        processed = runtime.process_user_input("我要学习，请监督我！")

        self.assertEqual(scheduler.study_start_count, 1)
        self.assertEqual(scheduler.study_stop_count, 0)
        self.assertTrue(processed.startswith("我要学习，请监督我！"))
        self.assertIn("本轮实际专注时长为 3 分钟", processed)
        self.assertIn("不要自行改用其他时长", processed)
        self.assertEqual(scheduler.activity_count, 1)

    def test_continue_study_starts_a_fresh_session(self) -> None:
        scheduler = FakeScheduler()
        scheduler.study_focus_minutes = 3.0
        with runtime._lock:
            runtime._scheduler = scheduler

        processed = runtime.process_user_input(
            "不用，因为我一直在分心，继续学习三分钟"
        )

        self.assertEqual(scheduler.study_start_count, 1)
        self.assertIn("本轮实际专注时长为 3 分钟", processed)

    def test_disabled_study_supervision_does_not_claim_it_started(self) -> None:
        scheduler = FakeScheduler()
        scheduler.study_focus_minutes = None
        with runtime._lock:
            runtime._scheduler = scheduler

        processed = runtime.process_user_input("监督我学习")

        self.assertEqual(scheduler.study_start_count, 1)
        self.assertIn("学习监督功能当前已关闭", processed)
        self.assertNotIn("学习监督已开启", processed)

    def test_natural_language_stops_study_supervision(self) -> None:
        scheduler = FakeScheduler()
        with runtime._lock:
            runtime._scheduler = scheduler

        processed = runtime.process_user_input("我先休息一下，停止监督吧")

        self.assertEqual(scheduler.study_stop_count, 1)
        self.assertEqual(scheduler.study_start_count, 0)
        self.assertEqual(processed, "我先休息一下，停止监督吧")

    def test_negative_command_wins_over_embedded_start_words(self) -> None:
        scheduler = FakeScheduler()
        with runtime._lock:
            runtime._scheduler = scheduler

        runtime.process_user_input("不要监督我学习")

        self.assertEqual(scheduler.study_stop_count, 1)
        self.assertEqual(scheduler.study_start_count, 0)

    def test_general_study_chat_does_not_toggle_mode(self) -> None:
        scheduler = FakeScheduler()
        with runtime._lock:
            runtime._scheduler = scheduler

        runtime.process_user_input("你觉得我今天该学习什么？")

        self.assertEqual(scheduler.study_start_count, 0)
        self.assertEqual(scheduler.study_stop_count, 0)

    def test_user_correction_trusts_study_for_one_check(self) -> None:
        scheduler = FakeScheduler()
        with runtime._lock:
            runtime._scheduler = scheduler

        runtime.process_user_input("没分心，你看错了，继续就好")

        self.assertEqual(scheduler.study_trust_count, 1)
        self.assertEqual(scheduler.study_start_count, 0)
        self.assertEqual(scheduler.study_stop_count, 0)

    def test_only_final_reply_event_releases_scheduler(self) -> None:
        scheduler = FakeScheduler()
        context = FakeChatUIContext()
        with runtime._lock:
            runtime._scheduler = scheduler

        runtime.bind_chat_ui(context)
        self.assertEqual(scheduler.reply_tracking, [True])

        runtime.process_user_input("hello")
        self.assertEqual(scheduler.reply_finished_count, 0)

        context.reply_handler()
        self.assertEqual(scheduler.reply_finished_count, 1)

        runtime.shutdown()
        self.assertEqual(context.disconnect_count, 1)
        self.assertEqual(scheduler.reply_tracking, [True, False])


if __name__ == "__main__":
    unittest.main()
