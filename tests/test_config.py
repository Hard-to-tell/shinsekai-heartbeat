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
            self.assertEqual(config.interval_minutes, 10.0)
            self.assertEqual(config.mode_weights["screen"], 50.0)

    def test_values_are_clamped_and_zero_weights_fall_back(self) -> None:
        config = HeartbeatConfig.from_mapping(
            {
                "interval_minutes": -5,
                "monitor_index": 999,
                "mode_weights": {"screen": -1, "monologue": 0, "question": 0},
            }
        )

        self.assertEqual(config.interval_minutes, 0.1)
        self.assertEqual(config.monitor_index, 32)
        self.assertEqual(config.mode_weights["screen"], 0.0)
        self.assertEqual(config.mode_weights["monologue"], 1.0)

    def test_invalid_hot_reload_keeps_last_valid_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps({"interval_minutes": 20}), encoding="utf-8")
            store = ConfigStore(path)
            self.assertEqual(store.initialize().interval_minutes, 20.0)

            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(store.get(force=True).interval_minutes, 20.0)

    def test_hot_reload_detects_immediate_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            store = ConfigStore(path)
            store.initialize()

            path.write_text(json.dumps({"interval_minutes": 0.1}), encoding="utf-8")

            self.assertEqual(store.get().interval_minutes, 0.1)


if __name__ == "__main__":
    unittest.main()
