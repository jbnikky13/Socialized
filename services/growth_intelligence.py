from __future__ import annotations
import os, re
from typing import Any
from urllib.parse import quote
import feedparser
import requests

TRENDS_RSS = "https://trends.google.com/trending/rss?geo={geo}"
YOUTUBE_SEARCH = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"


def _secret(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    if value:
        return value
    try:
        import streamlit as st
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return default


def google_trends(geo: str = "NG", limit: int = 20) -> list[dict[str, Any]]:
    """Read Google's public Trending Now RSS feed. This is discovery data, not a search-volume API."""
    url = TRENDS_RSS.format(geo=quote(geo.upper()))
    try:
        feed = feedparser.parse(url)
    except Exception as exc:
        raise RuntimeError(f"Google Trends request failed: {exc}") from exc
    results = []
    for entry in feed.entries[: max(1, min(limit, 50))]:
        title = entry.get("title", "").strip()
        if title:
            results.append({"query": title, "published": entry.get("published", ""), "source": "Google Trends"})
    return results


def youtube_opportunity(query: str, region: str = "NG", limit: int = 10) -> dict[str, Any]:
    """Estimate YouTube opportunity from public search results. Requires YOUTUBE_API_KEY."""
    key = _secret("YOUTUBE_API_KEY")
    if not key:
        return {"query": query, "available": False, "reason": "YOUTUBE_API_KEY not configured"}
    params = {"part": "snippet", "q": query, "type": "video", "maxResults": max(1, min(limit, 25)), "regionCode": region.upper(), "key": key}
    try:
        r = requests.get(YOUTUBE_SEARCH, params=params, timeout=30)
        r.raise_for_status()
        items = r.json().get("items", [])
    except requests.RequestException as exc:
        return {"query": query, "available": False, "reason": str(exc)}
    ids = [x.get("id", {}).get("videoId") for x in items if x.get("id", {}).get("videoId")]
    stats = {}
    if ids:
        try:
            r = requests.get(YOUTUBE_VIDEOS, params={"part": "statistics,snippet", "id": ",".join(ids), "key": key}, timeout=30)
            r.raise_for_status()
            stats = {x["id"]: x for x in r.json().get("items", [])}
        except requests.RequestException:
            stats = {}
    rows = []
    for item in items:
        vid = item.get("id", {}).get("videoId", "")
        data = stats.get(vid, {})
        s = data.get("statistics", {})
        rows.append({"title": item.get("snippet", {}).get("title", ""), "channel": item.get("snippet", {}).get("channelTitle", ""), "views": int(s.get("viewCount", 0) or 0), "video_id": vid})
    views = sorted([x["views"] for x in rows], reverse=True)
    median = views[len(views)//2] if views else 0
    return {"query": query, "available": True, "results": rows, "median_views": median, "max_views": max(views, default=0)}


def score_opportunity(trend_score: float, youtube_score: float, monetization: float, competition: float, freshness: float) -> float:
    """0-100 opportunity score. Competition is entered as 0-100 where higher means harder."""
    value = (trend_score * 0.30) + (youtube_score * 0.25) + (monetization * 0.20) + (freshness * 0.15) + ((100 - competition) * 0.10)
    return round(max(0, min(100, value)), 1)


def headline_score(title: str) -> float:
    """Local heuristic inspired by creator headline best practices; not an AMI score."""
    text = re.sub(r"\s+", " ", title.strip())
    if not text:
        return 0.0
    score = 35.0
    if 45 <= len(text) <= 75: score += 18
    elif 35 <= len(text) <= 90: score += 10
    if any(c.isdigit() for c in text): score += 7
    if "?" in text or ":" in text: score += 5
    if any(w in text.lower().split() for w in ["why", "how", "best", "secret", "mistake", "truth", "before", "after", "explained"]): score += 12
    if any(w in text.lower() for w in ["you", "your"]): score += 5
    if text.count("!") <= 1: score += 4
    if len(text) > 100: score -= 12
    return round(max(0, min(100, score)), 1)
