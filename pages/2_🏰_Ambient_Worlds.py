from __future__ import annotations

import os
import streamlit as st
from supabase import create_client
from services.ambient import WORLD_TEMPLATES, template_prompt
from services.ambient_ai import generate_ambient_concept
from services.campaigns import save_campaign

st.set_page_config(page_title="Ambient Worlds", page_icon="🏰", layout="wide")
st.title("🏰 Ambient Worlds Engine")
st.caption("Original fantasy ambience production. GitHub Actions is the only production FFmpeg renderer.")

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
    st.info("Production rule: create one strong environment image and animate it subtly. Rendering happens on GitHub Actions, not inside Streamlit.")

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
st.header("🎬 Queue Render")
pack = st.session_state.get("ambient_pack")
if not pack:
    st.info("Design and save an Ambient World first.")
else:
    ambient = pack["ambient"]
    hours = float(ambient["duration"].split()[0])
    image = st.file_uploader("Upload the 16:9 environment image", type=["png", "jpg", "jpeg", "webp"], key="ambient_image")
    st.caption(f"Target: {hours:g} hour(s) · {ambient['world']} · {ambient['weather']} · {ambient['use_case']}")

    if st.button("🌧️ Queue GitHub Render", type="primary", use_container_width=True):
        if not image:
            st.warning("Upload the environment image first.")
        else:
            try:
                supabase_url = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
                service_key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                if not supabase_url or not service_key:
                    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for queueing.")
                sb = create_client(supabase_url, service_key)
                raw = image.getvalue()
                if len(raw) > 20 * 1024 * 1024:
                    raise ValueError("Environment image is larger than 20 MB.")
                ext = image.name.rsplit(".", 1)[-1].lower()
                if ext == "jpg": ext = "jpeg"
                storage_path = f"ambient-inputs/{st.session_state.get('ambient_campaign', {}).get('id', 'adhoc')}-{abs(hash(image.name))}.{ext}"
                content_type = image.type or f"image/{ext}"
                sb.storage.from_("media-assets").upload(storage_path, raw, {"content-type": content_type, "upsert": "true"})
                public_url = sb.storage.from_("media-assets").get_public_url(storage_path)
                if isinstance(public_url, dict):
                    public_url = public_url.get("publicUrl") or public_url.get("public_url")
                payload = {
                    "image_url": public_url,
                    "title": pack.get("title") or "Ambient World",
                    "duration_hours": hours,
                    "layers": ambient.get("layers", []),
                    "thumbnail_text": pack.get("thumbnail_text") or pack.get("title", "Ambient World"),
                    "world": ambient.get("world"),
                    "weather": ambient.get("weather"),
                    "use_case": ambient.get("use_case")
                }
                row = sb.table("render_jobs").insert({
                    "campaign_id": st.session_state.get("ambient_campaign", {}).get("id"),
                    "job_type": "ambient_render",
                    "priority": 100,
                    "payload": payload,
                    "status": "queued",
                    "progress": 0,
                }).execute()
                job = row.data[0] if row.data else {}
                st.success(f"Queued GitHub render: {job.get('id', 'created')} — worker will process it automatically.")
            except Exception as ex:
                st.error(f"Queue failed: {ex}")

st.divider()
st.caption("Production architecture: Streamlit/Vercel frontend → Supabase queue → GitHub Actions + FFmpeg → Supabase Storage. No Render/Railway/Oracle video worker is used.")
