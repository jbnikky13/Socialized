from __future__ import annotations

from typing import Any


def extract_uploaded_text(uploaded_file) -> str:
    name = (uploaded_file.name or "").lower()
    raw = uploaded_file.getvalue()
    if name.endswith((".txt", ".md", ".markdown", ".csv")):
        return raw.decode("utf-8", errors="replace")
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(raw))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if name.endswith(".docx"):
        from docx import Document
        import io
        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    raise ValueError("Unsupported story file. Use TXT, MD, DOCX or PDF.")


def screenplay_from_source(source_text: str, source_kind: str = "story", title: str = "") -> dict[str, Any]:
    text = source_text.strip()
    if not text:
        raise ValueError("The selected source is empty.")
    from services.ai import _gemini
    prompt = f"""
You are the screenplay director for a photorealistic AI video studio.
Convert the source below into a production-ready microdrama/documentary screenplay.
Source type: {source_kind}
Title: {title}

Rules:
- Preserve factual claims from research/campaign material; never invent facts presented as facts.
- For fictional stories, preserve the plot and character intent.
- Break the material into 4-15 second visual scenes. Keep the total scene count practical.
- Each scene has one clear continuous action.
- Extract recurring characters and give each a concise visual identity description.
- Dialogue must be exact spoken words, not summaries.
- For narration/documentary material, put exact narration in dialogue and use a Narrator character.
- Keep scenes visually coherent and suitable for photorealistic reference-to-video generation.
- Return JSON only with exactly this schema:
{{"title":"...","characters":[{{"name":"...","description":"..."}}],"scenes":[{{"number":1,"title":"...","setting":"...","characters":["..."],"action":"...","dialogue":"...","duration":6}}]}}

SOURCE:
{text[:30000]}
"""
    data = _gemini(prompt)
    if not data.get("scenes"):
        raise RuntimeError("The screenplay contains no scenes.")
    for index, scene in enumerate(data["scenes"], 1):
        scene["number"] = index
        scene["duration"] = max(4, min(15, int(scene.get("duration", 6))))
        scene["characters"] = scene.get("characters") or []
    return data


def campaign_script(campaign: dict, reused_content: list[dict] | None = None) -> str:
    reused_content = reused_content or []
    for item in reused_content:
        if item.get("platform") == "youtube" and item.get("content_type") == "video" and (item.get("body") or "").strip():
            return item["body"].strip()
    return str(campaign.get("script") or campaign.get("body") or "").strip()
