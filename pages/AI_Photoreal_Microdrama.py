from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from services import media
from services.video_providers import available, create_and_wait, estimate
from services.minimax_h3 import download, stitch

st.set_page_config(page_title="AI Photoreal Microdrama", page_icon="🎬", layout="wide")
st.title("🎬 AI Photoreal Microdrama")
st.caption("Generate a microdrama from AI visuals or uploaded images, then turn each image into a moving scene.")

campaign = st.session_state.get("last_campaign") or {}
campaign_id = campaign.get("id")

visual_source = st.radio(
    "Visual source",
    ["🤖 Generate visuals with Pollination AI", "📤 Upload my own images"],
    horizontal=True,
)

provider = st.selectbox("Video engine", ["Kling 3.0 Turbo", "Kling 2.5 Turbo", "MiniMax H3"])
if provider == "Kling 3.0 Turbo":
    resolution = st.selectbox("Resolution", ["720P", "1080P"])
    ratio = st.selectbox("Format", ["9:16", "16:9", "1:1"])
    duration = st.slider("Seconds per scene", 3, 15, 5)
elif provider == "Kling 2.5 Turbo":
    resolution = st.selectbox("Resolution", ["720P", "1080P"])
    ratio = st.selectbox("Format", ["9:16", "16:9", "1:1"])
    duration = st.select_slider("Seconds per scene", [5, 10], value=5)
else:
    resolution = st.selectbox("Resolution", ["768P", "2K"])
    ratio = st.selectbox("Format", ["9:16", "16:9", "1:1", "4:3", "3:4", "21:9"])
    duration = st.slider("Seconds per scene", 4, 15, 5)

if not available(provider):
    st.warning(f"Add the {('KLING_API_KEY' if provider.startswith('Kling') else 'MINIMAX_API_KEY')} secret before generating video.")

uploaded_assets = []
if visual_source == "📤 Upload my own images":
    st.subheader("📤 Your visual assets")
    st.info("These images replace the AI image-generation step. They are uploaded to Supabase and passed directly to the selected image-to-video provider.")
    uploads = st.file_uploader(
        "Upload scene/character images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="microdrama_pipeline_uploads",
    )
    if uploads:
        cols = st.columns(min(4, len(uploads)))
        for i, f in enumerate(uploads):
            with cols[i % len(cols)]:
                st.image(f, caption=f.name, use_container_width=True)

        if not campaign_id:
            st.error("Create or select a campaign first. Uploaded images need a campaign ID so they can be stored and reused.")
        elif st.button("☁️ Save uploaded images", type="primary", use_container_width=True):
            try:
                saved = []
                for i, f in enumerate(uploads):
                    suffix = Path(f.name).suffix.lower() or ".png"
                    temp = Path(tempfile.gettempdir()) / f"socialized_microdrama_{campaign_id}_{i}{suffix}"
                    temp.write_bytes(f.getbuffer())
                    try:
                        saved.append(media.upload_asset(str(temp), str(campaign_id), asset_type="microdrama_image"))
                    finally:
                        temp.unlink(missing_ok=True)
                st.session_state["microdrama_pipeline_images"] = saved
                st.success(f"Saved {len(saved)} image(s). They are now available to the video pipeline.")
            except Exception as exc:
                st.error(str(exc))

    uploaded_assets = st.session_state.get("microdrama_pipeline_images", [])
    if uploaded_assets:
        st.markdown("### Saved images")
        cols = st.columns(min(4, len(uploaded_assets)))
        for i, asset in enumerate(uploaded_assets):
            with cols[i % len(cols)]:
                st.image(asset.get("public_url", ""), caption=f"Image {i + 1}", use_container_width=True)
else:
    st.subheader("🤖 Pollination AI visuals")
    st.caption("This mode keeps the existing AI-image path. Uploaded-image mode above never calls Pollination for visuals.")
    st.warning("For uploaded-image generation, switch the visual source above. Pollination is not involved in that path.")

st.divider()
st.subheader("🎞️ Scene builder")
scene_count = st.number_input("Number of scenes", 1, 12, min(5, max(1, len(uploaded_assets) or 5)), 1)

scenes = []
for i in range(int(scene_count)):
    with st.expander(f"Scene {i + 1}", expanded=i == 0):
        action = st.text_area("Action / camera direction", key=f"pipeline_action_{i}", height=80, placeholder="A woman enters the apartment, freezes, then slowly turns toward the open bedroom door.")
        dialogue = st.text_area("Exact dialogue (optional)", key=f"pipeline_dialogue_{i}", height=70, placeholder="Don't move. I know what you did.")
        setting = st.text_input("Setting / continuity", key=f"pipeline_setting_{i}", placeholder="Modern Lagos apartment at night")

        ref_url = None
        if uploaded_assets:
            labels = [f"Uploaded image {j + 1}" for j in range(len(uploaded_assets))]
            selected = st.selectbox("Starting image", labels, key=f"pipeline_image_{i}")
            ref_url = uploaded_assets[int(selected.split()[-1]) - 1].get("public_url")
            if ref_url:
                st.image(ref_url, width=180)

        prompt = (
            "Photorealistic live-action microdrama. Preserve the subject's identity, clothing, environment and visual continuity "
            "from the starting image. Natural skin texture, realistic eyes, hair, hands and physics. Cinematic but believable lighting. "
            "No animation, illustration, warped faces, extra fingers, text overlays or watermarks. "
            f"SETTING: {setting}. ACTION/CAMERA: {action}. EXACT DIALOGUE: {dialogue or '[No spoken dialogue]'}. "
            "Make the movement subtle and cinematic, with realistic facial performance and camera motion."
        )
        scenes.append({"prompt": prompt, "reference": ref_url})

st.divider()
if scenes:
    total_seconds = int(duration) * len(scenes)
    st.metric("Estimated video duration", f"{total_seconds}s")
    st.caption(f"Estimated API generation cost: ${estimate(provider, total_seconds, resolution):.2f} based on the rates configured in Socialized.")

if st.button("🎬 Generate Microdrama", type="primary", use_container_width=True):
    if not campaign_id:
        st.error("Create or select a campaign first so the finished video can be stored in Supabase.")
    elif visual_source == "📤 Upload my own images" and not uploaded_assets:
        st.error("Upload and save at least one image first.")
    elif not available(provider):
        st.error("Configure the selected video provider API key first.")
    else:
        try:
            work = Path(tempfile.mkdtemp(prefix="socialized_microdrama_pipeline_"))
            clips = []
            progress = st.progress(0)
            status = st.empty()

            for i, scene in enumerate(scenes, 1):
                status.info(f"Generating scene {i}/{len(scenes)} with {provider}...")
                refs = [scene["reference"]] if scene.get("reference") else []
                url = create_and_wait(provider, scene["prompt"], refs, int(duration), resolution, ratio)
                clip = work / f"scene_{i:02d}.mp4"
                download(url, clip)
                clips.append(clip)
                progress.progress(int(i / len(scenes) * 100))

            final = work / "microdrama_episode.mp4"
            stitch(clips, final)
            asset = media.upload_asset(str(final), str(campaign_id), asset_type="microdrama_video")
            st.session_state["microdrama_pipeline_video"] = asset
            st.session_state["video_asset"] = asset
            status.success("Microdrama generated, stitched and stored in Supabase. It is ready in the YouTube publishing flow.")
        except Exception as exc:
            st.error(f"Microdrama generation failed: {exc}")

video_asset = st.session_state.get("microdrama_pipeline_video")
if video_asset and video_asset.get("public_url"):
    st.divider()
    st.subheader("🎥 Finished Microdrama")
    st.video(video_asset["public_url"])
    st.success("The finished MP4 is stored as a campaign media asset and is also loaded into Socialized's publishing video slot.")
