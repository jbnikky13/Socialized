"""Thumbnail generation adapter using OpenAI image generation."""
from __future__ import annotations
import os
from pathlib import Path
import base64
from openai import OpenAI


def generate_thumbnail(prompt: str, output_path: str) -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    client = OpenAI(api_key=key)
    result = client.images.generate(model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"), prompt=prompt, size="1536x1024")
    data = getattr(result.data[0], "b64_json", None)
    if not data:
        raise RuntimeError("Image provider did not return image data")
    Path(output_path).write_bytes(base64.b64decode(data))
    return output_path
