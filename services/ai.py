from __future__ import annotations
import json
import os
import re
import requests

SYSTEM = """You are a YouTube and X content strategist. Create original, useful, platform-compliant content. Never invent sources or facts when source material is supplied. Return valid JSON only. Do not use markdown fences. Do not add trailing commas."""


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini returned invalid JSON: {exc}. Response: {cleaned[:800]}") from exc


def _gemini_key() -> str:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        try:
            import streamlit as st
            key = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
        except Exception:
            pass
    return key


def _gemini(prompt: str) -> dict:
    key = _gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    try:
        import streamlit as st
        model = str(st.secrets.get("GEMINI_MODEL", model))
    except Exception:
        pass
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {"systemInstruction": {"parts": [{"text": SYSTEM}]}, "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}}
    r = requests.post(url, headers={"x-goog-api-key": key, "Content-Type": "application/json"}, json=payload, timeout=90)
    if not r.ok:
        try: detail = r.json().get("error", {}).get("message", r.text)
        except Exception: detail = r.text
        raise RuntimeError(f"Gemini API error ({r.status_code}): {detail}")
    data = r.json(); candidates = data.get("candidates", [])
    if not candidates: raise RuntimeError("Gemini returned no candidates. Check the model, API key, and safety response.")
    text = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", [])).strip()
    if not text: raise RuntimeError("Gemini returned an empty response.")
    return _parse_json(text)


def generate_package(topic: str, niche: str, format_name: str = "long-form", source_context: str = ""):
    prompt = f"""
Create a YouTube + X content package.
Niche: {niche}
Format: {format_name}
Topic: {topic}
Research context: {source_context[:6000]}

Return JSON with exactly these keys:
idea, title_options, hook, script, description, tags, thumbnail_text, chapters, x_posts, shorts
Rules: title_options is an array of 5 strings; tags is an array of 10-15 strings; chapters is an array of objects with time and title; x_posts is an array of 3 posts <=280 characters; shorts is an array of 3 short-form scripts; script should be original and suitable for narration; do not state uncertain claims as facts; no trailing commas.
"""
    return _gemini(prompt)
