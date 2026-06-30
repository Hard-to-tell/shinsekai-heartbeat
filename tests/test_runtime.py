from __future__ import annotations

import unittest

from tests import _bootstrap  # noqa: F401
from plugins.heartbeat_companion import runtime


class FakeScheduler:
    def __init__(self) -> None:
        self.activity_count = 0
        self.reply_finished_count = 0
        self.reply_tracking: list[bool] = []

    def note_user_activity(self) -> None:
        self.activity_count += 1

    def note_reply_finished(self) -> None:
        self.reply_finished_count += 1

    def enable_reply_tracking(self, enabled: bool = True) -> None:
        self.reply_tracking.append(enabled)

    def stop(self) -> None:
        pass


class FakeChatUIContext:
    def __init__(self) -> None:
        self.reply_handler = None
        self.display_handler = None
        self.typing_handler = None
        self.skip_handler = None
        self.disconnect_count = 0

    def on_llm_reply_finished(self, handler):
        self.reply_handler = handler

        return self._disconnect

    def on_dialog_typing_finished(self, handler):
        self.typing_handler = handler

        return self._disconnect

    def on_display_words_changed(self, handler):
        self.display_handler = handler

        return self._disconnect

    def on_skip_speech_signal(self, handler):
        self.skip_handler = handler

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

    def test_chat_ui_reply_finished_event_releases_scheduler(self) -> None:
        scheduler = FakeScheduler()
        context = FakeChatUIContext()
        with runtime._lock:
            runtime._scheduler = scheduler

        runtime.bind_chat_ui(context)
        self.assertEqual(scheduler.reply_tracking, [True])

        runtime.process_user_input("hello")
        context.display_handler("<b>你</b>：hello")
        context.typing_handler()
        self.assertEqual(scheduler.reply_finished_count, 0)

        context.display_handler("<b>角色</b>：你好")
        context.typing_handler()
        self.assertEqual(scheduler.reply_finished_count, 1)

        runtime.process_user_input("hello again")
        context.reply_handler()
        self.assertEqual(scheduler.reply_finished_count, 2)

        runtime.process_user_input("one more")
        context.skip_handler()
        self.assertEqual(scheduler.reply_finished_count, 3)

        runtime.shutdown()
        self.assertEqual(context.disconnect_count, 4)
        self.assertEqual(scheduler.reply_tracking, [True, False])


if __name__ == "__main__":
    unittest.main()
