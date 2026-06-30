from __future__ import annotations

import unittest

from tests import _bootstrap  # noqa: F401
from plugins.heartbeat_companion import runtime


class FakeScheduler:
    def __init__(self) -> None:
        self.activity_count = 0

    def note_user_activity(self) -> None:
        self.activity_count += 1


class RuntimeTests(unittest.TestCase):
    def tearDown(self) -> None:
        with runtime._lock:
            runtime._scheduler = None

    def test_own_heartbeat_does_not_count_as_user_activity(self) -> None:
        scheduler = FakeScheduler()
        with runtime._lock:
            runtime._scheduler = scheduler

        runtime.process_user_input("[心跳·自言自语 10:00] test")
        runtime.process_user_input("hello")

        self.assertEqual(scheduler.activity_count, 1)


if __name__ == "__main__":
    unittest.main()
