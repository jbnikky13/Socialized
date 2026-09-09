from __future__ import annotations
import math, os, shutil, subprocess, tempfile, wave
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WORLD_TEMPLATES = {
    "Medieval Tavern": {"visual": "a cozy medieval tavern with a roaring hearth, rain outside leaded windows, wooden tables, candles and warm cinematic atmosphere", "layers": ["rain", "fireplace", "room_tone"]},
    "Ancient Library": {"visual": "an ancient fantasy library at night, towering bookshelves, candles, stained glass, fireplace and rain beyond the windows", "layers": ["rain", "fireplace", "room_tone"]},
    "Wizard Tower": {"visual": "a secluded wizard study in a stone tower, glowing fireplace, books, astronomical instruments, storm outside", "layers": ["rain", "fireplace", "wind"]},
    "Forest Cottage": {"visual": "a cozy forest cottage at night, warm fireplace, mossy trees, lanterns, mist and gentle rain", "layers": ["rain", "fireplace", "forest"]},
    "Gothic Castle": {"visual": "a vast gothic castle hall lit by candles and a stone fireplace, rain and distant thunder beyond arched windows", "layers": ["rain", "fireplace", "thunder"]},
    "Elven Grove": {"visual": "an enchanted moonlit elven grove with ancient trees, glowing plants, a quiet stream and soft mist", "layers": ["forest", "water", "soft_tone"]},
}


def template_prompt(world: str, weather: str = "rain", mood: str = "cozy") -> str:
    base = WORLD_TEMPLATES.get(world, WORLD_TEMPLATES["Medieval Tavern"])["visual"]
    return f"{base}. Weather: {weather}. Mood: {mood}. Original fantasy environment, cinematic wide composition, highly detailed, atmospheric lighting, no text, no logos, no copyrighted characters."


def _noise(seconds: int, rate: int = 22050, amp: float = 0.10):
    n = max(1, int(seconds * rate))
    import random
    return [int((random.random() * 2 - 1) * 32767 * amp) for _ in range(n)]


def _tone(seconds: int, freq: float, amp: float = 0.03, rate: int = 22050):
    n = max(1, int(seconds * rate))
    return [int(math.sin(2 * math.pi * freq * i / rate) * 32767 * amp) for i in range(n)]


def generate_ambient_audio(out_path: str, duration_hours: float = 1.0, layers: list[str] | None = None) -> str:
    """Create an original low-level ambience bed. It intentionally avoids third-party recordings."""
    duration_hours = max(0.01, min(float(duration_hours), 10.0))
    seconds = int(duration_hours * 3600)
    rate = 22050
    layers = layers or ["rain", "fireplace", "room_tone"]
    # Generate in chunks so long videos do not require the entire PCM buffer in memory.
    chunk = 10
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
        for start in range(0, seconds, chunk):
            size = min(chunk, seconds - start)
            data = [0] * int(size * rate)
            if "rain" in layers:
                r = _noise(size, rate, 0.035)
                data = [a + b for a, b in zip(data, r)]
            if "fireplace" in layers:
                r = _noise(size, rate, 0.018)
                data = [a + b for a, b in zip(data, r)]
            if "wind" in layers:
                r = _noise(size, rate, 0.012)
                data = [a + b for a, b in zip(data, r)]
            if "water" in layers:
                r = _noise(size, rate, 0.015)
                data = [a + b for a, b in zip(data, r)]
            if "forest" in layers or "room_tone" in layers or "soft_tone" in layers:
                r = _tone(size, 110, 0.008, rate)
                data = [a + b for a, b in zip(data, r)]
            import struct
            wf.writeframes(struct.pack("<" + "h" * len(data), *[max(-32768, min(32767, x)) for x in data]))
    return out_path


def make_ambient_thumbnail(title: str, background_path: str, out_path: str) -> str:
    img = Image.open(background_path).convert("RGB").resize((1280, 720))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle((0, 0, 1280, 720), fill=(0, 0, 0, 80))
    try: font = ImageFont.truetype("DejaVuSans-Bold.ttf", 58)
    except Exception: font = ImageFont.load_default()
    draw.multiline_text((55, 520), title[:70], font=font, fill=(255,255,255,255), spacing=8)
    img.save(out_path, quality=94)
    return out_path


def render_ambient_video(image_path: str, audio_path: str, out_path: str, duration_hours: float) -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required to render ambient videos.")
    duration = max(1, int(float(duration_hours) * 3600))
    cmd = [ffmpeg, "-y", "-loop", "1", "-i", image_path, "-i", audio_path, "-t", str(duration), "-vf", "scale=1280:720,zoompan=z='min(zoom+0.00008,1.12)':d=1:s=1280x720:fps=30", "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return out_path
