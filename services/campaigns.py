"""High-level campaign persistence and reuse workflow."""
from __future__ import annotations
from services.db import create_campaign, add_content, list_campaigns, client


def save_campaign(name: str, niche: str, pack: dict, user_id: str | None = None) -> dict:
    campaign = create_campaign(name, niche, user_id)
    campaign_id = campaign["id"]
    title = pack.get("title") or pack.get("idea") or name
    body = pack.get("script") or pack.get("description") or ""
    add_content(campaign_id, "youtube", "video", title, body)
    for post in pack.get("x_posts", []):
        add_content(campaign_id, "x", "post", title, post)
    for short in pack.get("shorts", []):
        add_content(campaign_id, "youtube", "short", title, short)
    return campaign


def recent_campaigns(user_id: str | None = None) -> list[dict]:
    return list_campaigns(user_id)


def get_campaign(campaign_id: str) -> dict:
    rows = client().table("campaigns").select("*").eq("id", campaign_id).limit(1).execute().data
    if not rows: raise ValueError("Campaign not found")
    return rows[0]


def get_campaign_content(campaign_id: str) -> list[dict]:
    return client().table("content_items").select("*").eq("campaign_id", campaign_id).order("created_at").execute().data


def reuse_campaign(campaign_id: str) -> dict:
    """Load a saved campaign and all its content so it can be edited, regenerated or republished."""
    return {"campaign": get_campaign(campaign_id), "content": get_campaign_content(campaign_id)}
