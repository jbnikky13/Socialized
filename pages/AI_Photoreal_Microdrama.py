from __future__ import annotations

import os
import tempfile
from pathlib import Path
from urllib.parse import quote

import streamlit as st

from services import media

st.set_page_config(page_title="AI Photoreal Microdrama", page_icon="🎬", layout="wide")
st.title("🎬 AI Photoreal Microdrama")
st.caption("Create short-form microdrama scenes with AI visuals or your own uploaded images.")

# Upload Images is a real alternative visual provider: when selected,
# the Pollination image path is never requested.
visual_source = st.radio(
    "Visual source",
    ["🤖 Pollination AI", "📤 Upload images"],
    horizontal=True,
    help="Choose Pollination AI for generated scene images, or upload your own images and use them instead.",
)

campaign_id = st.session_state.get("last_campaign", {}).get("id")

if visual_source == "📤 Upload images":
    st.subheader("📤 Upload your microdrama images")
    st.info("Uploaded images are used as the scene visuals. Pollination AI is not called when this option is selected.")

    uploads = st.file_uploader(
        "Character, location, or scene reference images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="microdrama_images",
        help="Upload one or several images. You can assign them to scenes below.",
    )

    if uploads:
        cols = st.columns(min(4, len(uploads)))
        for i, uploaded in enumerate(uploads):
            with cols[i % len(cols)]:
                st.image(uploaded, caption=uploaded.name, use_container_width=True)

        if not campaign_id:
            st.warning("Select or create a campaign first if you want the images permanently stored in Supabase.")
        elif st.button("☁️ Save images to campaign", type="primary", use_container_width=True):
            saved = []
            try:
                for index, uploaded in enumerate(uploads):
                    suffix = Path(uploaded.name).suffix.lower() or ".png"
                    temp = Path(tempfile.gettempdir()) / f"socialized_microdrama_{campaign_id}_{index}{suffix}"
                    temp.write_bytes(uploaded.getbuffer())
                    try:
                        saved.append(media.upload_asset(str(temp), str(campaign_id), asset_type="microdrama_image"))
                    finally:
                        temp.unlink(missing_ok=True)
                st.session_state["microdrama_images"] = saved
                st.success(f"Saved {len(saved)} image(s) to Supabase Storage.")
            except Exception as exc:
                st.error(str(exc))

    saved = st.session_state.get("microdrama_images", [])
    if saved:
        st.subheader("Saved scene images")
        for index, asset in enumerate(saved, 1):
            url = asset.get("public_url", "")
            st.image(url, caption=f"Uploaded image {index}", width=220)

else:
    st.subheader("🤖 Pollination AI visuals")
    st.caption("Use AI-generated stills when you do not have your own visual assets.")
    prompt = st.text_area(
        "Scene visual prompt",
        placeholder="Photorealistic cinematic close-up of two people arguing in a Lagos apartment at night, natural skin texture, dramatic practical lighting, 9:16 vertical composition",
        height=120,
    )
    if st.button("Generate scene image", type="primary"):
        if not prompt.strip():
            st.warning("Enter a visual prompt first.")
        else:
            encoded = quote(prompt.strip())
            model = os.getenv("POLLINATIONS_MODEL", "flux")
            url = f"https://image.pollinations.ai/prompt/{encoded}?model={quote(model)}&width=768&height=1365&nologo=true"
            st.session_state["microdrama_pollination_url"] = url
            st.success("Pollination AI scene image prepared.")

    if st.session_state.get("microdrama_pollination_url"):
        st.image(st.session_state["microdrama_pollination_url"], caption="Pollination AI scene", use_container_width=True)

st.divider()
st.subheader("🎞️ Microdrama scene plan")
scene_count = st.number_input("Number of scenes", min_value=1, max_value=20, value=5, step=1)

saved_images = st.session_state.get("microdrama_images", [])
visual_options = ["Use uploaded image"] + [f"Uploaded image {i + 1}" for i in range(len(saved_images))]

for scene in range(1, int(scene_count) + 1):
    with st.expander(f"Scene {scene}", expanded=scene == 1):
        st.text_area("Action / dialogue", key=f"micro_scene_{scene}", height=100, placeholder="Describe what happens in this scene...")
        if visual_source == "📤 Upload images":
            st.selectbox("Visual", visual_options, key=f"micro_visual_{scene}")
        else:
            st.caption("Visual source: Pollination AI")

st.caption("Uploaded-image mode is provider-independent: your image is stored as a campaign asset and can be passed to the downstream image-to-video renderer without requesting a new image from Pollination AI.")
