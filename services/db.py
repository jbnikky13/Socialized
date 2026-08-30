"""Supabase persistence helpers for Socialized."""
from __future__ import annotations
import os
from typing import Any
from supabase import create_client


def client():
    url = os.getenv("SUPABASE_URL")
    # Streamlit server-side apps should use the service-role key for backend
    # persistence when no Supabase Auth session is present. Never expose this
    # key to the browser or commit it to GitHub.
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_PUBLISHABLE_KEY")
    )
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and a Supabase server key are required")
    return create_client(url, key)


def create_campaign(name: str, niche: str, user_id: str | None = None) -> dict[str, Any]:
    row = {"name": name, "niche": niche, "status": "draft"}
    if user_id: row["user_id"] = user_id
    return client().table("campaigns").insert(row).execute().data[0]


def add_content(campaign_id: str, platform: str, content_type: str, title: str = "", body: str = "", scheduled_at: str | None = None) -> dict[str, Any]:
    row = {"campaign_id": campaign_id, "platform": platform, "content_type": content_type, "title": title, "body": body, "status": "draft"}
    if scheduled_at: row["scheduled_at"] = scheduled_at
    return client().table("content_items").insert(row).execute().data[0]


def list_campaigns(user_id: str | None = None) -> list[dict[str, Any]]:
    q = client().table("campaigns").select("*").order("created_at", desc=True)
    if user_id: q = q.eq("user_id", user_id)
    return q.execute().data


def record_metric(content_id: str, platform: str, event_type: str, metrics: dict[str, Any]) -> dict[str, Any]:
    return client().table("analytics_events").insert({"content_id": content_id, "platform": platform, "event_type": event_type, "metrics": metrics}).execute().data[0]
