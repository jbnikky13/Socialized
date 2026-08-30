"""X (Twitter) publishing service for Socialized.

Uses the official X API v2. Credentials are supplied through environment
variables; no secrets are stored in the repository.
"""
from __future__ import annotations

import os
from typing import Optional

import requests


class XService:
    """Minimal X API v2 client for posting text and media-ready workflows."""

    BASE_URL = "https://api.x.com/2"

    def __init__(self, bearer_token: Optional[str] = None, access_token: Optional[str] = None):
        self.bearer_token = bearer_token or os.getenv("X_BEARER_TOKEN")
        self.access_token = access_token or os.getenv("X_ACCESS_TOKEN")

    def configured(self) -> bool:
        return bool(self.access_token)

    def create_post(self, text: str, reply_to: Optional[str] = None) -> dict:
        if not self.access_token:
            raise RuntimeError("X_ACCESS_TOKEN is not configured")
        if not text or len(text) > 280:
            raise ValueError("X post must contain 1-280 characters")
        payload = {"text": text}
        if reply_to:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to}
        response = requests.post(
            f"{self.BASE_URL}/tweets",
            json=payload,
            headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def create_thread(self, posts: list[str]) -> list[dict]:
        results = []
        previous_id = None
        for post in posts:
            result = self.create_post(post, reply_to=previous_id)
            results.append(result)
            previous_id = result.get("data", {}).get("id")
        return results
