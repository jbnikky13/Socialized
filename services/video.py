"""Simple FFmpeg video assembly from a narration track and optional image."""
from __future__ import annotations
import os
import subprocess


def assemble_video(audio_path: str, output_path: str, image_path: str | None = None) -> str:
    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path)
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    if image_path and os.path.exists(image_path):
        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", image_path, "-i", audio_path,
               "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac", "-b:a", "192k",
               "-pix_fmt", "yuv420p", "-shortest", output_path]
    else:
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30",
               "-i", audio_path, "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
               "-shortest", output_path]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return output_path
