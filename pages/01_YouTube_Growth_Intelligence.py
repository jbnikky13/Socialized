from __future__ import annotations
import io
import textwrap
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from services.growth_intelligence import google_trends, youtube_opportunity, score_opportunity, headline_score
from services.ai import generate_package
from services.campaigns import save_campaign

st.set_page_config(page_title="YouTube Growth Intelligence", page_icon="🚀", layout="wide")
st.title("🚀 YouTube Growth Intelligence")
st.caption("Validate demand → score opportunity → optimize titles → build campaign → thumbnail")

if "growth_ideas" not in st.session_state:
    st.session_state.growth_ideas = []

with st.sidebar:
    st.header("Growth settings")
    geo = st.selectbox("Trend market", ["NG", "US", "GB", "CA", "AU", "IN"], index=0)
    niche = st.text_input("Channel niche", value="Technology")
    monetization = st.slider("Monetization potential", 0, 100, 70)
    competition = st.slider("Competition", 0, 100, 55, help="Higher = harder. Use your vidIQ competition estimate here when available.")
    freshness = st.slider("Freshness", 0, 100, 80)

st.subheader("1. Discover demand")
if st.button("🔥 Scan Google Trends", type="primary"):
    with st.spinner("Reading Google Trends Trending Now..."):
        st.session_state.trends = google_trends(geo, 20)

trends = st.session_state.get("trends", [])
if trends:
    for i, item in enumerate(trends):
        q = item["query"]
        with st.container(border=True):
            c1, c2, c3 = st.columns([5, 2, 2])
            c1.write(f"**{q}**")
            c1.caption(item.get("published", ""))
            if c2.button("Check YouTube", key=f"yt_{i}"):
                with st.spinner("Checking YouTube search results..."):
                    st.session_state[f"yt_{i}"] = youtube_opportunity(q, geo)
            if c3.button("Add idea", key=f"add_{i}"):
                if q not in [x["query"] for x in st.session_state.growth_ideas]:
                    st.session_state.growth_ideas.append({"query": q, "yt": st.session_state.get(f"yt_{i}", {})})
        yt = st.session_state.get(f"yt_{i}")
        if yt and yt.get("available"):
            median = yt.get("median_views", 0)
            # Normalize public result performance into a useful 0-100 proxy, not a vidIQ score.
            yt_score = min(100, 25 + (median / 100000) * 25 + min(len(yt.get("results", [])), 10) * 5)
            opp = score_opportunity(75, yt_score, monetization, competition, freshness)
            st.caption(f"YouTube opportunity proxy: {yt_score:.0f}/100 · Median result views: {median:,} · Overall opportunity: **{opp}/100**")
        elif yt and not yt.get("available"):
            st.caption(f"YouTube check unavailable: {yt.get('reason', 'unknown error')}")

st.divider()
st.subheader("2. Rank opportunities")
if st.session_state.growth_ideas:
    ranked = []
    for item in st.session_state.growth_ideas:
        yt = item.get("yt") or youtube_opportunity(item["query"], geo)
        median = yt.get("median_views", 0) if yt.get("available") else 0
        yt_score = min(100, 25 + (median / 100000) * 25 + min(len(yt.get("results", [])), 10) * 5)
        score = score_opportunity(75, yt_score, monetization, competition, freshness)
        ranked.append((score, item["query"], median))
    for rank, (score, query, median) in enumerate(sorted(ranked, reverse=True), 1):
        st.write(f"**#{rank} {query}** — {score}/100 · median result views {median:,}")
else:
    st.info("Add topics from the Trends scan to build your opportunity list.")

st.divider()
st.subheader("3. Headline lab")
seed = st.text_input("Topic/title seed", value=st.session_state.growth_ideas[0]["query"] if st.session_state.growth_ideas else "")
if st.button("✨ Generate high-converting title set"):
    if not seed:
        st.warning("Enter a topic first.")
    else:
        with st.spinner("Generating title candidates..."):
            pack = generate_package(seed, niche, "long-form", "Demand discovered from Google Trends. Generate original titles and content; do not claim an external headline analyzer score.")
        titles = pack.get("title_options", [])
        st.session_state.title_lab = sorted([(headline_score(t), t) for t in titles], reverse=True)
        st.session_state.generated_package = pack

for score, title in st.session_state.get("title_lab", []):
    st.write(f"**{score:.0f}/100** — {title}")

if st.session_state.get("generated_package"):
    pack = st.session_state.generated_package
    st.divider()
    st.subheader("4. Turn the winner into a campaign")
    titles = [t for _, t in st.session_state.get("title_lab", [])] or [pack.get("idea", seed)]
    selected_title = st.selectbox("Winning title", titles)
    context = st.text_area("Optional research context", height=90)
    if st.button("🚀 Build campaign package", type="primary"):
        with st.spinner("Building script, description, tags, X posts and Shorts..."):
            final = generate_package(selected_title, niche, "long-form", context or f"Topic: {seed}")
            final["title"] = selected_title
            st.session_state.final_package = final

final = st.session_state.get("final_package")
if final:
    st.text_area("Hook", final.get("hook", ""), height=80)
    st.text_area("Script", final.get("script", ""), height=260)
    st.text_area("Description", final.get("description", ""), height=140)
    if st.button("💾 Save to Socialized campaigns"):
        try:
            campaign = save_campaign(final.get("title", seed), niche, final)
            st.success(f"Campaign saved: {campaign['id']}. Open the Campaigns tab in Socialized to render and publish it.")
        except Exception as exc:
            st.error(f"Could not save campaign: {exc}")

st.divider()
st.subheader("5. Canva-style thumbnail builder")
thumb_title = st.text_input("Thumbnail headline", value=(st.session_state.get("title_lab", [(0, seed)])[0][1] if st.session_state.get("title_lab") else seed))
thumb_sub = st.text_input("Small supporting text", value="WATCH BEFORE YOU DECIDE")
subject = st.text_input("Subject / visual cue", value="high-impact technology visual")


def _font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def make_thumb(title: str, subtitle: str, subject: str) -> bytes:
    img = Image.new("RGB", (1280, 720), "#111827")
    draw = ImageDraw.Draw(img)
    # Clean creator-template layout: high contrast, large text, clear visual hierarchy.
    draw.rectangle((0, 0, 1280, 720), outline="#ffffff", width=4)
    draw.rounded_rectangle((55, 55, 1225, 665), radius=30, outline="#374151", width=4)
    draw.text((85, 95), "SOCIALIZED", font=_font(28), fill="#9ca3af")
    wrapped = "\n".join(textwrap.wrap(title.upper(), width=19)[:3])
    draw.multiline_text((85, 180), wrapped, font=_font(72), fill="white", spacing=8)
    draw.text((88, 570), subtitle.upper()[:45], font=_font(30), fill="#fbbf24")
    cue = "VISUAL: " + subject[:55]
    draw.text((760, 590), cue, font=_font(22), fill="#d1d5db")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=94)
    return out.getvalue()

if st.button("🎨 Generate thumbnail"):
    data = make_thumb(thumb_title, thumb_sub, subject)
    st.session_state.thumbnail_data = data
if st.session_state.get("thumbnail_data"):
    st.image(st.session_state.thumbnail_data, caption="Socialized creator template — customize further in Canva if desired.")
    st.download_button("⬇️ Download thumbnail", st.session_state.thumbnail_data, "socialized-youtube-thumbnail.jpg", "image/jpeg")

st.divider()
st.info("vidIQ and AMI are treated as optional validation inputs rather than scraped services. Paste their scores into the sidebar/title lab when you use those tools; Socialized keeps its own reproducible opportunity and headline scores instead of depending on fragile browser scraping.")
