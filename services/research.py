from __future__ import annotations
import feedparser
from urllib.parse import quote

DEFAULT_FEEDS = [
    "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en",
    "https://www.reddit.com/search.rss?q={query}&sort=new",
]


def research_topics(query: str, limit: int = 12):
    results = []
    for template in DEFAULT_FEEDS:
        try:
            url = template.format(query=quote(query))
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit]:
                results.append({
                    "title": entry.get("title", "").strip(),
                    "url": entry.get("link", ""),
                    "summary": entry.get("summary", "")[:500],
                    "source": feed.feed.get("title", "RSS")
                })
        except Exception:
            continue
    # De-duplicate by title while keeping source order.
    seen, unique = set(), []
    for item in results:
        key = item["title"].lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:limit]
