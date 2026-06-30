from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from plugins.heartbeat_companion.config import ConfigStore, HeartbeatConfig


class ConfigTests(unittest.TestCase):
    def test_initialize_creates_default_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            store = ConfigStore(path)

            config = store.initialize()

            self.assertTrue(path.is_file())
            self.assertEqual(config.interval_minutes_range, (5.0, 15.0))
            self.assertEqual(config.mode_weights["screen"], 50.0)
            self.assertTrue(config.fixed_questions)
            self.assertTrue(config.common_expressions)

    def test_values_are_clamped_and_zero_weights_fall_back(self) -> None:
        config = HeartbeatConfig.from_mapping(
            {
                "interval_minutes": -5,
                "monitor_index": 999,
                "mode_weights": {"screen": -1, "monologue": 0, "question": 0},
            }
        )

        self.assertEqual(config.interval_minutes_range, (0.1, 0.1))
        self.assertEqual(config.monitor_index, 32)
        self.assertEqual(config.mode_weights["screen"], 0.0)
        self.assertEqual(config.mode_weights["monologue"], 1.0)

    def test_invalid_hot_reload_keeps_last_valid_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"interval_minutes": 20}), encoding="utf-8")
            store = ConfigStore(path)
            self.assertEqual(store.initialize().interval_minutes_range, (20.0, 20.0))

            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(store.get(force=True).interval_minutes_range, (20.0, 20.0))

    def test_hot_reload_detects_immediate_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            store = ConfigStore(path)
            store.initialize()

            path.write_text(
                json.dumps({"interval_minutes_range": [0.1, 0.5]}), encoding="utf-8"
            )

            self.assertEqual(store.get().interval_minutes_range, (0.1, 0.5))

    def test_custom_content_lists_and_ranges_are_loaded(self) -> None:
        config = HeartbeatConfig.from_mapping(
            {
                "reply_sentence_range": [6, 2],
                "fixed_question_chance": 2,
                "fixed_questions": ["睡了吗？", "", 123],
                "expression_chance": -1,
                "common_expressions": ["✨", "（打哈欠）"],
            }
        )

        self.assertEqual(config.reply_sentence_range, (2, 6))
        self.assertEqual(config.fixed_question_chance, 1.0)
        self.assertEqual(config.fixed_questions, ("睡了吗？",))
        self.assertEqual(config.expression_chance, 0.0)
        self.assertEqual(config.common_expressions, ("✨", "（打哈欠）"))


if __name__ == "__main__":
    unittest.main()
