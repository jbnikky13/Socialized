from __future__ import annotations

import tempfile
from pathlib import Path
import streamlit as st

from services.minimax_h3 import api_key, build_episode, image_data_url
from services.media import upload_asset

st.set_page_config(page_title="AI Microdrama | Socialized", page_icon="🎥", layout="wide")
st.title("🎥 AI Photoreal Microdrama")
st.caption("Idea → recurring characters → scene dialogue → MiniMax H3 → finished MP4 → Supabase → YouTube")

campaign = st.session_state.get("last_campaign") or {}
reused = st.session_state.get("reused_content", [])
default_script = campaign.get("script", "")
if not default_script:
    default_script = next((x.get("body", "") for x in reused if x.get("platform") == "youtube" and x.get("content_type") == "video"), "")
default_title = campaign.get("title") or campaign.get("name") or "AI Microdrama"

with st.sidebar:
    st.subheader("⚙️ Render")
    resolution = st.selectbox("Resolution", ["768P", "2K"], index=0)
    ratio = st.selectbox("YouTube format", ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"], index=0)
    if api_key():
        st.success("MiniMax API key detected")
    else:
        st.warning("MINIMAX_API_KEY missing")
    st.info("H3 is billed per output second. Start with one 4–5 second 768P scene before generating a full episode.")

st.subheader("1. Episode")
title = st.text_input("Episode title", value=default_title)
story = st.text_area("Story / script", value=default_script, height=180, placeholder="Describe the story and exact dialogue. For best lip-sync, enter the words characters should actually speak.")

st.subheader("2. Recurring characters")
char_count = st.number_input("Characters", min_value=1, max_value=6, value=2, step=1)
characters = []
cols = st.columns(min(3, int(char_count)))
for i in range(int(char_count)):
    with cols[i % len(cols)]:
        name = st.text_input("Name", value=["Maya", "Daniel", "Sarah", "David", "Amara", "Tunde"][i], key=f"char_name_{i}")
        description = st.text_area("Appearance / identity", key=f"char_desc_{i}", height=80, placeholder="Age, skin tone, hair, clothing, distinctive features...")
        ref_url = st.text_input("Reference image URL", key=f"char_url_{i}", placeholder="https://...")
        upload = st.file_uploader("Or upload reference", type=["jpg", "jpeg", "png", "webp"], key=f"char_upload_{i}")
        ref = image_data_url(upload) if upload else ref_url.strip()
        if upload:
            st.image(upload, width=150)
        characters.append({"name": name.strip() or f"Character {i+1}", "description": description.strip(), "reference": ref})

st.subheader("3. Scene plan")
scene_count = st.number_input("Scenes", min_value=1, max_value=12, value=3, step=1)
scenes = []
for i in range(int(scene_count)):
    with st.expander(f"Scene {i+1}", expanded=(i == 0)):
        setting = st.text_input("Setting", key=f"setting_{i}", placeholder="Lagos apartment at sunset...")
        selected_names = st.multiselect("Characters", [c["name"] for c in characters], default=[characters[0]["name"]], key=f"scene_chars_{i}")
        action = st.text_area("Action + camera", key=f"action_{i}", height=80, placeholder="She enters, notices the phone, freezes. Slow camera push-in...")
        dialogue = st.text_area("Exact spoken dialogue", key=f"dialogue_{i}", height=80, placeholder="Enter exact words. Do not summarize.")
        duration = st.slider("Duration", 4, 15, 5, key=f"duration_{i}")
        prompt = f"""Photorealistic live-action microdrama scene. Natural human skin, eyes, hair, hands and body movement. Cinematic but believable lighting and camera movement. No cartoon, illustration, plastic skin, warped faces, extra fingers, text overlays or baked-in subtitles. Keep recurring characters consistent with their supplied reference images.

SETTING: {setting}
CHARACTERS: {', '.join(selected_names)}
CHARACTER DETAILS: {'; '.join(c['name'] + ': ' + c['description'] for c in characters if c['name'] in selected_names and c['description'])}
ACTION / CAMERA: {action}

The character must speak the following dialogue exactly and naturally, with facial expression and mouth movement synchronized to the words. Do not paraphrase or invent dialogue.
EXACT DIALOGUE: {dialogue or '[No spoken dialogue]'}"""
        refs = [c["reference"] for c in characters if c["name"] in selected_names and c["reference"]]
        scenes.append({"prompt": prompt, "references": refs, "duration": int(duration), "resolution": resolution, "ratio": ratio})

st.divider()
missing = [c["name"] for c in characters if not c["reference"]]
if missing:
    st.warning("Add a reference image URL or upload for: " + ", ".join(missing))
if not story.strip():
    st.info("You can use the saved YouTube script above or enter a new story.")

if st.button("🚀 Generate Photoreal Episode", type="primary", use_container_width=True, disabled=(not api_key() or bool(missing))):
    run_dir = Path(tempfile.mkdtemp(prefix="socialized_h3_"))
    progress_box = st.empty()
    progress = st.progress(0)
    try:
        def update(scene_no, total, status, task):
            progress.progress(min(100, int((scene_no - 1) / total * 100)))
            progress_box.info(f"Scene {scene_no}/{total}: {status} — MiniMax task {task.get('task_id', '')}")

        final_path, task_ids = build_episode(scenes, run_dir, progress=update)
        progress.progress(100)
        progress_box.success(f"Episode generated: {len(task_ids)} scenes")
        video_data = final_path.read_bytes()
        st.video(video_data)
        st.download_button("⬇️ Download MP4", data=video_data, file_name=f"{title or 'microdrama'}.mp4", mime="video/mp4", use_container_width=True)

        if campaign.get("id"):
            asset = upload_asset(str(final_path), str(campaign["id"]), asset_type="video")
            st.session_state["video_asset"] = asset
            st.success("Video stored in Supabase and attached to the active campaign. Open the YouTube tab to review/publish.")
        else:
            st.info("No saved campaign was selected, so the MP4 was not attached to Supabase. Save a campaign in Create first if you want automatic publishing.")
        st.session_state["microdrama_task_ids"] = task_ids
        st.session_state["microdrama_title"] = title
    except Exception as exc:
        st.error(f"Generation failed: {exc}")
        st.exception(exc)
