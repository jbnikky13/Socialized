from __future__ import annotations

import base64, os, time
from pathlib import Path
import requests


def _secret(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value: return value
    try:
        import streamlit as st
        return str(st.secrets.get(name, default)).strip()
    except Exception: return default


def estimate(provider: str, seconds: int, resolution: str = "768P") -> float:
    rates = {
        "MiniMax H3": 0.13 if resolution == "2K" else 0.08,
        "Kling 2.5 Turbo": 0.042 if resolution != "2K" else 0.084,
        "Wan 2.1": 0.40 if resolution != "480P" else 0.20,
    }
    return round(max(0, seconds) * rates.get(provider, 0.08), 2)


def available(provider: str) -> bool:
    return bool({
        "MiniMax H3": _secret("MINIMAX_API_KEY"),
        "Kling 2.5 Turbo": _secret("KLING_API_KEY"),
        "Wan 2.1": _secret("FAL_KEY"),
    }.get(provider, ""))


def _kling_create(prompt: str, image_url: str | None, duration: int, mode: str = "720p") -> str:
    key = _secret("KLING_API_KEY")
    base = _secret("KLING_API_BASE", "https://api.klingai.com").rstrip("/")
    if not key: raise ValueError("KLING_API_KEY is not configured.")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model_name": "kling-v2.5-turbo", "prompt": prompt, "duration": str(duration), "mode": mode}
    if image_url: payload["image"] = image_url
    r = requests.post(f"{base}/v1/videos/image2video" if image_url else f"{base}/v1/videos/text2video", headers=headers, json=payload, timeout=90)
    if r.status_code >= 400: raise RuntimeError(f"Kling create task failed ({r.status_code}): {r.text}")
    task_id = r.json().get("data", {}).get("task_id")
    if not task_id: raise RuntimeError(f"Kling did not return task_id: {r.text}")
    return task_id


def _kling_wait(task_id: str, timeout: int = 900) -> str:
    key = _secret("KLING_API_KEY"); base = _secret("KLING_API_BASE", "https://api.klingai.com").rstrip("/")
    headers = {"Authorization": f"Bearer {key}"}; started = time.time()
    while time.time() - started < timeout:
        r = requests.get(f"{base}/v1/videos/image2video/{task_id}", headers=headers, timeout=60)
        if r.status_code >= 400: raise RuntimeError(f"Kling query failed ({r.status_code}): {r.text}")
        data = r.json().get("data", {}); status = str(data.get("task_status", "")).lower()
        if status == "succeed":
            url = (data.get("task_result", {}).get("videos") or [{}])[0].get("url")
            if not url: raise RuntimeError("Kling completed without a video URL.")
            return url
        if status in {"failed", "cancelled"}: raise RuntimeError(f"Kling task failed: {data}")
        time.sleep(8)
    raise TimeoutError(f"Kling task timed out: {task_id}")


def _fal_wan(prompt: str, image_url: str | None, duration: int) -> str:
    key = _secret("FAL_KEY")
    if not key: raise ValueError("FAL_KEY is not configured.")
    # Uses fal.ai's queue endpoint for Wan image-to-video. The model slug can be changed by env without changing the UI.
    model = _secret("FAL_WAN_MODEL", "fal-ai/wan-i2v")
    payload = {"prompt": prompt}
    if image_url: payload["image_url"] = image_url
    r = requests.post(f"https://queue.fal.run/{model}", headers={"Authorization": f"Key {key}", "Content-Type": "application/json"}, json=payload, timeout=90)
    if r.status_code >= 400: raise RuntimeError(f"Wan/fal.ai request failed ({r.status_code}): {r.text}")
    data = r.json(); request_id = data.get("request_id")
    if not request_id: raise RuntimeError(f"fal.ai did not return request_id: {data}")
    status_url = data.get("status_url") or f"https://queue.fal.run/{model}/requests/{request_id}/status"
    result_url = data.get("response_url") or f"https://queue.fal.run/{model}/requests/{request_id}"
    started = time.time()
    while time.time() - started < 900:
        s = requests.get(status_url, headers={"Authorization": f"Key {key}"}, timeout=60).json()
        if str(s.get("status", "")).upper() == "COMPLETED":
            result = requests.get(result_url, headers={"Authorization": f"Key {key}"}, timeout=60).json()
            videos = result.get("video") or result.get("videos") or []
            if isinstance(videos, dict): videos = [videos]
            url = (videos[0] if videos else {}).get("url")
            if url: return url
            raise RuntimeError(f"fal.ai completed without a video URL: {result}")
        if str(s.get("status", "")).upper() in {"FAILED", "CANCELLED"}: raise RuntimeError(f"fal.ai task failed: {s}")
        time.sleep(5)
    raise TimeoutError(f"fal.ai task timed out: {request_id}")


def create_and_wait(provider: str, prompt: str, references: list[str], duration: int, resolution: str = "768P") -> str:
    if provider == "MiniMax H3":
        from services.minimax_h3 import create_task, wait_for_task
        task = create_task(prompt, references, duration, resolution, "16:9")
        return wait_for_task(task)
    if provider == "Kling 2.5 Turbo":
        image = references[0] if references else None
        mode = "720p" if resolution != "2K" else "1080p"
        task = _kling_create(prompt, image, duration, mode)
        return _kling_wait(task)
    if provider == "Wan 2.1":
        return _fal_wan(prompt, references[0] if references else None, duration)
    raise ValueError(f"Unknown video provider: {provider}")
