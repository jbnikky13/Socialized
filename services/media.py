"""Optional local media helpers for preparing narration/video assets."""
from __future__ import annotations
import os


def validate_media(path: str, max_mb: int = 512) -> tuple[bool, str]:
    if not path:
        return False, "No media file supplied."
    if not os.path.exists(path):
        return False, "Media file does not exist."
    size_mb = os.path.getsize(path) / (1024 * 1024)
    if size_mb > max_mb:
        return False, f"Media exceeds the {max_mb} MB limit."
    return True, "Media ready."


def build_asset_manifest(script: str, thumbnail_text: str, shorts: list[str] | None = None) -> dict:
    return {
        "script_ready": bool(script.strip()),
        "thumbnail_text": thumbnail_text.strip(),
        "shorts": shorts or [],
        "voiceover": "pending",
        "video": "pending",
        "thumbnail": "pending",
    }
