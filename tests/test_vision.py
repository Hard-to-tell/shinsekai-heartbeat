from __future__ import annotations

import unittest

from tests import _bootstrap  # noqa: F401
from plugins.heartbeat_companion.config import HeartbeatConfig
from plugins.heartbeat_companion.vision import MAX_SCREEN_SUMMARY_CHARS, query_screen


class VisionTests(unittest.TestCase):
    def test_registered_moondream_tool_is_called(self) -> None:
        received = {}

        def tool(question, monitor_index):
            received.update(question=question, monitor_index=monitor_index)
            return {"answer": "  The user   is writing code.  "}

        entries = [(tool, "moondream_query_screen", None, "vision", "low")]
        config = HeartbeatConfig(monitor_index=2)

        answer = query_screen(config, entries=entries)

        self.assertEqual(answer, "The user is writing code.")
        self.assertEqual(received["monitor_index"], 2)

    def test_missing_or_failed_tool_returns_none(self) -> None:
        config = HeartbeatConfig()
        self.assertIsNone(query_screen(config, entries=[]))

        def broken_tool(**kwargs):
            _ = kwargs
            raise RuntimeError("offline")

        entries = [(broken_tool, "moondream_query_screen", None, "vision", "low")]
        self.assertIsNone(query_screen(config, entries=entries))

    def test_summary_is_truncated(self) -> None:
        def tool(**kwargs):
            _ = kwargs
            return {"answer": "x" * 500}

        entries = [(tool, "moondream_query_screen", None, "vision", "low")]
        answer = query_screen(HeartbeatConfig(), entries=entries)
        self.assertEqual(len(answer or ""), MAX_SCREEN_SUMMARY_CHARS)


if __name__ == "__main__":
    unittest.main()
