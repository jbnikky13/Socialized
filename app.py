from __future__ import annotations
import os
from datetime import datetime, timezone
import streamlit as st
from dotenv import load_dotenv

from services.database import init_db, add_content, list_content, get_content, update_content, delete_content, decode_tags
from services.research import research_topics
from services.ai import generate_package
from services.youtube import get_service, channel_info, upload_video

load_dotenv()
init_db()
st.set_page_config(page_title="YouTube Content Bot", page_icon="🎬", layout="wide")

st.title("🎬 YouTube Content Bot")
st.caption("Research → Generate → Review → Publish → Learn")

with st.sidebar:
    st.header("Channel setup")
    channel_name = st.text_input("Channel name", os.getenv("CHANNEL_NAME", "My YouTube Channel"))
    niche = st.text_input("Niche", os.getenv("CHANNEL_NICHE", "Technology"))
    format_name = st.selectbox("Default format", ["long-form", "Short", "news", "explainer", "story"])
    st.divider()
    if st.button("🔗 Connect YouTube", use_container_width=True):
        try:
            yt = get_service()
            info = channel_info(yt)
            if info:
                st.session_state["youtube_connected"] = True
                st.success(f"Connected: {info['snippet']['title']}")
            else:
                st.warning("Google authorization succeeded, but no channel was returned.")
        except Exception as e:
            st.error(str(e))
    if st.session_state.get("youtube_connected"):
        st.success("YouTube connected")

# Dashboard metrics
items = list_content()
col1, col2, col3, col4 = st.columns(4)
col1.metric("Ideas", len(items))
col2.metric("Drafts", sum(x["status"] == "draft" for x in items))
col3.metric("Approved", sum(x["status"] == "approved" for x in items))
col4.metric("Published", sum(x["status"] == "published" for x in items))

research_tab, create_tab, queue_tab, analytics_tab = st.tabs(["🔎 Research", "✍️ Create", "📅 Queue", "📊 Channel"])

with research_tab:
    st.subheader("Find topics")
    query = st.text_input("Search topic", value=niche, key="research_query")
    limit = st.slider("Number of results", 5, 20, 10)
    if st.button("Research trends", type="primary"):
        with st.spinner("Collecting public RSS results..."):
            st.session_state["research"] = research_topics(query, limit)
    for item in st.session_state.get("research", []):
        with st.container(border=True):
            st.write(f"**{item['title']}**")
            st.caption(item.get("source", "RSS"))
            st.write(item.get("summary", ""))
            st.write(item.get("url", ""))
            if st.button("Use topic", key=f"use_{hash(item['title'])}"):
                st.session_state["selected_topic"] = item["title"]
                st.success("Topic selected. Open Create to continue.")

with create_tab:
    st.subheader("Create a video package")
    topic = st.text_input("Topic", value=st.session_state.get("selected_topic", ""))
    context = st.text_area("Optional research/source notes", height=120)
    if st.button("✨ Generate with AI", type="primary"):
        if not topic:
            st.warning("Enter a topic first.")
        else:
            try:
                with st.spinner("Generating script and metadata..."):
                    st.session_state["package"] = generate_package(topic, niche, format_name, context)
            except Exception as e:
                st.error(str(e))

    package = st.session_state.get("package")
    if package:
        titles = package.get("title_options", [])
        title = st.selectbox("Title", titles if titles else [package.get("idea", topic)])
        hook = st.text_area("Hook", package.get("hook", ""), height=100)
        script = st.text_area("Script", package.get("script", ""), height=320)
        description = st.text_area("Description", package.get("description", ""), height=180)
        tags = st.text_input("Tags", ", ".join(package.get("tags", [])))
        thumbnail = st.text_input("Thumbnail text", package.get("thumbnail_text", ""))
        uploaded = st.file_uploader("Attach finished MP4 (optional)", type=["mp4", "mov", "m4v"])
        schedule = st.datetime_input("Schedule time (optional)", value=None)
        if st.button("Save to content queue"):
            path = ""
            if uploaded:
                os.makedirs("media", exist_ok=True)
                path = os.path.join("media", uploaded.name)
                with open(path, "wb") as f:
                    f.write(uploaded.getbuffer())
            item_id = add_content(topic, title, hook + "\n\n" + script, description + "\n\nThumbnail: " + thumbnail,
                                 [x.strip() for x in tags.split(",") if x.strip()], path,
                                 schedule.isoformat() if schedule else "")
            st.success(f"Saved item #{item_id} as a draft.")
            st.session_state.pop("package", None)

with queue_tab:
    st.subheader("Content queue")
    status_filter = st.selectbox("Filter", ["all", "draft", "approved", "published", "failed"])
    rows = list_content(None if status_filter == "all" else status_filter)
    for row in rows:
        with st.expander(f"#{row['id']} · {row['title'] or row['topic']} · {row['status'].upper()}"):
            st.write(f"**Topic:** {row['topic']}")
            st.text_area("Script", row.get("script", ""), height=160, key=f"script_{row['id']}")
            st.write(f"**Scheduled:** {row.get('scheduled_at') or 'Not scheduled'}")
            if row.get("video_path"):
                st.caption(f"Video: {row['video_path']}")
            c1, c2, c3 = st.columns(3)
            if row["status"] == "draft" and c1.button("Approve", key=f"approve_{row['id']}"):
                update_content(row["id"], status="approved")
                st.rerun()
            if row["status"] == "approved" and c2.button("Publish", key=f"publish_{row['id']}"):
                if not row.get("video_path"):
                    st.warning("Attach an MP4 before publishing.")
                else:
                    try:
                        yt = get_service()
                        tags = decode_tags(row)
                        video_id = upload_video(yt, row["video_path"], row["title"], row["description"], tags,
                                                publish_at=row.get("scheduled_at") or None)
                        update_content(row["id"], status="published", youtube_id=video_id)
                        st.success(f"Published/uploaded: {video_id}")
                        st.rerun()
                    except Exception as e:
                        update_content(row["id"], status="failed")
                        st.error(str(e))
            if c3.button("Delete", key=f"delete_{row['id']}"):
                delete_content(row["id"])
                st.rerun()

with analytics_tab:
    st.subheader("YouTube channel")
    if st.button("Refresh channel stats"):
        try:
            yt = get_service()
            info = channel_info(yt)
            if info:
                stats = info.get("statistics", {})
                a, b, c = st.columns(3)
                a.metric("Subscribers", stats.get("subscriberCount", "Hidden"))
                b.metric("Views", stats.get("viewCount", "0"))
                c.metric("Videos", stats.get("videoCount", "0"))
                st.write(info["snippet"].get("description", ""))
        except Exception as e:
            st.error(str(e))

st.divider()
st.caption("Use only content and media you have rights to publish. Review AI output before publishing.")
