from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from services.video_providers import available, create_and_wait, estimate
from services.minimax_h3 import image_data_url, stitch, download
from services.media import upload_asset

st.set_page_config(page_title="AI Microdrama | Socialized", page_icon="🎥", layout="wide")
st.title("🎥 AI Photoreal Microdrama")
st.caption("Campaign/story → scenes → Kling/AI video → finished video → Supabase → YouTube")

campaign = st.session_state.get("last_campaign") or {}
reused = st.session_state.get("reused_content", [])
default_script = campaign.get("script", "") or next(
    (x.get("body", "") for x in reused if x.get("platform") == "youtube" and x.get("content_type") == "video"),
    "",
)
default_title = campaign.get("title") or campaign.get("name") or "AI Microdrama"

with st.sidebar:
    st.subheader("⚙️ Video engine")
    provider = st.selectbox(
        "Provider",
        ["Kling 3.0 Turbo", "Kling 2.5 Turbo", "Kling Studio (Manual)", "MiniMax H3"],
        help="Kling API uses KLING_API_KEY. Kling Studio (Manual) lets you generate clips in the Kling web app and bring them back into Socialized for stitching/storage.",
    )

    if provider == "Kling 3.0 Turbo":
        options = ["720P", "1080P"]
        ratio_options = ["16:9", "9:16", "1:1"]
        credential_label = "KLING_API_KEY"
        st.caption("Kling 3.0 Turbo: native audio + dialogue/lip-sync. Current API rates: $0.112/sec at 720P or $0.14/sec at 1080P.")
    elif provider == "Kling 2.5 Turbo":
        options = ["720P", "1080P"]
        ratio_options = ["16:9", "9:16", "1:1"]
        credential_label = "KLING_API_KEY"
        st.caption("Kling 2.5 Turbo: $0.042/sec at 720P or $0.07/sec at 1080P; no native audio.")
    elif provider == "Kling Studio (Manual)":
        options = ["720P", "1080P"]
        ratio_options = ["16:9", "9:16", "1:1"]
        credential_label = "not required"
        st.info("Manual mode uses your Kling Creative Studio account. Generate each scene there, download the MP4, then upload it below. No Kling API credits are consumed by Socialized.")
    else:
        options = ["768P", "2K"]
        ratio_options = ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]
        credential_label = "MINIMAX_API_KEY"

    resolution = st.selectbox("Resolution", options)
    ratio = st.selectbox("Format", ratio_options)

    if provider == "Kling Studio (Manual)":
        st.success("✓ Manual Studio mode ready")
    elif available(provider):
        st.success(f"{provider} API credentials detected")
    else:
        st.warning(f"Add {credential_label} to Streamlit Secrets")

    if provider.startswith("Kling") and provider != "Kling Studio (Manual)" and st.secrets.get("KLING_WEBHOOK_SECRET", ""):
        st.caption("✓ Kling webhook secret detected")

st.subheader("1. Episode")
title = st.text_input("Episode title", value=default_title)
story = st.text_area(
    "Campaign script / story",
    value=default_script,
    height=160,
    placeholder="Use the saved campaign script or paste a story.",
)

st.subheader("2. Recurring characters")
count = st.number_input("Characters", 1, 6, 2, 1)
characters = []
cols = st.columns(min(3, int(count)))
for i in range(int(count)):
    with cols[i % len(cols)]:
        name = st.text_input("Name", ["Maya", "Daniel", "Sarah", "David", "Amara", "Tunde"][i], key=f"vp_name_{i}")
        desc = st.text_area("Appearance / identity", key=f"vp_desc_{i}", height=70)
        url = st.text_input("Reference image URL", key=f"vp_url_{i}", placeholder="https://...")
        upload = st.file_uploader("Or upload reference", type=["jpg", "jpeg", "png", "webp"], key=f"vp_upload_{i}")
        ref = image_data_url(upload) if upload else url.strip()
        if upload:
            st.image(upload, width=140)
        characters.append({"name": name.strip() or f"Character {i + 1}", "description": desc.strip(), "reference": ref})

st.subheader("3. Scenes")
scene_count = st.number_input("Scenes", 1, 12, 3, 1)
scenes = []
for i in range(int(scene_count)):
    with st.expander(f"Scene {i + 1}", expanded=i == 0):
        setting = st.text_input("Setting", key=f"vp_setting_{i}")
        selected = st.multiselect("Characters", [c["name"] for c in characters], default=[characters[0]["name"]], key=f"vp_chars_{i}")
        action = st.text_area("Action + camera", key=f"vp_action_{i}", height=70)
        dialogue = st.text_area("Exact dialogue", key=f"vp_dialogue_{i}", height=70)
        duration_min = 3 if provider == "Kling 3.0 Turbo" else 5
        duration_max = 15 if provider == "Kling 3.0 Turbo" else 10
        duration_default = min(5, duration_max)
        duration = st.slider("Duration", duration_min, duration_max, duration_default, key=f"vp_duration_{i}")

        if provider == "Kling 3.0 Turbo":
            audio_note = "Generate natural spoken dialogue, accurate lip movements, facial performance, ambience and sound effects. Keep each character's voice/identity consistent and do not invent or paraphrase the supplied dialogue."
        elif provider == "Kling 2.5 Turbo":
            audio_note = "The spoken dialogue is a script cue only; do not attempt to render speech audio. Preserve the intended facial expression and mouth movement for later audio/lip-sync."
        elif provider == "Kling Studio (Manual)":
            audio_note = "This prompt will be copied into Kling Creative Studio. Use Kling VIDEO 3.0/3.0 Omni native audio or Kling Lip Sync in Studio for spoken dialogue."
        else:
            audio_note = "Speak the supplied dialogue naturally and synchronize mouth movement and facial expression to the words when supported by the selected model."

        prompt = (
            "Photorealistic live-action microdrama. Natural human skin, realistic eyes, hair, hands and body movement. "
            "Cinematic believable lighting. Preserve recurring character identity from reference images. No cartoon, illustration, "
            "warped faces, extra fingers, text overlays or baked-in subtitles. "
            f"SETTING: {setting}. CHARACTERS: {', '.join(selected)}. "
            f"DETAILS: {'; '.join(c['name'] + ': ' + c['description'] for c in characters if c['name'] in selected and c['description'])}. "
            f"ACTION/CAMERA: {action}. Exact dialogue: {dialogue or '[No spoken dialogue]'}. "
            f"{audio_note}"
        )
        st.code(prompt, language="text")

        manual_clip = None
        if provider == "Kling Studio (Manual)":
            st.caption("Generate this scene in Kling Studio, download the MP4, then upload it here. Socialized will stitch the uploaded scenes and save the final episode to Supabase.")
            manual_clip = st.file_uploader("Upload completed Kling Studio scene", type=["mp4", "mov"], key=f"vp_manual_clip_{i}")

        refs = [c["reference"] for c in characters if c["name"] in selected and c["reference"]]
        scenes.append({"prompt": prompt, "references": refs, "duration": int(duration), "manual_clip": manual_clip})

seconds = sum(s["duration"] for s in scenes)
cost = sum(estimate(provider, s["duration"], resolution) for s in scenes) if provider != "Kling Studio (Manual)" else 0.0
st.divider()
st.metric("Estimated generation cost", "$0.00" if provider == "Kling Studio (Manual)" else f"${cost:.2f}", f"{seconds}s total • {provider}")
if provider == "Kling 3.0 Turbo":
    st.caption("Kling 3.0 Turbo provides native audio, dialogue and lip-sync in the generated scene. Current API pricing is separate from Kling Studio membership/free credits.")
if provider == "Kling 2.5 Turbo":
    st.caption("Kling 2.5 Turbo has no native audio. Use Kling 3.0 Turbo or Manual Studio Lip Sync if spoken dialogue is required.")
if provider == "Kling Studio (Manual)":
    st.caption("Manual Studio mode does not call the Kling API. Your Kling Studio account handles generation; Socialized only assembles and stores the clips you upload.")
if cost > 10:
    st.warning("Estimated API generation cost is above $10. Consider fewer/shorter scenes or Manual Studio mode.")

missing = [c["name"] for c in characters if not c["reference"]]
if missing and provider != "Kling Studio (Manual)":
    st.warning("Add reference images for: " + ", ".join(missing))

manual_missing = provider == "Kling Studio (Manual)" and any(not s["manual_clip"] for s in scenes)
api_unavailable = provider != "Kling Studio (Manual)" and not available(provider)
disabled = api_unavailable or manual_missing or (bool(missing) and provider != "Kling Studio (Manual)")

if provider == "Kling Studio (Manual)":
    st.info("Workflow: 1) Copy each scene prompt → 2) Generate in Kling Studio → 3) Download each MP4 → 4) Upload each scene above → 5) Generate Episode below.")

if st.button("🚀 Generate / Assemble Episode", type="primary", use_container_width=True, disabled=disabled):
    work = Path(tempfile.mkdtemp(prefix="socialized_video_"))
    clips = []
    progress = st.progress(0)
    status = st.empty()
    try:
        for idx, scene in enumerate(scenes, 1):
            if provider == "Kling Studio (Manual)":
                status.info(f"Preparing manually generated scene {idx}/{len(scenes)}...")
                clip = work / f"scene_{idx:02d}.mp4"
                clip.write_bytes(scene["manual_clip"].getvalue())
            else:
                status.info(f"Generating scene {idx}/{len(scenes)} with {provider}...")
                url = create_and_wait(provider, scene["prompt"], scene["references"], scene["duration"], resolution, ratio)
                clip = work / f"scene_{idx:02d}.mp4"
                download(url, clip)
            clips.append(clip)
            progress.progress(int(idx / len(scenes) * 100))

        final = work / "microdrama_episode.mp4"
        stitch(clips, final)
        data = final.read_bytes()
        st.success(f"Episode ready — {seconds} seconds assembled with {provider}.")
        st.video(data)
        st.download_button("⬇️ Download MP4", data=data, file_name=f"{title or 'microdrama'}.mp4", mime="video/mp4", use_container_width=True)
        if campaign.get("id"):
            asset = upload_asset(str(final), str(campaign["id"]), asset_type="video")
            st.session_state["video_asset"] = asset
            st.success("Video attached to the active campaign. Open YouTube to review/publish.")
    except Exception as exc:
        msg = str(exc)
        if "KLING_AUTH_ERROR" in msg:
            st.error("🔐 Kling authentication failed. Verify KLING_API_KEY in Streamlit Secrets.")
        elif "KLING_BILLING_ERROR" in msg:
            st.error(f"💳 Kling API credits are insufficient. Estimated episode cost: ${cost:.2f}.")
        elif "402" in msg or "insufficient" in msg.lower():
            st.error(f"💳 {provider} rejected the request because the account balance/credits are insufficient. Estimated episode cost: ${cost:.2f}.")
        else:
            st.error(f"Video generation failed: {msg}")
        with st.expander("Technical details"):
            st.exception(exc)
