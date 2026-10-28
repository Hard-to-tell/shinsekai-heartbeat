"""Small, expiring status snapshot shared with the settings process."""
import json
import os
import tempfile
import time
from pathlib import Path


def publish(root: Path, message: str) -> None:
    path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root,
                                         prefix=".status-", delete=False) as handle:
            path = Path(handle.name)
            json.dump({"updated": time.time(), "message": message}, handle)
        os.replace(path, root / "status.json")
    finally:
        if path is not None and path.exists():
            path.unlink()


def read(root: Path) -> str:
    try:
        data = json.loads((root / "status.json").read_text(encoding="utf-8"))
        if not 0 <= time.time() - float(data["updated"]) < 20:
            return "状态暂未刷新（聊天可能已关闭，或识屏正在处理）"
        return str(data["message"])
    except (OSError, ValueError, KeyError, TypeError):
        return "尚未收到聊天运行状态"
