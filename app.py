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
from services.auto_media import build_campaign_media

load_dotenv()
st.set_page_config(page_title="Socialized", page_icon="📣", layout="wide")
st.title("📣 Socialized")
st.caption("One idea → AI campaign → automatic media → X + YouTube")
x_service = XService()

with st.sidebar:
    st.header("Creator setup")
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
    st.subheader("Create campaign"); topic = st.text_input("Topic", value=st.session_state.get("selected_topic", "")); context = st.text_area("Research/source notes", height=100)
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
        if st.button("🚀 Save + build media", type="primary"):
            try:
                pack = dict(package); pack.update({"title": title, "script": hook + "\n\n" + script, "description": description, "tags": [x.strip() for x in tags.split(",") if x.strip()], "thumbnail_text": thumbnail, "x_posts": x_posts})
                campaign = save_campaign(title, niche, pack); st.session_state["last_campaign"] = campaign
                with st.spinner("Creating free voiceover, thumbnail and MP4..."):
                    assets = build_campaign_media(title, pack["script"])
                    st.session_state["generated_assets"] = assets
                    with open(assets["video"], "rb") as vf: video_asset = upload_streamlit_file(vf, campaign["id"], "video")
                    with open(assets["thumbnail"], "rb") as tf: thumb_asset = upload_streamlit_file(tf, campaign["id"], "thumbnail")
                    st.session_state["video_asset"] = video_asset; st.session_state["thumbnail_asset"] = thumb_asset
                st.success("Campaign saved and media generated + stored in Supabase Storage."); st.session_state.pop("package", None)
            except Exception as ex: st.error(str(ex))

with queue_tab:
    st.subheader("Persistent campaigns")
    try:
        campaigns = recent_campaigns()
        if not campaigns: st.info("No campaigns saved yet.")
        for campaign in campaigns:
            with st.expander(f"{campaign['name']} · {campaign['status']}"): st.write(f"Niche: {campaign.get('niche', '')}"); st.caption(campaign.get('created_at', ''))
    except Exception as ex: st.warning(f"Supabase is not configured: {ex}")

with media_tab:
    st.subheader("🎬 Generated media")
    if st.session_state.get("generated_assets"):
        st.success("Automatic media generation complete.")
        st.video(st.session_state["generated_assets"]["video"]); st.image(st.session_state["generated_assets"]["thumbnail"])
    else: st.info("Generate a campaign to automatically create its media.")

with youtube_tab:
    st.subheader("▶️ YouTube Publisher")
    video_asset = st.session_state.get("video_asset")
    if video_asset: st.success("Campaign video is ready in Supabase Storage.")
    else: st.warning("No campaign video is ready yet. Generate one from Create.")
    yt_title = st.text_input("Video title", value=st.session_state.get("last_campaign", {}).get("name", "")); yt_description = st.text_area("Description", height=140); yt_tags = st.text_input("Tags, comma separated"); privacy = st.selectbox("Visibility", ["private", "unlisted", "public"])
    st.session_state["yt_approval"] = st.checkbox("I approve this campaign for YouTube publishing", value=st.session_state.get("yt_approval", False))
    if st.button("📤 Publish to YouTube", type="primary"):
        if approval_required and not st.session_state["yt_approval"]: st.warning("Approval required before publishing.")
        elif not video_asset: st.warning("Generate a campaign video first.")
        else:
            try:
                import requests
                data = requests.get(video_asset["public_url"], timeout=180); data.raise_for_status(); temp = "/tmp/socialized_upload.mp4"
                with open(temp, "wb") as f: f.write(data.content)
                video_id = upload_video(get_service(), temp, yt_title, yt_description, [x.strip() for x in yt_tags.split(",") if x.strip()], privacy=privacy); st.success(f"Uploaded to YouTube. Video ID: {video_id}")
            except Exception as ex: st.error(str(ex))

with x_tab:
    st.subheader("𝕏 Publisher"); x_text = st.text_area("Post", max_chars=280, height=100)
    if st.button("Post to X", type="primary"):
        if not x_service.configured(): st.error("Set X_ACCESS_TOKEN in secrets first.")
        elif not x_text.strip(): st.warning("Enter a post.")
        else:
            try: st.success(f"Posted to X: {x_service.create_post(x_text.strip()).get('data', {}).get('id', 'success')}")
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
