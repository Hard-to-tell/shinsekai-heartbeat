"""Import the repository root as ``plugins.heartbeat_companion`` in tests."""

from __future__ import annotations

import logging
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def install_test_package() -> None:
    if "sdk.logging" not in sys.modules:
        sdk_module = sys.modules.setdefault("sdk", types.ModuleType("sdk"))
        logging_module = types.ModuleType("sdk.logging")

        def get_logger(name=None, *, plugin_id=None):
            _ = plugin_id
            return logging.getLogger(name)

        logging_module.get_logger = get_logger
        sys.modules["sdk.logging"] = logging_module
        sdk_module.logging = logging_module

    plugins_module = sys.modules.setdefault("plugins", types.ModuleType("plugins"))
    if not hasattr(plugins_module, "__path__"):
        plugins_module.__path__ = []

    package_name = "plugins.heartbeat_companion"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(ROOT)]
        package.__package__ = package_name
        sys.modules[package_name] = package


install_test_package()
