from __future__ import annotations
import os
import streamlit as st
from dotenv import load_dotenv
from services.research import research_topics
from services.ai import generate_package
from services.youtube import get_service, channel_info, upload_video, begin_oauth, finish_oauth
from services.x import XService
from services.campaigns import save_campaign, recent_campaigns, reuse_campaign
from services import media
from services.auto_media import build_campaign_media

load_dotenv()
st.set_page_config(page_title="Socialized", page_icon="📣", layout="wide")
st.title("📣 Socialized")
st.caption("Campaign → script → title → description → video → preview → approval → YouTube")
x_service = XService()


def reused_content_items():
    return st.session_state.get("reused_content", [])


def content_value(platform, content_type=None, fallback=""):
    for item in reused_content_items():
        if item.get("platform") == platform and (content_type is None or item.get("content_type") == content_type) and (item.get("body") or "").strip():
            return item["body"]
    return fallback


# Complete OAuth callback before rendering publisher controls.
params = st.query_params
if params.get("code") and st.session_state.get("youtube_oauth_state"):
    try:
        finish_oauth(params["code"], st.session_state.pop("youtube_oauth_state"))
        st.query_params.clear()
        st.success("YouTube connected successfully. The selected Google account is now authorized.")
    except Exception as ex:
        st.error(f"YouTube authorization failed: {ex}")

with st.sidebar:
    st.header("Creator setup")
    channel_name = st.text_input("YouTube channel", os.getenv("CHANNEL_NAME", "My YouTube Channel"))
    niche = st.text_input("Content niche", os.getenv("CHANNEL_NICHE", "Technology"))
    format_name = st.selectbox("YouTube format", ["long-form", "Short", "news", "explainer", "story"])
    approval_required = st.toggle("Require approval before publishing", True)
    st.divider()
    st.subheader("Connections")
    st.caption("YouTube authorization is requested at publishing time so you can choose the Google account you want to use.")
    if st.button("🔗 Choose YouTube account", use_container_width=True):
        try:
            url, state = begin_oauth()
            st.session_state["youtube_oauth_state"] = state
            st.link_button("Choose Google account →", url, use_container_width=True)
        except Exception as e:
            st.error(str(e))
    if st.button("Check YouTube connection", use_container_width=True):
        try:
            info = channel_info(get_service())
            if info:
                st.success(f"Connected: {info['snippet']['title']}")
            else:
                st.warning("No YouTube channel returned.")
        except Exception as e:
            st.error(str(e))
    st.success("X API configured") if x_service.configured() else st.warning("X API not configured")

research_tab, create_tab, queue_tab, media_tab, youtube_tab, x_tab, analytics_tab = st.tabs(["🔎 Research", "✍️ Create", "📅 Campaigns", "🎬 Media", "▶️ YouTube", "𝕏 X", "📊 Analytics"])

with research_tab:
    st.subheader("Find content opportunities")
    query = st.text_input("Search topic", value=niche)
    limit = st.slider("Results", 5, 20, 10)
    if st.button("Research trends", type="primary"):
        with st.spinner("Collecting public RSS results..."):
            st.session_state["research"] = research_topics(query, limit)
    for item in st.session_state.get("research", []):
        with st.container(border=True):
            st.write(f"**{item['title']}**")
            st.caption(item.get("source", "RSS"))
            st.write(item.get("summary", ""))
            if item.get("url"):
                st.write(item["url"])
            if st.button("Use topic", key=f"use_{hash(item['title'])}"):
                st.session_state["selected_topic"] = item["title"]

with create_tab:
    st.subheader("Create persistent X + YouTube campaign")
    topic = st.text_input("Topic", value=st.session_state.get("selected_topic", ""))
    context = st.text_area("Research/source notes", height=100)
    if st.button("✨ Generate campaign", type="primary"):
        if not topic:
            st.warning("Enter a topic first.")
        else:
            try:
                with st.spinner("Generating content package..."):
                    st.session_state["package"] = generate_package(topic, niche, format_name, context)
            except Exception as ex:
                st.error(str(ex))
    package = st.session_state.get("package")
    if package:
        titles = package.get("title_options", [])
        title = st.selectbox("YouTube title", titles if titles else [package.get("idea", topic)])
        hook = st.text_area("Hook", package.get("hook", ""), height=80)
        script = st.text_area("YouTube script", package.get("script", ""), height=280)
        description = st.text_area("YouTube description", package.get("description", ""), height=150)
        tags = st.text_input("YouTube tags", ", ".join(package.get("tags", [])))
        thumbnail = st.text_input("Thumbnail text", package.get("thumbnail_text", ""))
        x_posts = [p.strip() for p in st.text_area("X posts — one per line", "\n".join(package.get("x_posts", []) or [hook or title]), height=150).splitlines() if p.strip()]
        if st.button("💾 Save campaign to Supabase", type="primary"):
            try:
                pack = dict(package)
                pack.update({"title": title, "script": script.strip() or hook.strip(), "description": description.strip(), "tags": [x.strip() for x in tags.split(",") if x.strip()], "thumbnail_text": thumbnail, "x_posts": x_posts})
                if not pack["script"].strip():
                    raise ValueError("The generated YouTube script is empty. Generate the campaign again before saving.")
                if not pack["description"].strip():
                    raise ValueError("The generated YouTube description is empty. Generate the campaign again before saving.")
                campaign = save_campaign(title, niche, pack)
                campaign["script"] = pack["script"]
                campaign["description"] = pack["description"]
                campaign["title"] = title
                campaign["tags"] = pack["tags"]
                st.session_state["last_campaign"] = campaign
                st.session_state["reused_content"] = [{"platform": "youtube", "content_type": "video", "title": title, "body": pack["script"]}, {"platform": "youtube", "content_type": "description", "title": title, "body": pack["description"]}] + [{"platform": "x", "content_type": "post", "title": title, "body": p} for p in x_posts]
                st.success(f"Campaign saved: {campaign['id']}")
                st.session_state.pop("package", None)
            except Exception as ex:
                st.error(str(ex))

with queue_tab:
    st.subheader("Persistent campaigns")
    try:
        campaigns = recent_campaigns()
        if not campaigns:
            st.info("No campaigns saved yet.")
        for campaign in campaigns:
            with st.expander(f"{campaign['name']} · {campaign['status']}"):
                st.write(f"Niche: {campaign.get('niche', '')}")
                st.caption(campaign.get('created_at', ''))
                c1, c2, c3 = st.columns(3)
                if c1.button("♻️ Reuse", key=f"reuse_{campaign['id']}"):
                    try:
                        loaded = reuse_campaign(campaign["id"])
                        st.session_state["last_campaign"] = loaded["campaign"]
                        st.session_state["reused_content"] = loaded["content"]
                        st.session_state.pop("video_asset", None)
                        st.success("Campaign loaded for reuse.")
                    except Exception as ex:
                        st.error(str(ex))
                if c2.button("🎬 Media", key=f"media_{campaign['id']}"):
                    try:
                        loaded = reuse_campaign(campaign["id"])
                        st.session_state["last_campaign"] = loaded["campaign"]
                        st.session_state["reused_content"] = loaded["content"]
                        st.session_state.pop("video_asset", None)
                        st.success("Campaign selected for media production.")
                    except Exception as ex:
                        st.error(str(ex))
                if c3.button("▶️ Publish", key=f"publish_{campaign['id']}"):
                    try:
                        loaded = reuse_campaign(campaign["id"])
                        st.session_state["last_campaign"] = loaded["campaign"]
                        st.session_state["reused_content"] = loaded["content"]
                        st.success("Campaign loaded for publishing.")
                    except Exception as ex:
                        st.error(str(ex))
                if st.session_state.get("last_campaign", {}).get("id") == campaign["id"] and st.session_state.get("reused_content"):
                    for item in st.session_state["reused_content"]:
                        st.write(f"**{item.get('platform', '').upper()} · {item.get('content_type', '')}** — {item.get('title', '')}")
    except Exception as ex:
        st.warning(f"Supabase is not configured: {ex}")

with media_tab:
    st.subheader("🎬 Campaign media")
    campaign = st.session_state.get("last_campaign")
    if not campaign:
        st.info("Select Reuse or Media on a saved campaign first.")
    else:
        st.success(f"Active campaign: {campaign['name']}")
        saved_items = st.session_state.get("reused_content", [])
        youtube_item = next((x for x in saved_items if x.get("platform") == "youtube" and x.get("content_type") == "video" and (x.get("body") or "").strip()), None)
        script_override = (youtube_item or {}).get("body") or campaign.get("script")
        if not script_override:
            st.warning("No saved YouTube script was found for this campaign.")
        if st.button("🤖 Generate complete video automatically", type="primary"):
            try:
                if not script_override:
                    raise ValueError("No saved YouTube script was found for this campaign. Please generate and save a YouTube script first.")
                with st.spinner("Generating voiceover, thumbnail and MP4..."):
                    result = build_campaign_media(campaign, script=script_override)
                st.session_state["video_asset"] = result.get("video_asset")
                st.success("Video generated and stored in Supabase Storage.")
            except Exception as ex:
                st.error(str(ex))
        uploaded = st.file_uploader("Or upload a finished video", type=["mp4", "mov", "webm", "m4v"], key="campaign_video")
        if uploaded and st.button("☁️ Store video in Supabase"):
            try:
                st.session_state["video_asset"] = media.upload_streamlit_file(uploaded, campaign["id"], "video")
                st.success("Video stored in Supabase Storage.")
            except Exception as ex:
                st.error(str(ex))

        video_asset = st.session_state.get("video_asset")
        if video_asset and video_asset.get("public_url"):
            st.divider()
            st.subheader("🎥 Video Preview")
            st.video(video_asset["public_url"])
            try:
                import requests
                preview_data = requests.get(video_asset["public_url"], timeout=120)
                preview_data.raise_for_status()
                st.download_button("⬇️ Download video", data=preview_data.content, file_name=f"{campaign.get('name', 'socialized_video')}.mp4", mime="video/mp4", use_container_width=True)
            except Exception as ex:
                st.warning(f"Download preview unavailable: {ex}")
            st.caption("The video above is the exact asset that will be sent to YouTube after approval.")

with youtube_tab:
    st.subheader("▶️ Publish to YouTube")
    campaign = st.session_state.get("last_campaign")
    video_asset = st.session_state.get("video_asset")
    selected = st.session_state.get("reused_content", [])

    if not campaign:
        st.info("Select a saved campaign first.")
    else:
        if video_asset and video_asset.get("public_url"):
            st.success("Campaign video is ready.")
            st.video(video_asset["public_url"])
        else:
            st.warning("Generate or upload a video in Media before publishing.")

        st.subheader("Edit metadata")
        yt_title = st.text_input("Title", value=campaign.get("title", campaign.get("name", "")))
        generated_description = next((x.get("body", "") for x in selected if x.get("platform") == "youtube" and x.get("content_type") == "description"), campaign.get("description", ""))
        yt_description = st.text_area("Description", value=generated_description, height=180)
        yt_tags = st.text_input("Tags, comma separated", value=", ".join(campaign.get("tags", [])))
        privacy = st.selectbox("Visibility", ["private", "unlisted", "public"])

        st.subheader("Approval")
        approved = st.checkbox("I approve this campaign for YouTube publishing", value=st.session_state.get("yt_approval", False))
        st.session_state["yt_approval"] = approved

        if st.button("📤 Publish to YouTube", type="primary"):
            if approval_required and not approved:
                st.warning("Approve the campaign before publishing.")
            elif not video_asset or not video_asset.get("public_url"):
                st.warning("Generate or upload a video in Media first.")
            elif not yt_title.strip():
                st.warning("Add a YouTube title before publishing.")
            elif not yt_description.strip():
                st.warning("Add a video description before publishing.")
            else:
                try:
                    youtube = get_service()
                except Exception:
                    try:
                        url, state = begin_oauth()
                        st.session_state["youtube_oauth_state"] = state
                        st.info("Choose the Google account/YouTube channel you want this video published to.")
                        st.link_button("🔐 Choose Google account & authorize YouTube →", url, use_container_width=True)
                    except Exception as ex:
                        st.error(f"Could not start YouTube authorization: {ex}")
                else:
                    try:
                        import requests
                        data = requests.get(video_asset["public_url"], timeout=120)
                        data.raise_for_status()
                        temp = "/tmp/socialized_upload.mp4"
                        with open(temp, "wb") as fh:
                            fh.write(data.content)
                        video_id = upload_video(youtube, temp, yt_title.strip(), yt_description.strip(), [x.strip() for x in yt_tags.split(",") if x.strip()], privacy=privacy)
                        st.success(f"Uploaded to YouTube successfully. Video ID: {video_id}")
                    except Exception as ex:
                        st.error(str(ex))

with x_tab:
    st.subheader("𝕏 Publisher")
    default_x = content_value("x", fallback="")
    x_text = st.text_area("Post", value=default_x, max_chars=280, height=100)
    st.caption(f"{len(x_text)}/280 characters")
    if st.button("Post to X", type="primary"):
        if not x_service.configured():
            st.error("Set X_ACCESS_TOKEN in secrets first.")
        elif not x_text.strip():
            st.warning("Enter a post.")
        else:
            try:
                st.success(f"Posted to X: {x_service.create_post(x_text.strip()).get('data', {}).get('id', 'success')}")
            except Exception as ex:
                st.error(str(ex))
    st.divider()
    st.subheader("Thread publisher")
    thread_text = st.text_area("Thread — one post per line", height=180)
    if st.button("Publish thread"):
        posts = [x.strip() for x in thread_text.splitlines() if x.strip()]
        if not posts:
            st.warning("Add at least one post.")
        elif any(len(x) > 280 for x in posts):
            st.error("Every post must be 280 characters or fewer.")
        elif not x_service.configured():
            st.error("Set X_ACCESS_TOKEN first.")
        else:
            try:
                st.success(f"Published {len(x_service.create_thread(posts))} posts as a thread.")
            except Exception as ex:
                st.error(str(ex))

with analytics_tab:
    st.subheader("YouTube channel")
    if st.button("Refresh YouTube stats"):
        try:
            info = channel_info(get_service())
            if info:
                stats = info.get("statistics", {})
                a, b, c = st.columns(3)
                a.metric("Subscribers", stats.get("subscriberCount", "Hidden"))
                b.metric("Views", stats.get("viewCount", "0"))
                c.metric("Videos", stats.get("videoCount", "0"))
        except Exception as ex:
            st.error(str(ex))

st.divider()
st.caption("Socialized uses official platform APIs. You choose the Google account at authorization time, review the generated media and metadata, approve, then publish.")
