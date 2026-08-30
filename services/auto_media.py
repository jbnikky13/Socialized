from __future__ import annotations
import os, subprocess, tempfile
from pathlib import Path
import requests
from gtts import gTTS
from PIL import Image, ImageDraw, ImageFont


def make_voiceover(text: str, out_path: str) -> str:
    gTTS(text=text[:5000], lang=os.getenv("TTS_LANGUAGE", "en"), slow=False).save(out_path)
    return out_path


def make_thumbnail(title: str, out_path: str) -> str:
    img = Image.new("RGB", (1280, 720), "#111827")
    draw = ImageDraw.Draw(img)
    try: font = ImageFont.truetype("DejaVuSans-Bold.ttf", 64)
    except Exception: font = ImageFont.load_default()
    words = title[:90]
    draw.multiline_text((70, 260), words, font=font, fill="white", spacing=15)
    img.save(out_path, quality=92)
    return out_path


def make_video(voice_path: str, out_path: str, thumbnail_path: str) -> str:
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", thumbnail_path, "-i", voice_path, "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p", "-shortest", "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out_path


def build_campaign_media(title: str, script: str) -> dict[str, str]:
    work = Path(tempfile.mkdtemp(prefix="socialized_"))
    voice = make_voiceover(script, str(work / "voiceover.mp3"))
    thumb = make_thumbnail(title, str(work / "thumbnail.jpg"))
    video = make_video(voice, str(work / "video.mp4"), thumb)
    return {"voiceover": voice, "thumbnail": thumb, "video": video}
