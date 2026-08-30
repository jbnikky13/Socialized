from __future__ import annotations
import os
import streamlit as st
from dotenv import load_dotenv

from services.database import init_db, add_content, list_content, update_content, delete_content, decode_tags
from services.research import research_topics
from services.ai import generate_package
from services.youtube import get_service, channel_info, upload_video
from services.x import XService

load_dotenv()
init_db()
st.set_page_config(page_title="Socialized", page_icon="📣", layout="wide")

st.title("📣 Socialized")
st.caption("One idea → AI content pack → X + YouTube → review → publish")

x_service = XService()

with st.sidebar:
    st.header("Creator setup")
    channel_name = st.text_input("YouTube channel", os.getenv("CHANNEL_NAME", "My YouTube Channel"))
    niche = st.text_input("Content niche", os.getenv("CHANNEL_NICHE", "Technology"))
    format_name = st.selectbox("YouTube format", ["long-form", "Short", "news", "explainer", "story"])
    approval_required = st.toggle("Require approval before publishing", os.getenv("APPROVAL_REQUIRED", "true").lower() == "true")
    st.divider()
    st.subheader("Connections")
    if st.button("🔗 Connect YouTube", use_container_width=True):
        try:
            info = channel_info(get_service())
            st.session_state["youtube_connected"] = bool(info)
            if info:
                st.success(f"Connected: {info['snippet']['title']}")
        except Exception as e:
            st.error(str(e))
    st.caption("X posting requires an X API user access token in X_ACCESS_TOKEN.")
    if x_service.configured():
        st.success("X API configured")
    else:
        st.warning("X API not configured")

items = list_content()
a, b, c, d, e = st.columns(5)
a.metric("Ideas", len(items))
b.metric("Drafts", sum(x["status"] == "draft" for x in items))
c.metric("Approved", sum(x["status"] == "approved" for x in items))
d.metric("Published", sum(x["status"] == "published" for x in items))
e.metric("Failed", sum(x["status"] == "failed" for x in items))

research_tab, create_tab, queue_tab, x_tab, analytics_tab = st.tabs(["🔎 Research", "✍️ Create", "📅 Queue", "𝕏 X", "📊 Analytics"])

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
                st.success("Topic selected.")

with create_tab:
    st.subheader("Create one content pack for both platforms")
    topic = st.text_input("Topic", value=st.session_state.get("selected_topic", ""))
    context = st.text_area("Research/source notes", height=100)
    if st.button("✨ Generate X + YouTube package", type="primary"):
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

        st.markdown("### 𝕏 X content")
        default_x = package.get("x_posts", [])
        if not default_x:
            default_x = [hook or title]
        x_posts_text = st.text_area("X posts — one post per line", "\n".join(default_x), height=150)
        x_posts = [p.strip() for p in x_posts_text.splitlines() if p.strip()]
        for i, post in enumerate(x_posts, 1):
            if len(post) > 280:
                st.warning(f"X post {i} is {len(post)} characters; it must be 280 characters or fewer.")

        uploaded = st.file_uploader("Attach finished MP4 for YouTube", type=["mp4", "mov", "m4v"])
        schedule = st.datetime_input("Schedule time (optional)", value=None)
        if st.button("Save content pack to queue"):
            path = ""
            if uploaded:
                os.makedirs("media", exist_ok=True)
                path = os.path.join("media", uploaded.name)
                with open(path, "wb") as f:
                    f.write(uploaded.getbuffer())
            metadata = description + "\n\nThumbnail: " + thumbnail + "\n\nX POSTS:\n" + "\n---\n".join(x_posts)
            item_id = add_content(topic, title, hook + "\n\n" + script, metadata,
                                  [x.strip() for x in tags.split(",") if x.strip()], path,
                                  schedule.isoformat() if schedule else "")
            st.success(f"Saved #{item_id}. Review it in Queue.")
            st.session_state.pop("package", None)

with queue_tab:
    st.subheader("Unified publishing queue")
    status_filter = st.selectbox("Filter", ["all", "draft", "approved", "published", "failed"])
    rows = list_content(None if status_filter == "all" else status_filter)
    for row in rows:
        with st.expander(f"#{row['id']} · {row['title'] or row['topic']} · {row['status'].upper()}"):
            st.write(f"**Topic:** {row['topic']}")
            st.text_area("YouTube script", row.get("script", ""), height=150, key=f"script_{row['id']}")
            st.write(f"**Scheduled:** {row.get('scheduled_at') or 'Not scheduled'}")
            if row.get("video_path"):
                st.caption(f"Video: {row['video_path']}")
            c1, c2, c3 = st.columns(3)
            if row["status"] == "draft" and c1.button("Approve", key=f"approve_{row['id']}"):
                update_content(row["id"], status="approved")
                st.rerun()
            if row["status"] == "approved" and c2.button("Publish YouTube", key=f"yt_{row['id']}"):
                if not row.get("video_path"):
                    st.warning("Attach an MP4 before publishing.")
                else:
                    try:
                        video_id = upload_video(get_service(), row["video_path"], row["title"], row["description"], decode_tags(row), publish_at=row.get("scheduled_at") or None)
                        update_content(row["id"], status="published", youtube_id=video_id)
                        st.success(f"YouTube published/uploaded: {video_id}")
                        st.rerun()
                    except Exception as ex:
                        update_content(row["id"], status="failed")
                        st.error(str(ex))
            if c3.button("Delete", key=f"delete_{row['id']}"):
                delete_content(row["id"])
                st.rerun()

with x_tab:
    st.subheader("𝕏 Publisher")
    st.write("Publish a single post or a thread from approved content.")
    x_text = st.text_area("Post", max_chars=280, height=100)
    st.caption(f"{len(x_text)}/280 characters")
    if st.button("Post to X", type="primary"):
        if not x_service.configured():
            st.error("Set X_ACCESS_TOKEN in your deployment secrets first.")
        elif not x_text.strip():
            st.warning("Enter a post.")
        else:
            try:
                result = x_service.create_post(x_text.strip())
                st.success(f"Posted to X: {result.get('data', {}).get('id', 'success')}")
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
            st.error("Every X post must be 280 characters or fewer.")
        elif not x_service.configured():
            st.error("Set X_ACCESS_TOKEN in your deployment secrets first.")
        else:
            try:
                results = x_service.create_thread(posts)
                st.success(f"Published {len(results)} posts as a thread.")
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
                st.write(info["snippet"].get("description", ""))
        except Exception as ex:
            st.error(str(ex))

st.divider()
st.caption("Socialized uses official platform APIs. Publish only content and media you have rights to use, and review AI output before automated publishing.")
