from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

from .config import LOG_PATH

_lock = threading.Lock()


def write_raw_logs(data: dict) -> None:
    """Append one JSON object as a line to logs.jsonl. Auto-stamps ts (UTC ISO8601)."""
    entry = {"ts": datetime.now(timezone.utc).isoformat(), **data}
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with _lock:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line)
