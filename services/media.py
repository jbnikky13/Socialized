"""Media validation and Supabase Storage helpers."""
from __future__ import annotations
import mimetypes
import os
from pathlib import Path
from services.db import client

BUCKET = "media-assets"


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


def upload_asset(path: str, campaign_id: str, content_id: str | None = None, asset_type: str = "video") -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Media file not found: {p}")
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    storage_path = f"campaigns/{campaign_id}/{asset_type}/{p.name}"
    sb = client()
    with p.open("rb") as fh:
        sb.storage.from_(BUCKET).upload(
            storage_path,
            fh,
            file_options={"content-type": mime, "upsert": "true"},
        )
    public_url = sb.storage.from_(BUCKET).get_public_url(storage_path)
    return sb.table("media_assets").insert({
        "campaign_id": campaign_id,
        "content_id": content_id,
        "asset_type": asset_type,
        "storage_path": storage_path,
        "public_url": public_url,
        "mime_type": mime,
    }).execute().data[0]


def upload_streamlit_file(uploaded_file, campaign_id: str, asset_type: str = "video") -> dict:
    """Save an UploadedFile temporarily and push it to Supabase Storage."""
    suffix = Path(uploaded_file.name).suffix or ".bin"
    temp_path = Path("/tmp") / f"socialized_{campaign_id}_{asset_type}{suffix}"
    temp_path.write_bytes(uploaded_file.getbuffer())
    try:
        return upload_asset(str(temp_path), campaign_id=campaign_id, asset_type=asset_type)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
