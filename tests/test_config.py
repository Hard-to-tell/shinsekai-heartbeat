from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests import _bootstrap  # noqa: F401
from plugins.heartbeat_companion.config import (
    ConfigStore,
    HeartbeatConfig,
    from_frontend_values,
    to_frontend_values,
)


class ConfigTests(unittest.TestCase):
    def test_initialize_creates_default_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            store = ConfigStore(path)

            config = store.initialize()

            self.assertTrue(path.is_file())
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])
            self.assertEqual(config.interval_minutes_range, (5.0, 15.0))
            self.assertTrue(config.adaptive_idle_policy)
            self.assertEqual(config.mode_weights["screen"], 50.0)
            self.assertEqual(config.study_check_interval_minutes, 5.0)
            self.assertEqual(config.study_focus_minutes, 25.0)
            self.assertTrue(config.study_supervision_enabled)
            self.assertEqual(config.study_safe_words, ("chat",))
            self.assertGreaterEqual(len(config.fixed_questions), 12)
            self.assertIn("忙了这么久，要不要休息一下？", config.fixed_questions)
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
                "study_check_interval_minutes": 0,
                "study_focus_minutes": 999,
            }
        )

        self.assertEqual(config.reply_sentence_range, (2, 6))
        self.assertEqual(config.fixed_question_chance, 1.0)
        self.assertEqual(config.fixed_questions, ("睡了吗？",))
        self.assertEqual(config.expression_chance, 0.0)
        self.assertEqual(config.common_expressions, ("✨", "（打哈欠）"))
        self.assertEqual(config.study_check_interval_minutes, 1.0)
        self.assertEqual(config.study_focus_minutes, 240.0)

    def test_legacy_default_questions_expand_without_overwriting_custom_lists(self) -> None:
        legacy = HeartbeatConfig.from_mapping(
            {
                "fixed_questions": [
                    "这么晚了，为什么还不睡？",
                    "今天过得怎么样？",
                    "忙了这么久，要不要休息一下？",
                ]
            }
        )
        custom = HeartbeatConfig.from_mapping(
            {"fixed_questions": ["只保留我自己的问题"]}
        )

        self.assertGreaterEqual(len(legacy.fixed_questions), 12)
        self.assertEqual(custom.fixed_questions, ("只保留我自己的问题",))

    def test_legacy_study_prompts_migrate_to_lenient_classification(self) -> None:
        legacy_prompt = (
            "Classify the user's visible activity for a study supervision session. "
            "Reply with exactly one label first: STUDY, DISTRACTED, or UNCERTAIN, then a "
            "very short reason. STUDY includes reading, writing, coding, coursework, research, "
            "and educational videos even on entertainment sites. DISTRACTED means clearly "
            "unrelated entertainment such as casual videos, games, or social feeds. Use "
            "UNCERTAIN when the evidence is ambiguous."
        )
        binary_prompt = (
            "Decide whether the visible screen is clearly being used for study. "
            "Reply with exactly STUDY or DISTRACTED. Use STUDY only when there is clear "
            "evidence of reading, writing, coding, coursework, research, or an educational "
            "lecture or tutorial. Games, entertainment videos, social feeds, unrelated chats, "
            "and anything unclear are DISTRACTED."
        )

        legacy = HeartbeatConfig.from_mapping({"study_screen_question": legacy_prompt})
        binary = HeartbeatConfig.from_mapping({"study_screen_question": binary_prompt})

        self.assertIn("When unsure, do not guess DISTRACTED", legacy.study_screen_question)
        self.assertEqual(binary.study_screen_question, legacy.study_screen_question)

    def test_frontend_values_are_user_friendly(self) -> None:
        config = HeartbeatConfig(
            study_supervision_enabled=False,
            interval_minutes_range=(2.5, 9.0),
            mode_weights={"screen": 10.0, "monologue": 30.0, "question": 60.0},
            adaptive_idle_policy=False,
            reply_sentence_range=(2, 5),
            fixed_question_chance=0.25,
            fixed_questions=("question one", "question two"),
            expression_chance=0.8,
            common_expressions=("hmm", "smile"),
            study_check_interval_minutes=7.5,
            study_focus_minutes=40.0,
        )

        values = to_frontend_values(config)

        self.assertEqual(values["interval_min_minutes"], 2.5)
        self.assertEqual(values["interval_max_minutes"], 9.0)
        self.assertEqual(values["screen_weight"], 10.0)
        self.assertFalse(values["adaptive_idle_policy"])
        self.assertEqual(values["fixed_question_chance_percent"], 25.0)
        self.assertEqual(values["expression_chance_percent"], 80.0)
        self.assertEqual(values["fixed_questions_text"], "question one\nquestion two")
        self.assertEqual(values["common_expressions_text"], "hmm\nsmile")
        self.assertEqual(values["study_check_interval_minutes"], 7.5)
        self.assertEqual(values["study_focus_minutes"], 40.0)
        self.assertFalse(values["study_supervision_enabled"])
        self.assertEqual(values["study_safe_words_text"], "chat")

    def test_frontend_values_save_as_runtime_config(self) -> None:
        config = from_frontend_values(
            {
                "enabled": False,
                "study_supervision_enabled": False,
                "interval_min_minutes": 30,
                "interval_max_minutes": 10,
                "screen_weight": 0,
                "monologue_weight": 70,
                "question_weight": 30,
                "adaptive_idle_policy": False,
                "reply_min_sentences": 6,
                "reply_max_sentences": 2,
                "monitor_index": 3,
                "screen_question": "Describe the screen.",
                "monologue_instruction": "Say something.",
                "question_instruction": "Ask something.",
                "fixed_question_chance_percent": 25,
                "fixed_questions_text": "first\n\nsecond\n",
                "expression_chance_percent": 80,
                "common_expressions_text": "hmm\nsmile",
                "study_check_interval_minutes": 8,
                "study_focus_minutes": 50,
                "study_screen_question": "Classify study activity.",
                "study_safe_words_text": "ChatGPT\n\n学校课程\n",
            }
        )

        self.assertFalse(config.enabled)
        self.assertFalse(config.study_supervision_enabled)
        self.assertEqual(config.interval_minutes_range, (10.0, 30.0))
        self.assertEqual(config.mode_weights["screen"], 0.0)
        self.assertEqual(config.mode_weights["monologue"], 70.0)
        self.assertFalse(config.adaptive_idle_policy)
        self.assertEqual(config.reply_sentence_range, (2, 6))
        self.assertEqual(config.monitor_index, 3)
        self.assertEqual(config.fixed_question_chance, 0.25)
        self.assertEqual(config.fixed_questions, ("first", "second"))
        self.assertEqual(config.expression_chance, 0.8)
        self.assertEqual(config.common_expressions, ("hmm", "smile"))
        self.assertEqual(config.study_check_interval_minutes, 8.0)
        self.assertEqual(config.study_focus_minutes, 50.0)
        self.assertEqual(config.study_screen_question, "Classify study activity.")
        self.assertEqual(config.study_safe_words, ("ChatGPT", "学校课程"))


if __name__ == "__main__":
    unittest.main()
