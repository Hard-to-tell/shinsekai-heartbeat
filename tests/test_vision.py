from __future__ import annotations

import unittest

from tests import _bootstrap  # noqa: F401
from plugins.heartbeat_companion.config import HeartbeatConfig
from plugins.heartbeat_companion.vision import (
    DISTRACTED,
    MAX_SCREEN_SUMMARY_CHARS,
    STUDY,
    classify_study_screen,
    query_screen,
    query_study_screen,
)


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

    def test_study_labels_are_binary_and_ambiguous_output_reminds(self) -> None:
        self.assertEqual(classify_study_screen("STUDY - writing notes"), STUDY)
        self.assertEqual(
            classify_study_screen("DISTRACTED - watching a comedy clip"), DISTRACTED
        )
        self.assertEqual(classify_study_screen("UNCERTAIN - maybe reading"), DISTRACTED)
        self.assertEqual(classify_study_screen("Maybe playing a game"), DISTRACTED)

    def test_study_query_uses_dedicated_classification_question(self) -> None:
        received = {}

        def tool(question, monitor_index):
            received.update(question=question, monitor_index=monitor_index)
            return {"answer": "STUDY - educational video on Bilibili"}

        result = query_study_screen(
            HeartbeatConfig(monitor_index=1),
            entries=[(tool, "moondream_query_screen", None, "vision", "low")],
        )

        self.assertEqual(result, (STUDY, "STUDY - educational video on Bilibili"))
        self.assertIn("exactly STUDY or DISTRACTED", received["question"])
        self.assertIn("Games, entertainment videos", received["question"])
        self.assertEqual(received["monitor_index"], 1)


if __name__ == "__main__":
    unittest.main()
