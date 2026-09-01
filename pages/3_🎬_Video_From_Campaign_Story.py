import tempfile
from pathlib import Path
import streamlit as st
from services.campaigns import recent_campaigns, reuse_campaign
from services.video_sources import extract_uploaded_text, screenplay_from_source, campaign_script
from services.minimax_h3 import api_key, build_episode, image_data_url
from services.media import upload_asset

st.set_page_config(page_title="Video Factory | Socialized", page_icon="🎬", layout="wide")
st.title("🎬 Video Factory")
st.caption("Campaign → script → screenplay → photoreal video OR upload/paste a story → screenplay → video")

with st.sidebar:
    resolution = st.selectbox("Resolution", ["768P", "2K"])
    ratio = st.selectbox("Format", ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"])
    st.success("MiniMax API key detected") if api_key() else st.warning("MINIMAX_API_KEY missing")

source = st.radio("Video source", ["📊 Campaign", "📄 Upload story/script", "✍️ Paste story/script"], horizontal=True)
text = ""; title = "AI Video"; kind = "story"; active_campaign = st.session_state.get("last_campaign") or {}

if source == "📊 Campaign":
    campaigns = recent_campaigns() or []
    if campaigns:
        labels = [f"{c.get('name','Untitled')} · {c.get('status','')}" for c in campaigns]
        idx = next((i for i,c in enumerate(campaigns) if c.get('id') == active_campaign.get('id')), 0)
        selected = campaigns[st.selectbox("Select campaign", labels, index=idx, key="vf_campaign") and labels.index(st.session_state.get("vf_campaign", labels[0]))]
        try:
            loaded = reuse_campaign(selected["id"]); active_campaign = loaded["campaign"]
            text = campaign_script(active_campaign, loaded["content"])
        except Exception:
            text = campaign_script(selected, [])
        title = selected.get("name") or title
        if text: st.success(f"Campaign script loaded ({len(text):,} characters).")
        else: st.warning("This campaign has no saved YouTube script. Generate/save the campaign first.")
    else:
        st.info("No campaigns found. Create and save one first.")
    kind = "campaign"
elif source == "📄 Upload story/script":
    upload = st.file_uploader("Upload story or screenplay", type=["txt","md","markdown","docx","pdf"])
    if upload:
        try:
            text = extract_uploaded_text(upload); title = Path(upload.name).stem
            st.success(f"Loaded {upload.name} ({len(text):,} characters).")
            with st.expander("Preview extracted text"): st.text(text[:12000])
        except Exception as exc: st.error(f"File extraction failed: {exc}")
    kind = "uploaded story/script"
else:
    title = st.text_input("Story title", "AI Microdrama")
    text = st.text_area("Paste story / script", height=320, placeholder="Paste a full story, screenplay, documentary script or narration here...")
    kind = "pasted story/script"

if st.button("✨ Convert Source to Screenplay", type="primary", disabled=not bool(text.strip())):
    try:
        with st.spinner("Creating characters, scenes and exact dialogue..."):
            st.session_state["video_factory_screenplay"] = screenplay_from_source(text, kind, title)
        st.success("Screenplay ready. Review it before generating video credits.")
    except Exception as exc: st.error(str(exc))

screenplay = st.session_state.get("video_factory_screenplay") or {}
if screenplay:
    title = st.text_input("Final video title", screenplay.get("title") or title)
    chars = screenplay.get("characters", []); refs = {}
    st.subheader("👤 Character Bible")
    cols = st.columns(min(3, max(1, len(chars))))
    for i, char in enumerate(chars):
        name = char.get("name", f"Character {i+1}")
        with cols[i % len(cols)]:
            st.markdown(f"**{name}**"); st.caption(char.get("description", ""))
            url = st.text_input("Reference image URL", key=f"vf_url_{i}")
            up = st.file_uploader("Or upload reference", type=["jpg","jpeg","png","webp"], key=f"vf_up_{i}")
            refs[name] = image_data_url(up) if up else url.strip()
            if up: st.image(up, width=140)

    st.subheader("🎞️ Scene plan"); scenes=[]; names=[c.get("name") for c in chars]
    for i, scene in enumerate(screenplay.get("scenes", [])):
        with st.expander(f"Scene {i+1} — {scene.get('title','Scene')}", expanded=i==0):
            setting=st.text_area("Setting",scene.get("setting",""),key=f"vf_set_{i}")
            selected=st.multiselect("Characters",names,default=scene.get("characters",[]),key=f"vf_chars_{i}")
            action=st.text_area("Action / camera",scene.get("action",""),key=f"vf_action_{i}")
            dialogue=st.text_area("Exact dialogue / narration",scene.get("dialogue",""),key=f"vf_dialogue_{i}")
            duration=st.slider("Seconds",4,15,int(scene.get("duration",6)),key=f"vf_dur_{i}")
            details="; ".join(c.get("name","")+": "+c.get("description","") for c in chars if c.get("name") in selected)
            prompt=f"""Photorealistic live-action scene. Realistic human faces, skin, eyes, hair, hands and movement. Cinematic natural lighting and camera motion. No cartoon, illustration, plastic skin, warped faces, extra fingers, text or baked-in subtitles. Maintain recurring-character identity using supplied references.
SETTING: {setting}
CHARACTERS: {', '.join(selected)}
IDENTITY: {details}
ACTION/CAMERA: {action}
EXACT SPOKEN DIALOGUE: {dialogue or '[No spoken dialogue]'}
Preserve every spoken word exactly. Do not paraphrase or invent dialogue. Synchronize facial expression and mouth movement to the words."""
            scenes.append({"prompt":prompt,"references":[refs[n] for n in selected if refs.get(n)],"duration":duration,"resolution":resolution,"ratio":ratio})
    missing=[n for n in names if not refs.get(n)]
    if missing: st.warning("Missing reference images: "+", ".join(missing)+". Identity consistency will be weaker.")
    if st.button("🚀 Generate Photoreal Video",type="primary",use_container_width=True,disabled=not api_key() or not scenes):
        workdir=Path(tempfile.mkdtemp(prefix="socialized_video_")); progress=st.progress(0); status=st.empty()
        try:
            def callback(scene_no,total,state,task):
                progress.progress(int((scene_no-1)/total*100)); status.info(f"Scene {scene_no}/{total}: {state}")
            final,task_ids=build_episode(scenes,workdir,progress=callback); progress.progress(100); status.success(f"Video complete — {len(task_ids)} scenes")
            data=final.read_bytes(); st.video(data); st.download_button("⬇️ Download MP4",data=data,file_name=f"{title}.mp4",mime="video/mp4",use_container_width=True)
            if active_campaign.get("id"):
                asset=upload_asset(str(final),str(active_campaign["id"]),asset_type="video"); st.session_state["video_asset"]=asset; st.session_state["last_campaign"]=active_campaign
                st.success("Video saved to Supabase and attached to the campaign. Go to YouTube to review/publish.")
            st.session_state["microdrama_task_ids"]=task_ids; st.session_state["microdrama_title"]=title
        except Exception as exc: st.error(f"Video generation failed: {exc}"); st.exception(exc)
