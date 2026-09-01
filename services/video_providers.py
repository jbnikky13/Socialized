from __future__ import annotations
import os, time, requests


def _secret(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value: return value
    try:
        import streamlit as st
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return default


def estimate(provider: str, seconds: int, resolution: str = "768P") -> float:
    rates = {
        "MiniMax H3": 0.13 if resolution == "2K" else 0.08,
        "Kling 2.5 Turbo": 0.042 if resolution != "2K" else 0.084,
    }
    return round(max(0, seconds) * rates.get(provider, 0.08), 2)


def available(provider: str) -> bool:
    return bool({
        "MiniMax H3": _secret("MINIMAX_API_KEY"),
        "Kling 2.5 Turbo": _secret("KLING_API_KEY"),
    }.get(provider, ""))


def _kling_headers() -> dict[str, str]:
    key = _secret("KLING_API_KEY")
    if not key: raise ValueError("KLING_API_KEY is not configured.")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _kling_create(prompt: str, image_url: str | None, duration: int, mode: str) -> str:
    base = _secret("KLING_API_BASE", "https://api.klingai.com").rstrip("/")
    payload = {"model_name": "kling-v2.5-turbo", "prompt": prompt, "duration": str(duration), "mode": mode}
    if image_url: payload["image"] = image_url
    endpoint = "/v1/videos/image2video" if image_url else "/v1/videos/text2video"
    response = requests.post(base + endpoint, headers=_kling_headers(), json=payload, timeout=90)
    if response.status_code >= 400:
        if response.status_code in (402, 403):
            raise RuntimeError("KLING_BILLING_OR_AUTH: Kling rejected the request. Check API key, account permissions, and API billing/credits.")
        raise RuntimeError(f"Kling create task failed ({response.status_code}): {response.text}")
    task_id = response.json().get("data", {}).get("task_id")
    if not task_id: raise RuntimeError(f"Kling did not return task_id: {response.text}")
    return str(task_id)


def _kling_wait(task_id: str, timeout: int = 900) -> str:
    base = _secret("KLING_API_BASE", "https://api.klingai.com").rstrip("/")
    started = time.time()
    while time.time() - started < timeout:
        response = requests.get(f"{base}/v1/videos/image2video/{task_id}", headers={"Authorization": f"Bearer {_secret('KLING_API_KEY')}"}, timeout=60)
        if response.status_code >= 400: raise RuntimeError(f"Kling query failed ({response.status_code}): {response.text}")
        data = response.json().get("data", {})
        status = str(data.get("task_status", "")).lower()
        if status == "succeed":
            videos = data.get("task_result", {}).get("videos") or []
            url = videos[0].get("url") if videos else None
            if not url: raise RuntimeError("Kling completed without a video URL.")
            return url
        if status in {"failed", "cancelled", "canceled"}: raise RuntimeError(f"Kling task failed: {data}")
        time.sleep(8)
    raise TimeoutError(f"Kling task timed out: {task_id}")


def create_and_wait(provider: str, prompt: str, references: list[str], duration: int, resolution: str = "768P", ratio: str = "16:9") -> str:
    if provider == "MiniMax H3":
        from services.minimax_h3 import create_task, wait_for_task
        task = create_task(prompt, references, duration, resolution, ratio)
        return wait_for_task(task)
    if provider == "Kling 2.5 Turbo":
        mode = "720p" if resolution != "2K" else "1080p"
        task = _kling_create(prompt, references[0] if references else None, duration, mode)
        return _kling_wait(task)
    raise ValueError(f"Unknown video provider: {provider}")
