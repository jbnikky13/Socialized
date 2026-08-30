"""Analytics helpers for Socialized.

Writes to Supabase when configured, with a local JSONL fallback for development.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone

EVENT_FILE = os.path.join("data", "events.jsonl")


def track_event(event: str, platform: str, content_id: str = "", metadata: dict | None = None) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "platform": platform,
        "content_id": content_id,
        "metadata": metadata or {},
    }
    try:
        from services.db import record_metric
        if content_id:
            record_metric(content_id, platform, event, metadata or {})
            return
    except Exception:
        pass
    os.makedirs(os.path.dirname(EVENT_FILE), exist_ok=True)
    with open(EVENT_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def record_metric(content_id: str, platform: str, event_type: str, metrics: dict | None = None) -> None:
    """Compatibility wrapper used by the dashboard."""
    track_event(event_type, platform, content_id, metrics or {})


def read_events() -> list[dict]:
    if not os.path.exists(EVENT_FILE):
        return []
    with open(EVENT_FILE, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
