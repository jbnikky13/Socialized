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
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7,
        },
    }
    # Google documents x-goog-api-key as the supported API-key header.
    r = requests.post(
        url,
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json=payload,
        timeout=90,
    )
    if not r.ok:
        try:
            detail = r.json().get("error", {}).get("message", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"Gemini API error ({r.status_code}): {detail}")
    data = r.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates. Check the model, API key, and safety response.")
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini returned non-JSON output: {text[:500]}") from exc


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
