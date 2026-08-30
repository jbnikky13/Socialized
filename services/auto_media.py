from __future__ import annotations
import os, subprocess, tempfile
from pathlib import Path
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
from services.media import upload_asset


def make_voiceover(text: str, out_path: str) -> str:
    gTTS(text=text[:5000], lang=os.getenv("TTS_LANGUAGE", "en"), slow=False).save(out_path)
    return out_path


def make_thumbnail(title: str, out_path: str) -> str:
    img = Image.new("RGB", (1280, 720), "#111827")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 64)
    except Exception:
        font = ImageFont.load_default()
    draw.multiline_text((70, 260), title[:90], font=font, fill="white", spacing=15)
    img.save(out_path, quality=92)
    return out_path


def make_video(voice_path: str, out_path: str, thumbnail_path: str) -> str:
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", thumbnail_path, "-i", voice_path,
           "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "128k",
           "-pix_fmt", "yuv420p", "-shortest", "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out_path


def build_campaign_media(campaign: dict) -> dict:
    """Generate voiceover, thumbnail and MP4, then store all assets in Supabase."""
    campaign_id = str(campaign["id"])
    title = campaign.get("name") or campaign.get("title") or "Socialized Video"
    payload = campaign.get("payload") or {}
    script = payload.get("script") or campaign.get("script") or ""
    if not script.strip():
        raise ValueError("Campaign has no YouTube script. Generate and save the campaign first.")

    work = Path(tempfile.mkdtemp(prefix="socialized_"))
    voice = make_voiceover(script, str(work / "voiceover.mp3"))
    thumb = make_thumbnail(title, str(work / "thumbnail.jpg"))
    video = make_video(voice, str(work / "video.mp4"), thumb)

    assets = {
        "voiceover_asset": upload_asset(voice, campaign_id, asset_type="voiceover"),
        "thumbnail_asset": upload_asset(thumb, campaign_id, asset_type="thumbnail"),
        "video_asset": upload_asset(video, campaign_id, asset_type="video"),
    }
    return assets
