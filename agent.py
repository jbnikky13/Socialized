"""CLI entry point for Socialized's research-to-content agent."""
from __future__ import annotations
import os
from services.content_agent import find_opportunities, create_content_pack
from services.analytics import read_events
from services.strategy import recommend_next_content


def run() -> None:
    niche = os.getenv("CHANNEL_NICHE", "Technology")
    opportunities = find_opportunities(niche, niche, limit=10)
    print("Top opportunities:")
    for i, item in enumerate(opportunities[:5], 1):
        print(f"{i}. [{item.score}] {item.title} ({item.source})")
    if opportunities:
        top = opportunities[0]
        pack = create_content_pack(top.title, niche, os.getenv("YOUTUBE_FORMAT", "long-form"), top.summary)
        print("Generated package:", pack.get("idea", top.title))
    print("Strategy:", recommend_next_content(read_events(), niche))


if __name__ == "__main__":
    run()
