"""Import the plugin against a real Shinsekai SDK checkout."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "plugins.heartbeat_companion"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: smoke_host_sdk.py <shinsekai-root>")

    host_root = Path(sys.argv[1]).resolve()
    if not (host_root / "sdk" / "plugin.py").is_file():
        raise SystemExit(f"Shinsekai SDK not found under {host_root}")
    sys.path.insert(0, str(host_root))

    plugins_package = types.ModuleType("plugins")
    plugins_package.__path__ = []
    sys.modules["plugins"] = plugins_package

    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not create plugin package spec")
    package = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_NAME] = package
    spec.loader.exec_module(package)

    from plugins.heartbeat_companion.plugin import HeartbeatCompanionPlugin
    from sdk.register import PluginCapabilityRegistry

    plugin = HeartbeatCompanionPlugin()
    assert plugin.plugin_id == "io.github.hard_to_tell.heartbeat_companion"
    assert plugin.plugin_version == package.__version__
    with tempfile.TemporaryDirectory() as tmp:
        registry = PluginCapabilityRegistry()
        plugin.initialize(registry, Path(tmp), object())
        config_path = Path(tmp) / "config.json"
        assert config_path.is_file()

        config_page = registry.frontend_config_contributions[0]
        values = config_page.load_values()
        values["interval_min_minutes"] = 20.0
        values["interval_max_minutes"] = 20.0
        config_page.save_values(values)
        config_path.write_text("{broken", encoding="utf-8")
        assert config_page.load_values()["interval_min_minutes"] == 20.0
        plugin.shutdown()
    print(f"host SDK smoke test passed for Heartbeat Companion {plugin.plugin_version}")


if __name__ == "__main__":
    main()
