"""Content strategy and performance feedback layer."""
from __future__ import annotations
from collections import Counter
from typing import Any


def rank_topics(opportunities: list[Any]) -> list[Any]:
    return sorted(opportunities, key=lambda x: getattr(x, "score", 0), reverse=True)


def recommend_next_content(events: list[dict], niche: str) -> dict:
    """Return transparent recommendations from locally recorded performance events."""
    platform_counts = Counter(e.get("platform", "unknown") for e in events)
    event_counts = Counter(e.get("event", "unknown") for e in events)
    recommendations = []
    if event_counts.get("published", 0) == 0:
        recommendations.append("Publish a small approved batch so the agent can collect baseline performance data.")
    if platform_counts.get("x", 0) < platform_counts.get("youtube", 0):
        recommendations.append("Increase X repurposing from successful YouTube topics.")
    elif platform_counts.get("youtube", 0) < platform_counts.get("x", 0):
        recommendations.append("Turn strong X topics into YouTube explainers or Shorts.")
    else:
        recommendations.append(f"Keep testing {niche} topics across both platforms and compare engagement.")
    return {"recommendations": recommendations, "event_counts": dict(event_counts), "platform_counts": dict(platform_counts)}
