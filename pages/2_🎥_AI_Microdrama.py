from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from services.video_providers import available, create_and_wait, estimate
from services.minimax_h3 import image_data_url, stitch, download
from services.media import upload_asset

st.set_page_config(page_title="AI Microdrama | Socialized", page_icon="🎥", layout="wide")
st.title("🎥 AI Photoreal Microdrama")
st.caption("Campaign/story → scenes → Kling or MiniMax → finished video → Supabase → YouTube")

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
        ["Kling 2.5 Turbo", "MiniMax H3"],
        help="Kling uses the direct Open Platform API with Access Key + Secret Key JWT authentication.",
    )
    if provider == "Kling 2.5 Turbo":
        options = ["720P", "2K"]
        ratio_options = ["16:9", "9:16", "1:1"]
        credential_label = "KLING_ACCESS_KEY + KLING_SECRET_KEY"
    else:
        options = ["768P", "2K"]
        ratio_options = ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]
        credential_label = "MINIMAX_API_KEY"

    resolution = st.selectbox("Resolution", options)
    ratio = st.selectbox("Format", ratio_options)

    if available(provider):
        st.success(f"{provider} credentials detected")
    else:
        st.warning(f"Add {credential_label} to Streamlit Secrets")

    if provider == "Kling 2.5 Turbo" and st.secrets.get("KLING_WEBHOOK_SECRET", ""):
        st.caption("✓ Kling webhook secret detected (reserved for callback verification)")

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
        upload = st.file_uploader(
            "Or upload reference",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"vp_upload_{i}",
        )
        ref = image_data_url(upload) if upload else url.strip()
        if upload:
            st.image(upload, width=140)
        characters.append({
            "name": name.strip() or f"Character {i + 1}",
            "description": desc.strip(),
            "reference": ref,
        })

st.subheader("3. Scenes")
scene_count = st.number_input("Scenes", 1, 12, 3, 1)
scenes = []
for i in range(int(scene_count)):
    with st.expander(f"Scene {i + 1}", expanded=i == 0):
        setting = st.text_input("Setting", key=f"vp_setting_{i}")
        selected = st.multiselect(
            "Characters",
            [c["name"] for c in characters],
            default=[characters[0]["name"]],
            key=f"vp_chars_{i}",
        )
        action = st.text_area("Action + camera", key=f"vp_action_{i}", height=70)
        dialogue = st.text_area("Exact dialogue", key=f"vp_dialogue_{i}", height=70)
        duration = st.slider("Duration", 5, 10, 5, key=f"vp_duration_{i}")
        prompt = (
            "Photorealistic live-action microdrama. Natural human skin, realistic eyes, hair, hands and body movement. "
            "Cinematic believable lighting. Preserve recurring character identity from reference images. No cartoon, "
            "illustration, warped faces, extra fingers, text overlays or baked-in subtitles. "
            f"SETTING: {setting}. CHARACTERS: {', '.join(selected)}. "
            f"DETAILS: {'; '.join(c['name'] + ': ' + c['description'] for c in characters if c['name'] in selected and c['description'])}. "
            f"ACTION/CAMERA: {action}. Exact spoken dialogue: {dialogue or '[No spoken dialogue]'}. "
            "Speak the supplied dialogue naturally and synchronize mouth movement and facial expression to the words; "
            "do not paraphrase or invent dialogue."
        )
        refs = [c["reference"] for c in characters if c["name"] in selected and c["reference"]]
        scenes.append({"prompt": prompt, "references": refs, "duration": int(duration)})

seconds = sum(s["duration"] for s in scenes)
cost = sum(estimate(provider, s["duration"], resolution) for s in scenes)
st.divider()
st.metric("Estimated generation cost", f"${cost:.2f}", f"{seconds}s total • {provider}")
st.caption("Estimate covers video generation only. Provider prices can change.")
if cost > 10:
    st.warning("Estimated cost is above $10. Consider fewer/shorter scenes or the cheaper provider.")

missing = [c["name"] for c in characters if not c["reference"]]
if missing:
    st.warning("Add reference images for: " + ", ".join(missing))

if provider == "Kling 2.5 Turbo" and ratio not in {"16:9", "9:16", "1:1"}:
    st.error("Kling 2.5 Turbo supports only 16:9, 9:16, and 1:1 formats.")

if st.button(
    "🚀 Generate Episode",
    type="primary",
    use_container_width=True,
    disabled=(not available(provider) or bool(missing)),
):
    work = Path(tempfile.mkdtemp(prefix="socialized_video_"))
    clips = []
    progress = st.progress(0)
    status = st.empty()
    try:
        for idx, scene in enumerate(scenes, 1):
            status.info(f"Generating scene {idx}/{len(scenes)} with {provider}...")
            url = create_and_wait(
                provider,
                scene["prompt"],
                scene["references"],
                scene["duration"],
                resolution,
                ratio,
            )
            clip = work / f"scene_{idx:02d}.mp4"
            download(url, clip)
            clips.append(clip)
            progress.progress(int(idx / len(scenes) * 100))

        final = work / "microdrama_episode.mp4"
        stitch(clips, final)
        data = final.read_bytes()
        st.success(f"Episode ready — {seconds} seconds generated with {provider}.")
        st.video(data)
        st.download_button(
            "⬇️ Download MP4",
            data=data,
            file_name=f"{title or 'microdrama'}.mp4",
            mime="video/mp4",
            use_container_width=True,
        )
        if campaign.get("id"):
            asset = upload_asset(str(final), str(campaign["id"]), asset_type="video")
            st.session_state["video_asset"] = asset
            st.success("Video attached to the active campaign. Open YouTube to review/publish.")
    except Exception as exc:
        msg = str(exc)
        if "KLING_AUTH_ERROR" in msg:
            st.error("🔐 Kling authentication failed. Verify KLING_ACCESS_KEY and KLING_SECRET_KEY in Streamlit Secrets.")
        elif "KLING_BILLING_ERROR" in msg:
            st.error(f"💳 Kling API credits are insufficient. Estimated episode cost: ${cost:.2f}.")
        elif "402" in msg or "insufficient" in msg.lower():
            st.error(f"💳 {provider} rejected the request because the account balance/credits are insufficient. Estimated episode cost: ${cost:.2f}.")
        else:
            st.error(f"Video generation failed: {msg}")
        with st.expander("Technical details"):
            st.exception(exc)
