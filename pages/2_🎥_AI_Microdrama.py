from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from services.ai import generate_package, generate_campaign_visual_prompts, generate_campaign_image
from services.campaigns import save_campaign
from services.video_providers import available, create_and_wait, estimate
from services.minimax_h3 import image_data_url, stitch, download
from services.media import upload_asset

st.set_page_config(page_title="AI Microdrama | Socialized", page_icon="🎥", layout="wide")
st.title("🎥 AI Photoreal Microdrama")
st.caption("Campaign → story → campaign images → scenes → Kling/AI video → finished video → Supabase → YouTube")

campaign = st.session_state.get("last_campaign") or {}
reused = st.session_state.get("reused_content", [])
default_script = campaign.get("script", "") or next(
    (x.get("body", "") for x in reused if x.get("platform") == "youtube" and x.get("content_type") == "video"),
    "",
)
default_title = campaign.get("title") or campaign.get("name") or "AI Microdrama"

st.subheader("0. Campaign Studio")
st.caption("Start with an idea. Socialized can write the campaign and create visual assets that match the story.")

with st.container(border=True):
    c1, c2 = st.columns([2, 1])
    with c1:
        campaign_topic = st.text_input(
            "Campaign idea / topic",
            value=st.session_state.get("micro_campaign_topic", ""),
            placeholder="e.g. A woman discovers a secret that changes her family forever",
            key="micro_campaign_topic_input",
        )
    with c2:
        campaign_niche = st.text_input(
            "Niche",
            value=st.session_state.get("micro_campaign_niche", "Drama / Storytelling"),
            key="micro_campaign_niche_input",
        )

    campaign_context = st.text_area(
        "Optional campaign direction / notes",
        value=st.session_state.get("micro_campaign_context", ""),
        height=80,
        placeholder="Audience, location, theme, brand message, characters, or anything the story should include.",
        key="micro_campaign_context_input",
    )

    if st.button("✨ Generate Campaign", type="primary", use_container_width=True, key="generate_micro_campaign"):
        if not campaign_topic.strip():
            st.warning("Enter a campaign idea first.")
        else:
            try:
                with st.spinner("Writing campaign story, hook, titles and social content..."):
                    st.session_state["micro_campaign_package"] = generate_package(
                        campaign_topic.strip(),
                        campaign_niche.strip() or "Drama / Storytelling",
                        "story",
                        campaign_context.strip(),
                    )
                st.session_state.pop("micro_campaign_images", None)
                st.success("Campaign generated. Review it below, then save it and create the visuals.")
            except Exception as exc:
                st.error(f"Campaign generation failed: {exc}")

package = st.session_state.get("micro_campaign_package")
if package:
    with st.container(border=True):
        st.markdown("### Generated campaign")
        title_options = package.get("title_options", [])
        campaign_title = st.selectbox(
            "Campaign title",
            title_options if title_options else [package.get("idea", campaign_topic or "AI Microdrama")],
            key="micro_campaign_title",
        )
        campaign_hook = st.text_area("Hook", package.get("hook", ""), height=80, key="micro_campaign_hook")
        campaign_script = st.text_area(
            "Campaign story / script",
            package.get("script", ""),
            height=260,
            key="micro_campaign_script",
        )
        campaign_description = st.text_area(
            "YouTube description",
            package.get("description", ""),
            height=120,
            key="micro_campaign_description",
        )

        if st.button("💾 Save Campaign to Supabase", type="primary", use_container_width=True, key="save_micro_campaign"):
            try:
                pack = dict(package)
                pack.update(
                    {
                        "title": campaign_title,
                        "script": campaign_script.strip(),
                        "description": campaign_description.strip(),
                        "tags": package.get("tags", []),
                        "thumbnail_text": package.get("thumbnail_text", ""),
                        "x_posts": package.get("x_posts", []),
                        "shorts": package.get("shorts", []),
                    }
                )
                if not pack["script"]:
                    raise ValueError("The campaign story/script is empty.")
                saved = save_campaign(campaign_title, campaign_niche.strip() or "Drama / Storytelling", pack)
                saved.update(
                    {
                        "title": campaign_title,
                        "script": pack["script"],
                        "description": pack["description"],
                        "tags": pack["tags"],
                    }
                )
                st.session_state["last_campaign"] = saved
                st.session_state["reused_content"] = [
                    {"platform": "youtube", "content_type": "video", "title": campaign_title, "body": pack["script"]},
                    {"platform": "youtube", "content_type": "description", "title": campaign_title, "body": pack["description"]},
                ] + [
                    {"platform": "x", "content_type": "post", "title": campaign_title, "body": p}
                    for p in pack.get("x_posts", [])
                ]
                st.session_state["micro_campaign_saved_id"] = saved["id"]
                st.session_state["micro_campaign_topic"] = campaign_topic.strip()
                st.session_state["micro_campaign_niche"] = campaign_niche.strip()
                st.success(f"Campaign saved: {saved['id']}")
                campaign = saved
                default_script = saved["script"]
                default_title = saved["title"]
            except Exception as exc:
                st.error(f"Could not save campaign: {exc}")

saved_campaign = st.session_state.get("last_campaign") or {}
if package:
    st.markdown("### 🖼️ Campaign Images")
    st.caption("Generate original visuals directly from the campaign story. These are stored under the campaign in Supabase Storage.")

    v1, v2, v3 = st.columns(3)
    with v1:
        image_count = st.slider("Images", 1, 4, 3, key="micro_image_count")
    with v2:
        image_style = st.selectbox(
            "Visual style",
            ["photorealistic cinematic", "premium advertising", "dark cinematic drama", "warm emotional drama"],
            key="micro_image_style",
        )
    with v3:
        image_ratio = st.selectbox("Aspect ratio", ["16:9", "9:16", "1:1"], key="micro_image_ratio")

    if not saved_campaign.get("id"):
        st.info("Save the campaign first. Images will then be attached to that campaign and available for the video workflow.")
    else:
        if st.button("🎨 Generate Campaign Images", type="primary", use_container_width=True, key="generate_micro_images"):
            try:
                with st.spinner("Creating campaign-specific visual prompts..."):
                    prompts = generate_campaign_visual_prompts(
                        saved_campaign.get("title", default_title),
                        campaign_script if package else saved_campaign.get("script", default_script),
                        saved_campaign.get("niche", campaign_niche),
                        image_count,
                        image_style,
                    )

                work = Path(tempfile.mkdtemp(prefix="socialized_campaign_images_"))
                assets = []
                progress = st.progress(0)
                status = st.empty()

                for idx, prompt in enumerate(prompts, 1):
                    status.info(f"Generating campaign image {idx}/{len(prompts)}...")
                    image_bytes = generate_campaign_image(prompt, image_ratio)
                    path = work / f"campaign_image_{idx:02d}.png"
                    path.write_bytes(image_bytes)
                    asset = upload_asset(str(path), str(saved_campaign["id"]), asset_type="campaign_image")
                    asset["prompt"] = prompt
                    assets.append(asset)
                    progress.progress(int(idx / len(prompts) * 100))

                st.session_state["micro_campaign_images"] = assets
                status.success(f"{len(assets)} campaign images generated and stored.")
            except Exception as exc:
                st.error(f"Campaign image generation failed: {exc}")

images = st.session_state.get("micro_campaign_images", [])
if images:
    cols = st.columns(min(4, len(images)))
    for idx, asset in enumerate(images):
        with cols[idx % len(cols)]:
            if asset.get("public_url"):
                st.image(asset["public_url"], use_container_width=True)
            st.caption(f"Campaign visual {idx + 1}")
            with st.expander("Image prompt"):
                st.write(asset.get("prompt", ""))

st.divider()

with st.sidebar:
    st.subheader("⚙️ Video engine")
    provider = st.selectbox(
        "Provider",
        ["Kling 3.0 Turbo", "Kling 2.5 Turbo", "Kling Studio (Manual)", "MiniMax H3"],
        help="Kling API uses KLING_API_KEY. Kling Studio (Manual) lets you generate clips in the Kling web app and bring them back into Socialized for stitching/storage.",
    )

    if provider == "Kling 3.0 Turbo":
        options = ["720P", "1080P"]
        ratio_options = ["16:9", "9:16", "1:1"]
        credential_label = "KLING_API_KEY"
        st.caption("Kling 3.0 Turbo: native audio + dialogue/lip-sync. Current API rates: $0.112/sec at 720P or $0.14/sec at 1080P.")
    elif provider == "Kling 2.5 Turbo":
        options = ["720P", "1080P"]
        ratio_options = ["16:9", "9:16", "1:1"]
        credential_label = "KLING_API_KEY"
        st.caption("Kling 2.5 Turbo: $0.042/sec at 720P or $0.07/sec at 1080P; no native audio.")
    elif provider == "Kling Studio (Manual)":
        options = ["720P", "1080P"]
        ratio_options = ["16:9", "9:16", "1:1"]
        credential_label = "not required"
        st.info("Manual mode uses your Kling Creative Studio account. Generate each scene there, download the MP4, then upload it below. No Kling API credits are consumed by Socialized.")
    else:
        options = ["768P", "2K"]
        ratio_options = ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"]
        credential_label = "MINIMAX_API_KEY"

    resolution = st.selectbox("Resolution", options)
    ratio = st.selectbox("Format", ratio_options)

    if provider == "Kling Studio (Manual)":
        st.success("✓ Manual Studio mode ready")
    elif available(provider):
        st.success(f"{provider} API credentials detected")
    else:
        st.warning(f"Add {credential_label} to Streamlit Secrets")

    if provider.startswith("Kling") and provider != "Kling Studio (Manual)" and st.secrets.get("KLING_WEBHOOK_SECRET", ""):
        st.caption("✓ Kling webhook secret detected")

campaign = st.session_state.get("last_campaign") or campaign or {}
reused = st.session_state.get("reused_content", [])
default_script = campaign.get("script", "") or next(
    (x.get("body", "") for x in reused if x.get("platform") == "youtube" and x.get("content_type") == "video"),
    default_script,
)
default_title = campaign.get("title") or campaign.get("name") or default_title

st.subheader("1. Episode")
title = st.text_input("Episode title", value=default_title, key="micro_episode_title")
story = st.text_area(
    "Campaign script / story",
    value=default_script,
    height=160,
    placeholder="Use the saved campaign script or paste a story.",
    key="micro_episode_story",
)

st.subheader("2. Recurring characters")
count = st.number_input("Characters", 1, 6, 2, 1)
characters = []
cols = st.columns(min(3, int(count)))
for i in range(int(count)):
    with cols[i % len(cols)]:
        name = st.text_input("Name", ["Maya", "Daniel", "Sarah", "David", "Amara", "Tunde"][i], key=f"vp_name_{i}")
        desc = st.text_area("Appearance / identity", key=f"vp_desc_{i}", height=70)
        url = st.text_input("Reference image URL", key=f"vp_url_{i}", placeholder="https://...")
        upload = st.file_uploader("Or upload reference", type=["jpg", "jpeg", "png", "webp"], key=f"vp_upload_{i}")
        ref = image_data_url(upload) if upload else url.strip()
        if upload:
            st.image(upload, width=140)
        characters.append({"name": name.strip() or f"Character {i + 1}", "description": desc.strip(), "reference": ref})

st.subheader("3. Scenes")
scene_count = st.number_input("Scenes", 1, 12, 3, 1)
scenes = []
for i in range(int(scene_count)):
    with st.expander(f"Scene {i + 1}", expanded=i == 0):
        setting = st.text_input("Setting", key=f"vp_setting_{i}")
        selected = st.multiselect("Characters", [c["name"] for c in characters], default=[characters[0]["name"]], key=f"vp_chars_{i}")
        action = st.text_area("Action + camera", key=f"vp_action_{i}", height=70)
        dialogue = st.text_area("Exact dialogue", key=f"vp_dialogue_{i}", height=70)
        duration_min = 3 if provider == "Kling 3.0 Turbo" else 5
        duration_max = 15 if provider == "Kling 3.0 Turbo" else 10
        duration_default = min(5, duration_max)
        duration = st.slider("Duration", duration_min, duration_max, duration_default, key=f"vp_duration_{i}")

        if provider == "Kling 3.0 Turbo":
            audio_note = "Generate natural spoken dialogue, accurate lip movements, facial performance, ambience and sound effects. Keep each character's voice/identity consistent and do not invent or paraphrase the supplied dialogue."
        elif provider == "Kling 2.5 Turbo":
            audio_note = "The spoken dialogue is a script cue only; do not attempt to render speech audio. Preserve the intended facial expression and mouth movement for later audio/lip-sync."
        elif provider == "Kling Studio (Manual)":
            audio_note = "This prompt will be copied into Kling Creative Studio. Use Kling VIDEO 3.0/3.0 Omni native audio or Kling Lip Sync in Studio for spoken dialogue."
        else:
            audio_note = "Speak the supplied dialogue naturally and synchronize mouth movement and facial expression to the words when supported by the selected model."

        prompt = (
            "Photorealistic live-action microdrama. Natural human skin, realistic eyes, hair, hands and body movement. "
            "Cinematic believable lighting. Preserve recurring character identity from reference images. No cartoon, illustration, "
            "warped faces, extra fingers, text overlays or baked-in subtitles. "
            f"SETTING: {setting}. CHARACTERS: {', '.join(selected)}. "
            f"DETAILS: {'; '.join(c['name'] + ': ' + c['description'] for c in characters if c['name'] in selected and c['description'])}. "
            f"ACTION/CAMERA: {action}. Exact dialogue: {dialogue or '[No spoken dialogue]'}. "
            f"{audio_note}"
        )
        st.code(prompt, language="text")

        manual_clip = None
        if provider == "Kling Studio (Manual)":
            st.caption("Generate this scene in Kling Studio, download the MP4, then upload it here. Socialized will stitch the uploaded scenes and save the final episode to Supabase.")
            manual_clip = st.file_uploader("Upload completed Kling Studio scene", type=["mp4", "mov"], key=f"vp_manual_clip_{i}")

        refs = [c["reference"] for c in characters if c["name"] in selected and c["reference"]]
        scenes.append({"prompt": prompt, "references": refs, "duration": int(duration), "manual_clip": manual_clip})

seconds = sum(s["duration"] for s in scenes)
cost = sum(estimate(provider, s["duration"], resolution) for s in scenes) if provider != "Kling Studio (Manual)" else 0.0
st.divider()
st.metric("Estimated generation cost", "$0.00" if provider == "Kling Studio (Manual)" else f"${cost:.2f}", f"{seconds}s total • {provider}")
if provider == "Kling 3.0 Turbo":
    st.caption("Kling 3.0 Turbo provides native audio, dialogue and lip-sync in the generated scene. Current API pricing is separate from Kling Studio membership/free credits.")
if provider == "Kling 2.5 Turbo":
    st.caption("Kling 2.5 Turbo has no native audio. Use Kling 3.0 Turbo or Manual Studio Lip Sync if spoken dialogue is required.")
if provider == "Kling Studio (Manual)":
    st.caption("Manual Studio mode does not call the Kling API. Your Kling Studio account handles generation; Socialized only assembles and stores the clips you upload.")
if cost > 10:
    st.warning("Estimated API generation cost is above $10. Consider fewer/shorter scenes or Manual Studio mode.")

missing = [c["name"] for c in characters if not c["reference"]]
if missing and provider != "Kling Studio (Manual)":
    st.warning("Add reference images for: " + ", ".join(missing))

manual_missing = provider == "Kling Studio (Manual)" and any(not s["manual_clip"] for s in scenes)
api_unavailable = provider != "Kling Studio (Manual)" and not available(provider)
disabled = api_unavailable or manual_missing or (bool(missing) and provider != "Kling Studio (Manual)")

if provider == "Kling Studio (Manual)":
    st.info("Workflow: 1) Copy each scene prompt → 2) Generate in Kling Studio → 3) Download each MP4 → 4) Upload each scene above → 5) Generate Episode below.")

if st.button("🚀 Generate / Assemble Episode", type="primary", use_container_width=True, disabled=disabled):
    work = Path(tempfile.mkdtemp(prefix="socialized_video_"))
    clips = []
    progress = st.progress(0)
    status = st.empty()
    try:
        for idx, scene in enumerate(scenes, 1):
            if provider == "Kling Studio (Manual)":
                status.info(f"Preparing manually generated scene {idx}/{len(scenes)}...")
                clip = work / f"scene_{idx:02d}.mp4"
                clip.write_bytes(scene["manual_clip"].getvalue())
            else:
                status.info(f"Generating scene {idx}/{len(scenes)} with {provider}...")
                url = create_and_wait(provider, scene["prompt"], scene["references"], scene["duration"], resolution, ratio)
                clip = work / f"scene_{idx:02d}.mp4"
                download(url, clip)
            clips.append(clip)
            progress.progress(int(idx / len(scenes) * 100))

        final = work / "microdrama_episode.mp4"
        stitch(clips, final)
        data = final.read_bytes()
        st.success(f"Episode ready — {seconds} seconds assembled with {provider}.")
        st.video(data)
        st.download_button("⬇️ Download MP4", data=data, file_name=f"{title or 'microdrama'}.mp4", mime="video/mp4", use_container_width=True)
        if campaign.get("id"):
            asset = upload_asset(str(final), str(campaign["id"]), asset_type="video")
            st.session_state["video_asset"] = asset
            st.success("Video attached to the active campaign. Open YouTube to review/publish.")
    except Exception as exc:
        msg = str(exc)
        if "KLING_AUTH_ERROR" in msg:
            st.error("🔐 Kling authentication failed. Verify KLING_API_KEY in Streamlit Secrets.")
        elif "KLING_BILLING_ERROR" in msg:
            st.error(f"💳 Kling API credits are insufficient. Estimated episode cost: ${cost:.2f}.")
        elif "402" in msg or "insufficient" in msg.lower():
            st.error(f"💳 {provider} rejected the request because the account balance/credits are insufficient. Estimated episode cost: ${cost:.2f}.")
        else:
            st.error(f"Video generation failed: {msg}")
        with st.expander("Technical details"):
            st.exception(exc)
