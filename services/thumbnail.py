"""Free local thumbnail generator; no image API key required."""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def generate_thumbnail(prompt: str, output_path: str) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1280, 720), "#111827")
    draw = ImageDraw.Draw(image)
    text = prompt.strip()[:120] or "NEW VIDEO"
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 64)
    except OSError:
        font = ImageFont.load_default()
    box = draw.multiline_textbbox((0, 0), text, font=font, spacing=12)
    x = (1280 - (box[2] - box[0])) / 2
    y = (720 - (box[3] - box[1])) / 2
    draw.multiline_text((x, y), text, font=font, fill="white", align="center", spacing=12)
    image.save(output_path, "JPEG", quality=92)
    return output_path
