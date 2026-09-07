from __future__ import annotations

import json
import re
from typing import Any

from services.ai import _gemini


SYSTEM_PROMPT = """You are a cinematic microdrama showrunner. Create original fictional romance stories for short-form video. Keep characters visually consistent and make every scene directly filmable. Return valid JSON only."""


def _clean_json(value: str) -> dict[str, Any]:
    value = re.sub(r"^```(?:json)?\s*", "", value.strip(), flags=re.I)
    value = re.sub(r"\s*```$", "", value)
    return json.loads(value)


def generate_love_microdrama(premise: str, duration_seconds: int = 60, scene_count: int = 8) -> dict[str, Any]:
    prompt = f"""
Create a photorealistic romantic microdrama for YouTube Shorts.
Premise: {premise}
Target duration: {duration_seconds} seconds.
Number of scenes: {scene_count}.

Return exactly these keys:
- title: short compelling title
- logline: one sentence
- characters: array of objects with name, age, appearance, personality, wardrobe
- continuity_bible: concise rules for preserving faces, hair, wardrobe and locations
- scenes: array of exactly {scene_count} objects with scene_number, duration_seconds, setting, action, camera, dialogue, visual_prompt
- narration: complete narration if narration is needed
- youtube_hook: one sentence

Make the story emotionally strong, original and suitable for a general audience. Avoid copyrighted characters, real-person likenesses, explicit sexual content, graphic violence and hateful content. Visual prompts must describe photorealistic live-action imagery and repeat essential character appearance details for continuity.
"""
    result = _gemini(f"{SYSTEM_PROMPT}\n\n{prompt}")
    scenes = result.get("scenes") or []
    if len(scenes) != scene_count:
        raise RuntimeError(f"Story engine returned {len(scenes)} scenes; expected {scene_count}.")
    return result
