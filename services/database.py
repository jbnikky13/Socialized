from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("content_bot.db")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            title TEXT,
            script TEXT,
            description TEXT,
            tags TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            video_path TEXT,
            scheduled_at TEXT,
            youtube_id TEXT,
            created_at TEXT NOT NULL
        )""")


def add_content(topic, title="", script="", description="", tags=None, video_path="", scheduled_at=""):
    tags = tags or []
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO content(topic,title,script,description,tags,status,video_path,scheduled_at,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (topic, title, script, description, json.dumps(tags), "draft", video_path, scheduled_at,
             datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def list_content(status=None):
    with _conn() as c:
        if status:
            rows = c.execute("SELECT * FROM content WHERE status=? ORDER BY id DESC", (status,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM content ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def get_content(item_id):
    with _conn() as c:
        row = c.execute("SELECT * FROM content WHERE id=?", (item_id,)).fetchone()
    return dict(row) if row else None


def update_content(item_id, **fields):
    allowed = {"topic", "title", "script", "description", "tags", "status", "video_path", "scheduled_at", "youtube_id"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    if "tags" in fields and isinstance(fields["tags"], list):
        fields["tags"] = json.dumps(fields["tags"])
    sets = ", ".join(f"{k}=?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE content SET {sets} WHERE id=?", (*fields.values(), item_id))


def delete_content(item_id):
    with _conn() as c:
        c.execute("DELETE FROM content WHERE id=?", (item_id,))


def decode_tags(row):
    try:
        return json.loads(row.get("tags") or "[]")
    except Exception:
        return []
