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

    def note_user_activity(self, text: str | None = None) -> None:
        self.activity_count += 1
        self.activity_texts.append(text)

    def note_reply_finished(self) -> None:
        self.reply_finished_count += 1

    def enable_reply_tracking(self, enabled: bool = True) -> None:
        self.reply_tracking.append(enabled)

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
