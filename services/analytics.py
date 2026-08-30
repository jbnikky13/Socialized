"""Local analytics/event tracking for the Socialized agent."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

EVENT_FILE = os.path.join("data", "events.jsonl")


def track_event(event: str, platform: str, content_id: str = "", metadata: dict | None = None) -> None:
    os.makedirs(os.path.dirname(EVENT_FILE), exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "platform": platform,
        "content_id": content_id,
        "metadata": metadata or {},
    }
    with open(EVENT_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_events() -> list[dict]:
    if not os.path.exists(EVENT_FILE):
        return []
    with open(EVENT_FILE, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
