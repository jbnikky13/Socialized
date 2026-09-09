from __future__ import annotations
from services.ai import _gemini


def generate_ambient_concept(world: str, location: str, weather: str, use_case: str, duration: str) -> dict:
    prompt = f"""
Create an original fantasy ambient YouTube concept.
World: {world}
Location: {location}
Weather: {weather}
Use case: {use_case}
Duration: {duration}

Return JSON exactly with: title_options, description, tags, thumbnail_text, scene_prompt, audio_layers, lore.
Create 5 compelling titles. The environment must be original and must not use copyrighted characters, franchises, logos, or named fictional locations. This is an ambience video, not a narrated story. audio_layers should be an array of 5-8 practical ambience layers. thumbnail_text should be short. scene_prompt should describe one stable 16:9 environment suitable for a long loop.
"""
    return _gemini(prompt)
