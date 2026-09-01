from __future__ import annotations

import base64
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import requests

BASE_URL = os.getenv("MINIMAX_API_BASE", "https://api.minimax.io").rstrip("/")
CREATE_URL = f"{BASE_URL}/v2/video_generation"
QUERY_URL = f"{BASE_URL}/v2/query/video_generation/{{task_id}}"


def api_key() -> str:
    key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not key:
        try:
            import streamlit as st
            key = str(st.secrets.get("MINIMAX_API_KEY", "")).strip()
        except Exception:
            pass
    return key


def image_data_url(uploaded_file) -> str:
    raw = uploaded_file.getvalue()
    mime = getattr(uploaded_file, "type", None) or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _headers(key: str) -> dict[str, str]:
    if not key:
        raise ValueError("MINIMAX_API_KEY is not configured.")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def create_task(prompt: str, references: list[str] | None = None, duration: int = 5,
                resolution: str = "768P", ratio: str = "16:9") -> str:
    if duration < 4 or duration > 15:
        raise ValueError("MiniMax H3 duration must be between 4 and 15 seconds.")
    content = [{"type": "text", "text": prompt}]
    for ref in references or []:
        if ref:
            content.append({"type": "image_url", "image_url": {"url": ref}, "role": "reference_image"})
    payload = {
        "model": "MiniMax-H3",
        "content": content,
        "resolution": resolution,
        "duration": int(duration),
        "ratio": ratio,
    }
    response = requests.post(CREATE_URL, headers=_headers(api_key()), json=payload, timeout=90)
    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise RuntimeError(f"MiniMax create task failed ({response.status_code}): {detail}")
    task_id = response.json().get("task_id")
    if not task_id:
        raise RuntimeError(f"MiniMax did not return task_id: {response.text}")
    return str(task_id)


def wait_for_task(task_id: str, timeout: int = 900, poll_seconds: int = 8, callback=None) -> str:
    started = time.time()
    last = None
    while time.time() - started < timeout:
        response = requests.get(QUERY_URL.format(task_id=task_id), headers=_headers(api_key()), timeout=60)
        if response.status_code >= 400:
            raise RuntimeError(f"MiniMax query failed ({response.status_code}): {response.text}")
        data = response.json()
        task = data.get("task", data)
        status = str(task.get("status", "unknown")).lower()
        if callback and status != last:
            callback(status, task)
            last = status
        if status in {"success", "succeeded"}:
            url = (task.get("content") or {}).get("url") or task.get("video_url")
            if not url:
                raise RuntimeError(f"MiniMax succeeded without a video URL: {task}")
            return url
        if status in {"failed", "failure", "cancelled", "canceled"}:
            raise RuntimeError(f"MiniMax task failed: {task}")
        time.sleep(poll_seconds)
    raise TimeoutError(f"MiniMax task {task_id} timed out after {timeout} seconds.")


def download(url: str, destination: str | Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=180) as response:
        response.raise_for_status()
        with destination.open("wb") as fh:
            for chunk in response.iter_content(1024 * 1024):
                if chunk:
                    fh.write(chunk)
    return destination


def stitch(clips: list[str | Path], output: str | Path) -> Path:
    ffmpeg = shutil.which("ffmpeg") or shutil.which("avconv")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required. It is already declared in packages.txt; redeploy/reboot if unavailable.")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        concat = Path(td) / "concat.txt"
        concat.write_text("\n".join("file '" + str(Path(c).resolve()).replace("'", "'\\''") + "'" for c in clips), encoding="utf-8")
        proc = subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(output)], capture_output=True, text=True)
        if proc.returncode:
            raise RuntimeError(proc.stderr[-4000:] or "FFmpeg stitching failed")
    return output


def build_episode(scenes: list[dict], workdir: str | Path, progress=None) -> tuple[Path, list[str]]:
    key = api_key()
    if not key:
        raise ValueError("Add MINIMAX_API_KEY to Streamlit secrets before generating.")
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []
    task_ids: list[str] = []
    for index, scene in enumerate(scenes, 1):
        task_id = create_task(scene["prompt"], scene.get("references", []), scene.get("duration", 5), scene.get("resolution", "768P"), scene.get("ratio", "16:9"))
        task_ids.append(task_id)
        url = wait_for_task(task_id, callback=lambda status, task, i=index: progress(i, len(scenes), status, task) if progress else None)
        clip = workdir / f"scene_{index:02d}.mp4"
        download(url, clip)
        clips.append(clip)
    final = workdir / "microdrama_episode.mp4"
    stitch(clips, final)
    return final, task_ids
