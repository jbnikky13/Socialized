from __future__ import annotations
import json
import os
from openai import OpenAI

SYSTEM = """You are a YouTube content strategist. Create original, useful, platform-compliant content. Never invent sources or facts when source material is supplied. Return valid JSON only."""


def generate_package(topic: str, niche: str, format_name: str = "long-form", source_context: str = ""):
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")
    client = OpenAI(api_key=key)
    prompt = f"""
Create a YouTube content package.
Niche: {niche}
Format: {format_name}
Topic: {topic}
Research context: {source_context[:6000]}

Return JSON with exactly these keys:
idea, title_options, hook, script, description, tags, thumbnail_text, chapters
Rules: title_options is an array of 5 strings; tags is an array of 10-15 strings; chapters is an array of objects with time and title; script should be original and suitable for narration; do not state uncertain claims as facts.
"""
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return json.loads(response.choices[0].message.content)
