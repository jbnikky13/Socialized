from __future__ import annotations
import os, shutil, subprocess, tempfile
from pathlib import Path
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont
from services.media import upload_asset
from services.db import client


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


def _ffmpeg_binary() -> str | None:
    """Return an available ffmpeg executable, if the deployment image provides one."""
    return shutil.which("ffmpeg") or shutil.which("avconv")


def make_video(voice_path: str, out_path: str, thumbnail_path: str) -> str:
    ffmpeg = _ffmpeg_binary()
    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg is not installed in the Streamlit deployment. "
            "Add the system package ffmpeg to the deployment (packages.txt on Streamlit Cloud), then reboot the app."
        )
    cmd = [ffmpeg, "-y", "-loop", "1", "-i", thumbnail_path, "-i", voice_path, "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p", "-shortest", "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out_path


def _load_saved_script(campaign_id: str) -> tuple[str, str]:
    rows = (client().table("content_items").select("platform,content_type,title,body").eq("campaign_id", campaign_id).order("created_at").execute().data)
    video = next((r for r in rows if r.get("platform") == "youtube" and r.get("content_type") == "video" and (r.get("body") or "").strip()), None)
    if not video:
        video = next((r for r in rows if r.get("platform") == "youtube" and (r.get("body") or "").strip()), None)
    return ((video or {}).get("title", ""), (video or {}).get("body", ""))


def build_campaign_media(campaign_or_title: dict | str, script: str | None = None) -> dict:
    """Generate media for new or reused campaigns. Reused campaigns load their script from content_items."""
    if isinstance(campaign_or_title, dict):
        campaign = campaign_or_title
        campaign_id = str(campaign["id"])
        title = campaign.get("name") or campaign.get("title") or "Socialized Video"
        payload = campaign.get("payload") or {}
        script = payload.get("script") or campaign.get("script") or ""
        if not script.strip():
            saved_title, saved_script = _load_saved_script(campaign_id)
            title = saved_title or title
            script = saved_script
    else:
        title = str(campaign_or_title)
        campaign_id = "unassigned"
        script = script or ""

    if not script.strip():
        raise ValueError("This campaign has no saved YouTube script/content. Please generate and save a campaign with a YouTube script first.")

    work = Path(tempfile.mkdtemp(prefix="socialized_"))
    voice = make_voiceover(script, str(work / "voiceover.mp3"))
    thumb = make_thumbnail(title, str(work / "thumbnail.jpg"))
    video = make_video(voice, str(work / "video.mp4"), thumb)

    if campaign_id == "unassigned":
        return {"voiceover": voice, "thumbnail": thumb, "video": video}
    return {"voiceover_asset": upload_asset(voice, campaign_id, asset_type="voiceover"), "thumbnail_asset": upload_asset(thumb, campaign_id, asset_type="thumbnail"), "video_asset": upload_asset(video, campaign_id, asset_type="video")}