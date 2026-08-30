from __future__ import annotations
import json
import os
import requests

SYSTEM = """You are a YouTube and X content strategist. Create original, useful, platform-compliant content. Never invent sources or facts when source material is supplied. Return valid JSON only."""


def _gemini(prompt: str) -> dict:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {"system_instruction": {"parts": [{"text": SYSTEM}]}, "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}}
    r = requests.post(url, params={"key": key}, json=payload, timeout=90)
    r.raise_for_status()
    data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def generate_package(topic: str, niche: str, format_name: str = "long-form", source_context: str = ""):
    prompt = f"""
Create a YouTube + X content package.
Niche: {niche}
Format: {format_name}
Topic: {topic}
Research context: {source_context[:6000]}

Return JSON with exactly these keys:
idea, title_options, hook, script, description, tags, thumbnail_text, chapters, x_posts, shorts
Rules: title_options is an array of 5 strings; tags is an array of 10-15 strings; chapters is an array of objects with time and title; x_posts is an array of 3 posts <=280 characters; shorts is an array of 3 short-form scripts; script should be original and suitable for narration; do not state uncertain claims as facts.
"""
    return _gemini(prompt)
