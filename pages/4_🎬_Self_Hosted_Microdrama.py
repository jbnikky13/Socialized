from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import requests
import streamlit as st

from services.microdrama import generate_love_microdrama
from services import media


st.set_page_config(page_title="Self-Hosted AI Microdrama", page_icon="🎬", layout="wide")
st.title("🎬 Self-Hosted AI Photoreal Microdrama")
st.caption("Story on the control plane. Photoreal video generation on your rented GPU. No per-video generation credits.")


def _secret(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return default


worker_url = _secret("MICRODRAMA_WORKER_URL").rstrip("/")
worker_token = _secret("MICRODRAMA_WORKER_TOKEN")
headers = {"Authorization": f"Bearer {worker_token}"} if worker_token else {}

with st.sidebar:
    st.header("GPU worker")
    st.text_input("Worker URL", value=worker_url, disabled=True)
    if worker_url:
        try:
            response = requests.get(f"{worker_url}/health", headers=headers, timeout=15)
            response.raise_for_status()
            st.success("GPU worker online")
        except Exception as exc:
            st.error(f"GPU worker unavailable: {exc}")
    else:
        st.warning("Set MICRODRAMA_WORKER_URL in the Streamlit environment.")

campaign = st.session_state.get("last_campaign") or {}
if campaign.get("id"):
    st.info(f"Active campaign: {campaign.get('name', campaign.get('title', campaign['id']))}")
else:
    st.warning("Select or create a campaign in Socialized first. The finished MP4 will be stored against that campaign.")

st.subheader("1. Create the love story")
premise = st.text_area(
    "Story premise",
    value="Two university students who cannot stand each other are forced to work together and slowly fall in love, but a secret threatens to tear them apart.",
    height=100,
)
col1, col2 = st.columns(2)
with col1:
    duration_seconds = st.select_slider("Target episode length", options=[30, 45, 60, 90, 120], value=60)
with col2:
    scene_count = st.slider("Number of scenes", 4, 12, 8)

if st.button("✨ Generate romance story", type="primary", use_container_width=True):
    if not premise.strip():
        st.error("Enter a premise first.")
    else:
        try:
            with st.spinner("Writing the story and continuity bible..."):
                st.session_state["microdrama_story"] = generate_love_microdrama(
                    premise.strip(), duration_seconds, scene_count
                )
        except Exception as exc:
            st.error(str(exc))

story = st.session_state.get("microdrama_story")
if story:
    st.divider()
    st.subheader(f"2. {story.get('title', 'Microdrama')}")
    st.write(story.get("logline", ""))

    with st.expander("Characters & continuity", expanded=True):
        for character in story.get("characters", []):
            st.markdown(f"**{character.get('name', 'Character')}** — {character.get('age', '')}")
            st.write(character.get("appearance", ""))
            st.caption(f"Wardrobe: {character.get('wardrobe', '')} · Personality: {character.get('personality', '')}")
        st.info(story.get("continuity_bible", ""))

    st.subheader("3. GPU generation settings")
    model_type = st.text_input(
        "WanGP model type",
        value=_secret("MICRODRAMA_MODEL_TYPE", ""),
        help="Use a video model installed on the GPU worker. The worker is based on Wan2GP and can use its installed video models.",
    )
    resolution = st.selectbox("Resolution", ["832x480", "1280x720", "1280x704"], index=0)
    fps = st.selectbox("FPS", [24, 25, 30], index=0)
    steps = st.slider("Inference steps", 4, 30, 8)
    reference_text = st.text_area(
        "Character/reference image URL(s), one per line",
        value=_secret("MICRODRAMA_REFERENCE_IMAGE_URL", ""),
        height=80,
        help="Use public Supabase Storage image URLs or another URL the GPU worker can download. The first image becomes the starting image for I2V models.",
    )

    scene_options = story.get("scenes", [])
    selected_scene = st.selectbox(
        "Scene to generate",
        list(range(len(scene_options))),
        format_func=lambda i: f"Scene {i + 1}: {scene_options[i].get('setting', '')}",
    )
    scene = scene_options[selected_scene]
    st.text_area("Visual prompt", value=scene.get("visual_prompt", ""), height=180, key="microdrama_prompt")
    st.text_area("Action / camera", value=scene.get("action", ""), height=100, key="microdrama_action")
    st.text_area("Dialogue", value=scene.get("dialogue", ""), height=80, key="microdrama_dialogue")

    if st.button("🚀 Generate this scene on my GPU", type="primary", use_container_width=True):
        if not worker_url:
            st.error("MICRODRAMA_WORKER_URL is not configured.")
        elif not model_type.strip():
            st.error("Enter the WanGP model type installed on the worker.")
        elif not campaign.get("id"):
            st.error("Select/create a campaign first so the generated video has a storage destination.")
        else:
            prompt = (
                f"{story.get('continuity_bible', '')}\n\n"
                f"CHARACTERS: {story.get('characters', [])}\n\n"
                f"SCENE: {scene.get('visual_prompt', '')}\n"
                f"ACTION/CAMERA: {scene.get('action', '')}\n"
                f"DIALOGUE: {scene.get('dialogue', '')}\n"
                "Photorealistic live-action microdrama, natural human motion, realistic skin, eyes, hair and hands, "
                "cinematic but believable lighting, no animation, no text, no watermark."
            )
            settings = {
                "model_type": model_type.strip(),
                "prompt": prompt,
                "resolution": resolution,
                "num_inference_steps": steps,
                "video_length": max(17, round(int(scene.get("duration_seconds", 5)) * fps)),
                "duration_seconds": int(scene.get("duration_seconds", 5)),
                "force_fps": fps,
            }
            reference_urls = [x.strip() for x in reference_text.splitlines() if x.strip()]
            try:
                response = requests.post(
                    f"{worker_url}/jobs",
                    headers={**headers, "Content-Type": "application/json"},
                    json={"settings": settings, "reference_urls": reference_urls},
                    timeout=30,
                )
                response.raise_for_status()
                job = response.json()
                job_id = job["id"]
                st.session_state["microdrama_job_id"] = job_id
                st.success(f"GPU job queued: {job_id}")
            except Exception as exc:
                st.error(f"Could not queue GPU job: {exc}")

job_id = st.session_state.get("microdrama_job_id")
if job_id and worker_url:
    st.divider()
    st.subheader("4. GPU job")
    if st.button("🔄 Refresh generation status"):
        try:
            response = requests.get(f"{worker_url}/jobs/{job_id}", headers=headers, timeout=30)
            response.raise_for_status()
            st.session_state["microdrama_job"] = response.json()
        except Exception as exc:
            st.error(str(exc))

    job = st.session_state.get("microdrama_job", {})
    if job.get("status") in {None, "queued", "running"}:
        try:
            response = requests.get(f"{worker_url}/jobs/{job_id}", headers=headers, timeout=30)
            response.raise_for_status()
            job = response.json()
            st.session_state["microdrama_job"] = job
        except Exception:
            pass

    st.write(f"**Status:** {job.get('status', 'unknown')} — {job.get('message', '')}")
    if job.get("status") == "completed":
        try:
            response = requests.get(f"{worker_url}/jobs/{job_id}/download", headers=headers, timeout=300)
            response.raise_for_status()
            temp = Path(tempfile.gettempdir()) / f"socialized_microdrama_{job_id}.mp4"
            temp.write_bytes(response.content)
            asset = media.upload_asset(str(temp), str(campaign["id"]), asset_type="microdrama_video")
            st.session_state["video_asset"] = asset
            st.session_state["microdrama_pipeline_video"] = asset
            st.video(response.content)
            st.success("GPU-generated scene downloaded and stored in Supabase. It is now available to the existing YouTube approval flow.")
            temp.unlink(missing_ok=True)
        except Exception as exc:
            st.error(f"Could not store the generated video: {exc}")
    elif job.get("status") == "failed":
        st.error(job.get("message", "GPU generation failed."))
    else:
        st.info("The GPU worker is still processing. Refresh the status when it finishes.")
