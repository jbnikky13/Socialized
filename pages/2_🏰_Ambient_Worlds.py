from __future__ import annotations
import os
import tempfile
import streamlit as st
from services.ambient import WORLD_TEMPLATES, template_prompt, generate_ambient_audio, make_ambient_thumbnail, render_ambient_video
from services.ambient_ai import generate_ambient_concept
from services.campaigns import save_campaign

st.set_page_config(page_title="Ambient Worlds", page_icon="🏰", layout="wide")
st.title("🏰 Ambient Worlds Engine")
st.caption("Low-cost original fantasy ambience production — one world, layered sound, long-form video.")

if "ambient_concept" not in st.session_state:
    st.session_state["ambient_concept"] = None

c1, c2, c3 = st.columns(3)
world = c1.selectbox("World", list(WORLD_TEMPLATES))
location = c2.text_input("Location", "The Last Lantern Tavern")
weather = c3.selectbox("Weather", ["Rain", "Thunderstorm", "Snow", "Wind", "Clear night", "Fog"])
c4, c5, c6 = st.columns(3)
use_case = c4.selectbox("Use case", ["Sleep", "Study", "Reading", "Writing", "Gaming / D&D", "Relaxation"])
duration = c5.selectbox("Duration", ["1 hour", "3 hours", "8 hours", "10 hours"])
mood = c6.selectbox("Mood", ["Cozy", "Mysterious", "Dark", "Magical", "Peaceful", "Epic"])

if st.button("✨ Design Original World", type="primary", use_container_width=True):
    try:
        with st.spinner("Designing titles, description, sound layers and the world prompt..."):
            st.session_state["ambient_concept"] = generate_ambient_concept(world, location, weather, use_case, duration)
    except Exception as ex:
        st.error(str(ex))

concept = st.session_state.get("ambient_concept")
if concept:
    st.divider()
    titles = concept.get("title_options") or [f"{location} — {weather} Ambience"]
    title = st.selectbox("YouTube title", titles)
    description = st.text_area("Description", concept.get("description", ""), height=140)
    tags = st.text_input("Tags", ", ".join(concept.get("tags", [])))
    thumb_text = st.text_input("Thumbnail text", concept.get("thumbnail_text", ""))
    layers = concept.get("audio_layers", [])
    st.write("**Sound layers:** " + ", ".join(layers))
    scene_prompt = st.text_area("Single environment image prompt", concept.get("scene_prompt") or template_prompt(world, weather, mood), height=150)
    st.info("Production rule: create one strong environment image and animate it subtly. No expensive multi-scene AI video generation is required.")

    if st.button("💾 Save Campaign", use_container_width=True):
        pack = {
            "title": title, "script": "ambient", "description": description,
            "tags": [x.strip() for x in tags.split(",") if x.strip()],
            "thumbnail_text": thumb_text, "x_posts": [], "shorts": [],
            "ambient": {"world": world, "location": location, "weather": weather,
                        "use_case": use_case, "duration": duration, "layers": layers,
                        "scene_prompt": scene_prompt}
        }
        try:
            campaign = save_campaign(title, "Fantasy ambience", pack)
            st.session_state["ambient_campaign"] = campaign
            st.session_state["ambient_pack"] = pack
            st.success(f"Campaign saved: {campaign['id']}")
        except Exception as ex:
            st.error(str(ex))

st.divider()
st.header("🎬 Render")
pack = st.session_state.get("ambient_pack")
if not pack:
    st.info("Design and save an Ambient World first.")
else:
    ambient = pack["ambient"]
    hours = float(ambient["duration"].split()[0])
    image = st.file_uploader("Upload the 16:9 environment image", type=["png", "jpg", "jpeg", "webp"])
    st.caption(f"Target: {hours:g} hour(s) · {ambient['world']} · {ambient['weather']} · {ambient['use_case']}")
    if st.button("🌧️ Render Ambient Video", type="primary", use_container_width=True):
        if not image:
            st.warning("Upload the environment image first.")
        else:
            try:
                with st.spinner(f"Rendering {hours:g}-hour ambience video. This can take time on a small worker..."):
                    work = tempfile.mkdtemp(prefix="socialized_ambient_")
                    img = os.path.join(work, "world.jpg"); audio = os.path.join(work, "ambience.wav"); thumb = os.path.join(work, "thumbnail.jpg"); video = os.path.join(work, "ambient.mp4")
                    with open(img, "wb") as fh: fh.write(image.getbuffer())
                    generate_ambient_audio(audio, hours, ambient.get("layers"))
                    make_ambient_thumbnail(pack.get("thumbnail_text") or pack["title"], img, thumb)
                    render_ambient_video(img, audio, video, hours)
                    st.session_state["ambient_files"] = {"video": video, "thumbnail": thumb, "audio": audio}
                st.success("Ambient video rendered successfully.")
            except Exception as ex:
                st.error(str(ex))

files = st.session_state.get("ambient_files")
if files:
    st.video(files["video"])
    with open(files["video"], "rb") as fh:
        st.download_button("⬇️ Download MP4", fh.read(), file_name="ambient_world.mp4", mime="video/mp4", use_container_width=True)
    with open(files["thumbnail"], "rb") as fh:
        st.download_button("🖼️ Download Thumbnail", fh.read(), file_name="ambient_thumbnail.jpg", mime="image/jpeg", use_container_width=True)

st.divider()
st.caption("Original-world workflow. Do not copy another creator's artwork, audio, branding, characters or fictional locations.")
