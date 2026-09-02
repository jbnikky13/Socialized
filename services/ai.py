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
        try:
            detail = r.json().get("error", {}).get("message", r.text)
        except Exception:
            detail = r.text
        raise RuntimeError(f"Gemini API error ({r.status_code}): {detail}")
    data = r.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates. Check the model, API key, and safety response.")
    text = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", [])).strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response.")
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


def generate_campaign_visual_prompts(
    title: str,
    script: str,
    niche: str,
    count: int = 3,
    style: str = "photorealistic cinematic",
) -> list[str]:
    """Create campaign-specific image prompts from the saved campaign story."""
    count = max(1, min(int(count), 4))
    prompt = f"""
Create {count} distinct visual prompts for a social-media/YouTube campaign.

Campaign title: {title}
Niche: {niche}
Story/script:
{script[:9000]}

Visual style: {style}

Return JSON with exactly one key: prompts.
prompts must be an array of exactly {count} detailed English image-generation prompts.

Each image must clearly relate to the campaign story and depict a different moment, subject,
setting, or visual angle. Make the images useful as campaign artwork, thumbnails, story frames,
or promotional posts. Describe subject, environment, lighting, camera framing, mood, and important
visual continuity. Prefer photorealistic live-action imagery unless another style was explicitly requested.
Do not add logos, watermarks, captions, UI, or embedded text. Do not reference copyrighted characters.
"""
    result = _gemini(prompt)
    prompts = result.get("prompts", [])
    if not isinstance(prompts, list) or len(prompts) < count:
        raise RuntimeError("Gemini did not return enough campaign image prompts.")
    return [str(p).strip() for p in prompts[:count] if str(p).strip()]


def _pollinations_key() -> str:
    key = os.getenv("POLLINATIONS_API_KEY", "").strip()
    if not key:
        try:
            import streamlit as st
            key = str(st.secrets.get("POLLINATIONS_API_KEY", "")).strip()
        except Exception:
            pass
    return key


def generate_campaign_image(prompt: str, aspect_ratio: str = "16:9") -> bytes:
    """Generate a campaign image through Pollinations and return the image bytes."""
    key = _pollinations_key()
    if not key:
        raise RuntimeError("POLLINATIONS_API_KEY is not configured. Add your Pollinations API key to Streamlit Secrets.")

    model = os.getenv("POLLINATIONS_IMAGE_MODEL", "flux").strip() or "flux"
    try:
        import streamlit as st
        model = str(st.secrets.get("POLLINATIONS_IMAGE_MODEL", model)).strip() or "flux"
    except Exception:
        pass

    ratio_note = {
        "16:9": "wide 16:9 landscape composition",
        "9:16": "vertical 9:16 portrait composition",
        "1:1": "square 1:1 composition",
    }.get(aspect_ratio, f"{aspect_ratio} composition")
    final_prompt = f"{prompt}. Compose the image as a {ratio_note}."

    try:
        response = requests.get(
            "https://gen.pollinations.ai/image/" + requests.utils.quote(final_prompt, safe=""),
            params={"model": model},
            headers={"Authorization": f"Bearer {key}", "Accept": "image/*"},
            timeout=180,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Pollinations image request failed: {exc}") from exc

    if not response.ok:
        detail = response.text[:500]
        raise RuntimeError(f"Pollinations image API error ({response.status_code}): {detail}")
    if not response.content or not response.headers.get("content-type", "").lower().startswith("image/"):
        raise RuntimeError("Pollinations returned an unexpected response instead of an image.")
    return response.content
