"""Text-to-speech adapter. Uses OpenAI Audio when configured."""
from __future__ import annotations
import os
from pathlib import Path
from openai import OpenAI


def synthesize(text: str, output_path: str, voice: str = "alloy") -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    if not text.strip():
        raise ValueError("Narration text is empty")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=key)
    with client.audio.speech.with_streaming_response.create(
        model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
        voice=voice,
        input=text,
        response_format="mp3",
    ) as response:
        response.stream_to_file(output_path)
    return output_path
