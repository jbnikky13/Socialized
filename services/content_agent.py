"""Unified content-agent orchestration for X and YouTube."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.ai import generate_package
from services.research import research_topics


@dataclass
class Opportunity:
    title: str
    source: str
    url: str
    summary: str
    score: float


def score_topic(item: dict[str, Any], niche: str) -> float:
    """Simple transparent opportunity score; AI can refine it later."""
    text = f"{item.get('title','')} {item.get('summary','')}".lower()
    niche_words = [w for w in niche.lower().split() if len(w) > 2]
    relevance = sum(w in text for w in niche_words)
    freshness = 1.0 if item.get("url") else 0.5
    return round(min(10.0, 3.0 + relevance * 1.5 + freshness * 2.0), 1)


def find_opportunities(query: str, niche: str, limit: int = 10) -> list[Opportunity]:
    results = research_topics(query, limit)
    scored = []
    for item in results:
        scored.append(Opportunity(
            title=item.get("title", ""),
            source=item.get("source", "RSS"),
            url=item.get("url", ""),
            summary=item.get("summary", ""),
            score=score_topic(item, niche),
        ))
    return sorted(scored, key=lambda x: x.score, reverse=True)


def create_content_pack(topic: str, niche: str, format_name: str, context: str = "") -> dict[str, Any]:
    """Generate the platform-neutral pack used by both publishers."""
    package = generate_package(topic, niche, format_name, context)
    package.setdefault("x_posts", [])
    package.setdefault("shorts", [])
    package.setdefault("thumbnail_text", "")
    return package
