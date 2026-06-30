"""Shinsekai Heartbeat Companion plugin entry point."""

from __future__ import annotations

from pathlib import Path

from sdk.plugin import PluginBase
from sdk.plugin_host_context import PluginHostContext
from sdk.register import PluginCapabilityRegistry
from sdk.types import ChatUIContribution

from . import runtime
from .config import PLUGIN_ID


class HeartbeatCompanionPlugin(PluginBase):
    @property
    def plugin_id(self) -> str:
        return PLUGIN_ID

    @property
    def plugin_version(self) -> str:
        return "0.2.0"

    @property
    def plugin_name(self) -> str:
        return "Heartbeat Companion"

    @property
    def plugin_description(self) -> str:
        return "Let the current character speak after the user has been idle."

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
        runtime.configure(plugin_root)
        register.register_user_input_processor(runtime.process_user_input)
        register.register_user_input_trigger(runtime.bind_emit)

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
