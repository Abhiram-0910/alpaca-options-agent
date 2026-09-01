"""Lightweight alerting for critical events: order placed, kill switch tripped,
daily loss circuit breaker tripped, session spend cap reached, cycle errors.
Always appends a human-readable line to logs/alerts.log; additionally POSTs to
ALERT_WEBHOOK_URL (a Slack- or Discord-compatible incoming webhook — both accept
a bare {"text": ...} payload) if that env var is set. Never raises: a broken or
unconfigured notification path must never block or fail an actual trading/risk
decision, so any error here is swallowed after being written to the log file.
"""
import json
import os
from datetime import datetime, timezone

from agent.config import CONFIG

ALERTS_PATH = os.path.join(CONFIG.logs_dir, "alerts.log")


def alert(event: str, **fields) -> None:
    os.makedirs(CONFIG.logs_dir, exist_ok=True)
    line = f"[{datetime.now(timezone.utc).isoformat()}] {event}: {json.dumps(fields, default=str)}"
    try:
        with open(ALERTS_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass

    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if not webhook_url:
        return
    try:
        import httpx
        httpx.post(webhook_url, json={"text": line}, timeout=5.0)
    except Exception:
        pass
