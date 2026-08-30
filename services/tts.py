"""Free text-to-speech adapter using gTTS; no paid API key required."""
from __future__ import annotations
from pathlib import Path
from gtts import gTTS


def synthesize(text: str, output_path: str, voice: str = "en") -> str:
    if not text.strip():
        raise ValueError("Narration text is empty")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    gTTS(text=text, lang=voice if len(voice) <= 5 else "en", slow=False).save(output_path)
    return output_path
