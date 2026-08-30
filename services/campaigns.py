"""Campaign persistence and reusable campaign helpers."""
from __future__ import annotations
from typing import Any
from services.db import client


def save_campaign(name: str, niche: str, pack: dict, user_id: str | None = None) -> dict[str, Any]:
    row = {"name": name, "niche": niche, "status": "draft"}
    if user_id:
        row["user_id"] = user_id
    campaign = client().table("campaigns").insert(row).execute().data[0]
    campaign_id = campaign["id"]
    title = pack.get("title") or pack.get("idea") or name
    body = pack.get("script") or pack.get("description") or ""
    client().table("content_items").insert({"campaign_id": campaign_id, "platform": "youtube", "content_type": "video", "title": title, "body": body, "status": "draft"}).execute()
    for post in pack.get("x_posts", []):
        client().table("content_items").insert({"campaign_id": campaign_id, "platform": "x", "content_type": "post", "title": title, "body": post, "status": "draft"}).execute()
    for short in pack.get("shorts", []):
        client().table("content_items").insert({"campaign_id": campaign_id, "platform": "youtube", "content_type": "short", "title": title, "body": short, "status": "draft"}).execute()
    return campaign


def recent_campaigns(user_id: str | None = None) -> list[dict[str, Any]]:
    q = client().table("campaigns").select("*").order("created_at", desc=True)
    if user_id:
        q = q.eq("user_id", user_id)
    return q.execute().data


def get_campaign(campaign_id: str) -> dict[str, Any]:
    rows = client().table("campaigns").select("*").eq("id", campaign_id).limit(1).execute().data
    if not rows:
        raise ValueError("Campaign not found")
    return rows[0]


def get_campaign_content(campaign_id: str) -> list[dict[str, Any]]:
    return client().table("content_items").select("*").eq("campaign_id", campaign_id).order("created_at").execute().data


def reuse_campaign(campaign_id: str) -> dict[str, Any]:
    return {"campaign": get_campaign(campaign_id), "content": get_campaign_content(campaign_id)}
