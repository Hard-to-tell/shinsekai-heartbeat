"""Shinsekai Heartbeat Companion plugin entry point."""

from __future__ import annotations

from pathlib import Path

from sdk.plugin import PluginBase
from sdk.plugin_host_context import PluginHostContext
from sdk.register import PluginCapabilityRegistry
from sdk.types import ChatUIContribution, FrontendConfigContribution

from . import __version__, runtime
from .config import (
    DEFAULT_STUDY_SCREEN_QUESTION,
    PLUGIN_ID,
    from_frontend_values,
    to_frontend_values,
)


def _config_field(
    key: str,
    label: str,
    field_type: str,
    *,
    default,
    description: str = "",
    max_value: float | int | None = None,
    min_value: float | int | None = None,
    placeholder: str = "",
    span: str | None = None,
    step: float | int | None = None,
) -> dict[str, object]:
    field: dict[str, object] = {
        "defaultValue": default,
        "key": key,
        "label": label,
        "name": key,
        "type": field_type,
    }
    # Field descriptions render as hover tooltips that can overlap the sidebar.
    _ = description
    if max_value is not None:
        field["max"] = max_value
    if min_value is not None:
        field["min"] = min_value
    if placeholder:
        field["placeholder"] = placeholder
    if span:
        field["span"] = span
    if step is not None:
        field["step"] = step
    return field


CONFIG_PAGE_SCHEMA = [
    {
        "id": "general",
        "title": "General",
        "description": (
            "Enable the idle heartbeat, choose when it may speak, and optionally "
            "adapt behavior to the idle duration."
        ),
        "fields": [
            _config_field(
                "enabled",
                "Enabled",
                "boolean",
                default=True,
                description="Turn the heartbeat companion on or off.",
                span="full",
            ),
            _config_field(
                "interval_min_minutes",
                "Minimum idle minutes",
                "number",
                default=5.0,
                description="Shortest idle wait before the character may speak.",
                max_value=1440.0,
                min_value=0.1,
                step=0.1,
            ),
            _config_field(
                "interval_max_minutes",
                "Maximum idle minutes",
                "number",
                default=15.0,
                description="Longest idle wait before the character may speak.",
                max_value=1440.0,
                min_value=0.1,
                step=0.1,
            ),
            _config_field(
                "adaptive_idle_policy",
                "Adapt behavior to idle duration",
                "boolean",
                default=True,
                description=(
                    "Short idle periods favor recent conversation while long idle "
                    "periods favor screen context and fixed questions."
                ),
                span="full",
            ),
            _config_field(
                "monitor_index",
                "Monitor index",
                "integer",
                default=-1,
                description=(
                    "-1 follows Moondream Vision's monitor setting. "
                    "Use 0-32 to force a monitor."
                ),
                max_value=32,
                min_value=-1,
                step=1,
            ),
        ],
    },
    {
        "id": "modes",
        "title": "Modes and output",
        "description": "Weights are relative. Set a mode to 0 to disable it.",
        "fields": [
            _config_field(
                "screen_weight",
                "Screen mode weight",
                "number",
                default=50.0,
                description="Uses Moondream screen context when available.",
                max_value=100.0,
                min_value=0.0,
                step=1,
            ),
            _config_field(
                "monologue_weight",
                "Monologue weight",
                "number",
                default=25.0,
                description="Lets the character say something naturally.",
                max_value=100.0,
                min_value=0.0,
                step=1,
            ),
            _config_field(
                "question_weight",
                "Question weight",
                "number",
                default=25.0,
                description="Lets the character ask a time-aware question.",
                max_value=100.0,
                min_value=0.0,
                step=1,
            ),
            _config_field(
                "reply_min_sentences",
                "Minimum sentences",
                "integer",
                default=1,
                description="Shortest requested reply length.",
                max_value=8,
                min_value=1,
                step=1,
            ),
            _config_field(
                "reply_max_sentences",
                "Maximum sentences",
                "integer",
                default=4,
                description="Longest requested reply length.",
                max_value=8,
                min_value=1,
                step=1,
            ),
            _config_field(
                "fixed_question_chance_percent",
                "Fixed question chance (%)",
                "number",
                default=45.0,
                description=(
                    "Chance to use one of the fixed questions when question mode "
                    "is selected."
                ),
                max_value=100.0,
                min_value=0.0,
                step=1,
            ),
            _config_field(
                "expression_chance_percent",
                "Expression chance (%)",
                "number",
                default=35.0,
                description="Chance to prepend one common expression.",
                max_value=100.0,
                min_value=0.0,
                step=1,
            ),
        ],
    },
    {
        "id": "study",
        "title": "Study supervision",
        "description": (
            "Say '我要学习，请监督我' in chat to start one quiet focus session. "
            "Screen checks require Moondream Vision. Each local check can take several "
            "seconds, so use at least 1 minute and prefer 3-5 minutes for normal use."
        ),
        "fields": [
            _config_field(
                "study_supervision_enabled",
                "Enable study supervision",
                "boolean",
                default=True,
                span="full",
            ),
            _config_field(
                "study_check_interval_minutes",
                "Screen check interval (minutes)",
                "number",
                default=5.0,
                description="How often study mode quietly checks the screen.",
                max_value=60.0,
                min_value=1.0,
                step=0.5,
            ),
            _config_field(
                "study_focus_minutes",
                "Focus session length (minutes)",
                "number",
                default=25.0,
                description="Study mode stops and suggests a break after this time.",
                max_value=240.0,
                min_value=1.0,
                step=1.0,
            ),
        ],
    },
    {
        "id": "prompts",
        "title": "Prompts",
        "description": (
            "Each box is one complete instruction. New lines and semicolons do not "
            "create separate randomly selected prompts."
        ),
        "fields": [
            _config_field(
                "screen_question",
                "Screen question",
                "textarea",
                default="In one short sentence, describe what the user appears to be doing on screen.",
                description=(
                    "One question sent to Moondream Vision. The English default is "
                    "recommended for compatibility, but it has no special format."
                ),
                span="full",
            ),
            _config_field(
                "study_screen_question",
                "Study classification question",
                "textarea",
                default=DEFAULT_STUDY_SCREEN_QUESTION,
                description=(
                    "One structured classification question sent to Moondream during study mode."
                ),
                span="full",
            ),
            _config_field(
                "monologue_instruction",
                "Monologue instruction",
                "textarea",
                default="Keep the current character persona and say something naturally.",
                description=(
                    "One complete instruction sent to the current chat model. "
                    "Write it in any language the model understands."
                ),
                span="full",
            ),
            _config_field(
                "question_instruction",
                "Question instruction",
                "textarea",
                default="Considering the current local time, naturally ask the user a question.",
                description=(
                    "One complete instruction for generating a question. For random "
                    "ready-made questions, use the fixed question list below."
                ),
                span="full",
            ),
        ],
    },
    {
        "id": "content",
        "title": "Fixed text",
        "description": "Put one fixed question or expression on each line.",
        "fields": [
            _config_field(
                "fixed_questions_text",
                "Fixed questions",
                "textarea",
                default="",
                placeholder="One question per line",
                span="full",
            ),
            _config_field(
                "common_expressions_text",
                "Common expressions",
                "textarea",
                default="",
                placeholder="One expression per line",
                span="full",
            ),
        ],
    },
]


CONFIG_PAGE_I18N = {
    "zh_CN": {
        "title": "心跳陪伴",
        "description": "配置空闲触发、模式权重、回复长度、提示词和固定文案。",
        "restartHint": "只修改这些配置通常会自动生效；更新插件代码后仍需重启 Shinsekai。",
        "groups": {
            "general": {
                "title": "基础设置",
                "description": (
                    "控制插件是否启用、空闲多久后允许角色主动开口，以及是否根据空闲时长"
                    "自动调整模式。"
                ),
                "fields": {
                    "enabled": {
                        "label": "启用心跳陪伴",
                    },
                    "interval_min_minutes": {
                        "label": "最短空闲时间（分钟）",
                    },
                    "interval_max_minutes": {
                        "label": "最长空闲时间（分钟）",
                    },
                    "adaptive_idle_policy": {
                        "label": "根据空闲时长自动调整模式",
                    },
                    "monitor_index": {
                        "label": "显示器索引",
                    },
                },
            },
            "modes": {
                "title": "模式与输出",
                "description": "权重是相对比例；某个模式设为 0 就等于关闭该模式。",
                "fields": {
                    "screen_weight": {
                        "label": "识屏模式权重",
                    },
                    "monologue_weight": {
                        "label": "自言自语权重",
                    },
                    "question_weight": {
                        "label": "提问模式权重",
                    },
                    "reply_min_sentences": {"label": "最少回复句数"},
                    "reply_max_sentences": {"label": "最多回复句数"},
                    "fixed_question_chance_percent": {
                        "label": "使用固定问题概率（%）",
                    },
                    "expression_chance_percent": {
                        "label": "附加语气词概率（%）",
                    },
                },
            },
            "study": {
                "title": "学习监督",
                "description": (
                    "在聊天里对角色说“我要学习，请监督我”即可开启一轮低打扰专注；"
                    "确认在学习时保持安静，其余情况才提醒。识屏检查需要 Moondream Vision；"
                    "本地识别一次可能需要十几秒，间隔至少 1 分钟，日常建议设为 3～5 分钟。"
                ),
                "fields": {
                    "study_supervision_enabled": {
                        "label": "启用学习监督（防止误触可关闭）",
                    },
                    "study_check_interval_minutes": {
                        "label": "识屏检查间隔（至少 1 分钟）",
                    },
                    "study_focus_minutes": {
                        "label": "每轮专注时长（分钟）",
                    },
                },
            },
            "prompts": {
                "title": "提示词",
                "description": (
                    "每个输入框都是一条完整指令。换行或分号只用于组织文字，整框内容会一起发送，"
                    "不会像固定文案那样随机拆分。"
                ),
                "fields": {
                    "screen_question": {
                        "label": "识屏问题",
                    },
                    "study_screen_question": {
                        "label": "学习状态分类问题",
                    },
                    "monologue_instruction": {
                        "label": "自言自语提示词",
                    },
                    "question_instruction": {
                        "label": "提问提示词",
                    },
                },
            },
            "content": {
                "title": "固定文案",
                "description": "每行填写一条固定问题或语气词；留空表示不使用该列表。",
                "fields": {
                    "fixed_questions_text": {
                        "label": "固定问题列表",
                        "placeholder": "每行一个问题",
                    },
                    "common_expressions_text": {
                        "label": "常用语气词 / 动作",
                        "placeholder": "每行一个语气词或动作",
                    },
                },
            },
        },
    },
}


class HeartbeatCompanionPlugin(PluginBase):
    @property
    def plugin_id(self) -> str:
        return PLUGIN_ID

    @property
    def plugin_version(self) -> str:
        return __version__

    @property
    def plugin_name(self) -> str:
        return "心跳陪伴 Heartbeat Companion"

    @property
    def plugin_description(self) -> str:
        return "让角色主动陪聊，也能安静监督 25 分钟学习，在你分心时把你叫回来。"

    @property
    def plugin_author(self) -> str:
        return "Hard-to-tell"

    @property
    def priority(self) -> int:
        return 100

    def initialize(
        self,
        register: PluginCapabilityRegistry,
        plugin_root: Path,
        host: PluginHostContext,
    ) -> None:
        _ = host
        config_store = runtime.configure(plugin_root)
        register.register_user_input_processor(runtime.process_user_input)
        register.register_user_input_trigger(runtime.bind_emit)

        def load_config_values():
            return to_frontend_values(config_store.get(force=True))

        def save_config_values(values):
            config_store.save(from_frontend_values(values))

        register.register_frontend_config_page(
            FrontendConfigContribution(
                page_id="heartbeat_companion.settings",
                title="Heartbeat Companion",
                kind="settings",
                description="Configure idle heartbeat prompts, timing, and mode weights.",
                restart_hint=(
                    "Configuration changes are hot-loaded; restart Shinsekai "
                    "after updating plugin code."
                ),
                schema=CONFIG_PAGE_SCHEMA,
                load_values=load_config_values,
                save_values=save_config_values,
                order=120.0,
                i18n=CONFIG_PAGE_I18N,
            )
        )

        def build_chat_bridge(context):
            from PySide6.QtWidgets import QWidget

            runtime.bind_chat_ui(context)
            widget = QWidget()
            widget.setObjectName("heartbeat_companion_event_bridge")
            widget.setFixedSize(0, 0)
            return widget

        register.register_chat_ui_widget(
            ChatUIContribution(
                widget_id="heartbeat_companion.event_bridge",
                placement="overlay",
                build=build_chat_bridge,
                order=1000.0,
            )
        )

    def shutdown(self) -> None:
        runtime.shutdown()


Plugin = HeartbeatCompanionPlugin
