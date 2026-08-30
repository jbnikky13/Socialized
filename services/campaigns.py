"""High-level campaign persistence workflow."""
from __future__ import annotations
from services.db import create_campaign, add_content, list_campaigns


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
