import json
import os
from datetime import datetime, timezone

from agent.config import CONFIG


def log_event(event_type: str, **fields):
    os.makedirs(CONFIG.logs_dir, exist_ok=True)
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "type": event_type, **fields}
    path = os.path.join(CONFIG.logs_dir, "trade_log.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    return entry
