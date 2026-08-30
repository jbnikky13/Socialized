from __future__ import annotations
import os
import streamlit as st
from dotenv import load_dotenv
from services.research import research_topics
from services.ai import generate_package
from services.youtube import get_service, channel_info, upload_video
from services.x import XService
from services.campaigns import save_campaign, recent_campaigns
from services.media import upload_streamlit_file

load_dotenv()
st.set_page_config(page_title="Socialized", page_icon="📣", layout="wide")
st.title("📣 Socialized")
st.caption("One idea → AI campaign → X + YouTube → media → approval → publish → learn")
x_service = XService()

with st.sidebar:
    st.header("Creator setup")
    channel_name = st.text_input("YouTube channel", os.getenv("CHANNEL_NAME", "My YouTube Channel"))
    niche = st.text_input("Content niche", os.getenv("CHANNEL_NICHE", "Technology"))
    format_name = st.selectbox("YouTube format", ["long-form", "Short", "news", "explainer", "story"])
    approval_required = st.toggle("Require approval before publishing", True)
    st.divider(); st.subheader("Connections")
    if st.button("🔗 Connect / Check YouTube", use_container_width=True):
        try:
            info = channel_info(get_service()); st.success(f"Connected: {info['snippet']['title']}") if info else st.warning("No YouTube channel returned.")
        except Exception as e: st.error(str(e))
    st.success("X API configured") if x_service.configured() else st.warning("X API not configured")

research_tab, create_tab, queue_tab, media_tab, youtube_tab, x_tab, analytics_tab = st.tabs(["🔎 Research", "✍️ Create", "📅 Campaigns", "🎬 Media", "▶️ YouTube", "𝕏 X", "📊 Analytics"])

with research_tab:
    st.subheader("Find content opportunities"); query = st.text_input("Search topic", value=niche); limit = st.slider("Results", 5, 20, 10)
    if st.button("Research trends", type="primary"):
        with st.spinner("Collecting public RSS results..."): st.session_state["research"] = research_topics(query, limit)
    for item in st.session_state.get("research", []):
        with st.container(border=True):
            st.write(f"**{item['title']}**"); st.caption(item.get("source", "RSS")); st.write(item.get("summary", ""))
            if item.get("url"): st.write(item["url"])
            if st.button("Use topic", key=f"use_{hash(item['title'])}"): st.session_state["selected_topic"] = item["title"]

with create_tab:
    st.subheader("Create persistent X + YouTube campaign"); topic = st.text_input("Topic", value=st.session_state.get("selected_topic", "")); context = st.text_area("Research/source notes", height=100)
    if st.button("✨ Generate campaign", type="primary"):
        if not topic: st.warning("Enter a topic first.")
        else:
            try:
                with st.spinner("Generating content package..."): st.session_state["package"] = generate_package(topic, niche, format_name, context)
            except Exception as ex: st.error(str(ex))
    package = st.session_state.get("package")
    if package:
        titles = package.get("title_options", []); title = st.selectbox("YouTube title", titles if titles else [package.get("idea", topic)])
        hook = st.text_area("Hook", package.get("hook", ""), height=80); script = st.text_area("YouTube script", package.get("script", ""), height=280)
        description = st.text_area("YouTube description", package.get("description", ""), height=150); tags = st.text_input("YouTube tags", ", ".join(package.get("tags", []))); thumbnail = st.text_input("Thumbnail text", package.get("thumbnail_text", ""))
        x_posts = [p.strip() for p in st.text_area("X posts — one per line", "\n".join(package.get("x_posts", []) or [hook or title]), height=150).splitlines() if p.strip()]
        if st.button("💾 Save campaign to Supabase", type="primary"):
            try:
                pack = dict(package); pack.update({"title": title, "script": hook + "\n\n" + script, "description": description, "tags": [x.strip() for x in tags.split(",") if x.strip()], "thumbnail_text": thumbnail, "x_posts": x_posts})
                campaign = save_campaign(title, niche, pack); st.session_state["last_campaign"] = campaign; st.success(f"Campaign saved: {campaign['id']}"); st.session_state.pop("package", None)
            except Exception as ex: st.error(str(ex))

with queue_tab:
    st.subheader("Persistent campaigns")
    try:
        campaigns = recent_campaigns()
        if not campaigns: st.info("No campaigns saved yet.")
        for campaign in campaigns:
            with st.expander(f"{campaign['name']} · {campaign['status']}"):
                st.write(f"Niche: {campaign.get('niche', '')}"); st.caption(campaign.get('created_at', ''))
    except Exception as ex: st.warning(f"Supabase is not configured: {ex}")

with media_tab:
    st.subheader("🎬 Campaign media library")
    campaign = st.session_state.get("last_campaign")
    if not campaign: st.info("Save a campaign first, then upload its video or thumbnail here.")
    else:
        st.success(f"Active campaign: {campaign['name']}")
        uploaded = st.file_uploader("Upload finished video", type=["mp4", "mov", "webm", "m4v"], key="campaign_video")
        if uploaded and st.button("☁️ Store video in Supabase"):
            try:
                asset = upload_streamlit_file(uploaded, campaign["id"], "video"); st.session_state["video_asset"] = asset; st.success("Video stored in Supabase Storage.")
            except Exception as ex: st.error(str(ex))
        thumb = st.file_uploader("Upload thumbnail", type=["png", "jpg", "jpeg", "webp"], key="campaign_thumb")
        if thumb and st.button("☁️ Store thumbnail in Supabase"):
            try: st.success("Thumbnail stored: " + upload_streamlit_file(thumb, campaign["id"], "thumbnail")["public_url"])
            except Exception as ex: st.error(str(ex))
        if st.session_state.get("video_asset"): st.write("Stored video:", st.session_state["video_asset"].get("public_url", ""))

with youtube_tab:
    st.subheader("▶️ YouTube Publisher")
    st.write("Upload a campaign video to Supabase Storage, then select it here for publishing.")
    video_asset = st.session_state.get("video_asset")
    if video_asset: st.success("Campaign video is ready in Supabase Storage.")
    else: st.info("No campaign video stored yet. Use the Media tab first.")
    yt_title = st.text_input("Video title", value=st.session_state.get("last_campaign", {}).get("name", "")); yt_description = st.text_area("Description", height=140); yt_tags = st.text_input("Tags, comma separated"); privacy = st.selectbox("Visibility", ["private", "unlisted", "public"])
    st.caption("YouTube API uploads require a local file, so the app downloads the selected Storage asset temporarily during publishing.")
    if st.button("📤 Upload campaign to YouTube", type="primary"):
        if approval_required and not st.session_state.get("yt_approval"): st.warning("Approve the campaign below before publishing.")
        elif not video_asset: st.warning("Upload a video to Supabase Storage first.")
        else:
            try:
                import requests
                data = requests.get(video_asset["public_url"], timeout=120); data.raise_for_status(); temp = "/tmp/socialized_upload.mp4"; open(temp, "wb").write(data.content)
                video_id = upload_video(get_service(), temp, yt_title, yt_description, [x.strip() for x in yt_tags.split(",") if x.strip()], privacy=privacy); st.success(f"Uploaded to YouTube. Video ID: {video_id}")
            except Exception as ex: st.error(str(ex))
    st.session_state["yt_approval"] = st.checkbox("I approve this campaign for YouTube publishing", value=st.session_state.get("yt_approval", False))

with x_tab:
    st.subheader("𝕏 Publisher"); x_text = st.text_area("Post", max_chars=280, height=100); st.caption(f"{len(x_text)}/280 characters")
    if st.button("Post to X", type="primary"):
        if not x_service.configured(): st.error("Set X_ACCESS_TOKEN in secrets first.")
        elif not x_text.strip(): st.warning("Enter a post.")
        else:
            try: st.success(f"Posted to X: {x_service.create_post(x_text.strip()).get('data', {}).get('id', 'success')}")
            except Exception as ex: st.error(str(ex))
    st.divider(); st.subheader("Thread publisher"); thread_text = st.text_area("Thread — one post per line", height=180)
    if st.button("Publish thread"):
        posts = [x.strip() for x in thread_text.splitlines() if x.strip()]
        if not posts: st.warning("Add at least one post.")
        elif any(len(x) > 280 for x in posts): st.error("Every post must be 280 characters or fewer.")
        elif not x_service.configured(): st.error("Set X_ACCESS_TOKEN first.")
        else:
            try: st.success(f"Published {len(x_service.create_thread(posts))} posts as a thread.")
            except Exception as ex: st.error(str(ex))

with analytics_tab:
    st.subheader("YouTube channel")
    if st.button("Refresh YouTube stats"):
        try:
            info = channel_info(get_service())
            if info:
                stats = info.get("statistics", {}); a,b,c = st.columns(3); a.metric("Subscribers", stats.get("subscriberCount", "Hidden")); b.metric("Views", stats.get("viewCount", "0")); c.metric("Videos", stats.get("videoCount", "0"))
        except Exception as ex: st.error(str(ex))

st.divider(); st.caption("Socialized uses official platform APIs. Keep approval enabled until automated publishing is tested.")
