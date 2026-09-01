from __future__ import annotations

import os
import time
from typing import Any

import requests


def _secret(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
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
    api_key = _secret("KLING_API_KEY")
    if not api_key:
        raise ValueError("KLING_API_KEY is required.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _kling_base() -> str:
    return _secret("KLING_API_BASE", "https://api-singapore.klingai.com").rstrip("/")


def _kling_create(
    prompt: str,
    image_url: str | None,
    duration: int,
    ratio: str,
    mode: str = "std",
) -> tuple[str, str]:
    if ratio not in {"16:9", "9:16", "1:1"}:
        raise ValueError("Kling 2.5 Turbo supports 16:9, 9:16, and 1:1 aspect ratios.")
    if duration not in {5, 10}:
        raise ValueError("Kling 2.5 Turbo supports 5-second or 10-second clips.")

    payload: dict[str, Any] = {
        "model_name": "kling-v2-5-turbo",
        "prompt": prompt,
        "duration": str(duration),
        "mode": mode,
        "aspect_ratio": ratio,
    }
    if image_url:
        payload["image"] = image_url
        endpoint = "/v1/videos/image2video"
    else:
        endpoint = "/v1/videos/text2video"

    callback_url = _secret("KLING_CALLBACK_URL")
    if callback_url:
        payload["callback_url"] = callback_url

    response = requests.post(
        _kling_base() + endpoint,
        headers=_kling_headers(),
        json=payload,
        timeout=90,
    )
    if response.status_code >= 400:
        if response.status_code in (401, 403):
            raise RuntimeError(
                "KLING_AUTH_ERROR: Kling rejected the API key. Verify KLING_API_KEY and that API access is enabled."
            )
        if response.status_code == 402:
            raise RuntimeError(
                "KLING_BILLING_ERROR: Kling rejected the request because the account needs available API credits."
            )
        raise RuntimeError(f"Kling create task failed ({response.status_code}): {response.text}")

    body = response.json()
    if body.get("code") not in (None, 0):
        raise RuntimeError(f"Kling create task failed ({body.get('code')}): {body.get('message', body)}")

    task_id = body.get("data", {}).get("task_id")
    if not task_id:
        raise RuntimeError(f"Kling did not return task_id: {response.text}")
    return str(task_id), endpoint


def _kling_wait(task_id: str, endpoint: str, timeout: int = 1200) -> str:
    started = time.time()
    query_endpoint = endpoint.rsplit("/", 1)[-1]

    while time.time() - started < timeout:
        response = requests.get(
            f"{_kling_base()}/v1/videos/{query_endpoint}/{task_id}",
            headers=_kling_headers(),
            timeout=60,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Kling query failed ({response.status_code}): {response.text}")

        body = response.json()
        data = body.get("data", {})
        status = str(data.get("task_status", "")).lower()

        if status == "succeed":
            videos = data.get("task_result", {}).get("videos") or []
            url = videos[0].get("url") if videos else None
            if not url:
                raise RuntimeError("Kling completed without a video URL.")
            return url

        if status in {"failed", "cancelled", "canceled"}:
            message = data.get("task_status_msg") or body.get("message") or str(data)
            raise RuntimeError(f"Kling task failed: {message}")

        time.sleep(8)

    raise TimeoutError(f"Kling task timed out: {task_id}")


def create_and_wait(
    provider: str,
    prompt: str,
    references: list[str],
    duration: int,
    resolution: str = "768P",
    ratio: str = "16:9",
) -> str:
    if provider == "MiniMax H3":
        from services.minimax_h3 import create_task, wait_for_task
        task = create_task(prompt, references, duration, resolution, ratio)
        return wait_for_task(task)

    if provider == "Kling 2.5 Turbo":
        task_id, endpoint = _kling_create(
            prompt,
            references[0] if references else None,
            duration,
            ratio,
            mode="std",
        )
        return _kling_wait(task_id, endpoint)

    raise ValueError(f"Unknown video provider: {provider}")
