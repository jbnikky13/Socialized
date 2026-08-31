from __future__ import annotations
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
CLIENT_FILE = Path("client_secret.json")
TOKEN_FILE = Path("token.json")
DEFAULT_REDIRECT_URI = "https://socialized.streamlit.app/"


def _secret_json(name):
    try:
        import streamlit as st
        value = st.secrets.get(name)
        if value:
            return value
    except Exception:
        pass
    return os.getenv(name)


def _client_config():
    raw = _secret_json("GOOGLE_CLIENT_JSON")
    if raw:
        return json.loads(raw) if isinstance(raw, str) else dict(raw)
    if CLIENT_FILE.exists():
        return json.loads(CLIENT_FILE.read_text(encoding="utf-8"))
    raise RuntimeError("Add GOOGLE_CLIENT_JSON to Streamlit secrets. Do not upload client_secret.json to GitHub.")


def _redirect_uri():
    """Use one deterministic callback URL for Google OAuth."""
    return os.getenv("GOOGLE_REDIRECT_URI") or DEFAULT_REDIRECT_URI


def begin_oauth():
    """Start YouTube OAuth and always show Google's account chooser."""
    redirect_uri = _redirect_uri()
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account consent",
    )
    return authorization_url, state


def finish_oauth(code, state):
    """Exchange the OAuth code, save credentials, and identify the selected YouTube channel."""
    import streamlit as st
    redirect_uri = _redirect_uri()
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state, redirect_uri=redirect_uri)
    flow.fetch_token(code=code)
    token_json = flow.credentials.to_json()
    st.session_state["google_token_json"] = token_json

    # Verify the newly authorized account immediately. Google account selection can
    # succeed even when the selected Google account has no YouTube channel.
    youtube = build("youtube", "v3", credentials=flow.credentials)
    info = channel_info(youtube)
    if not info:
        st.session_state.pop("youtube_connected", None)
        st.session_state.pop("youtube_channel", None)
        raise RuntimeError(
            "Google authorization succeeded, but this Google account has no YouTube channel. "
            "Create or select a YouTube channel for this account and try again."
        )

    snippet = info.get("snippet", {})
    connection = {
        "channel_id": info.get("id"),
        "channel_title": snippet.get("title", "YouTube channel"),
        "custom_url": snippet.get("customUrl", ""),
        "thumbnail": (snippet.get("thumbnails", {}).get("default", {}) or {}).get("url", ""),
    }
    st.session_state["youtube_connected"] = True
    st.session_state["youtube_channel"] = connection
    st.success(f"YouTube connected: {connection['channel_title']}")
    return token_json, connection


def get_service(token_json=None):
    creds = None
    token_json = token_json or st_session_token()
    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    elif TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            if token_json:
                try:
                    import streamlit as st
                    st.session_state["google_token_json"] = creds.to_json()
                except Exception:
                    pass
        else:
            raise RuntimeError("YouTube is not connected. Choose a Google account and authorize YouTube.")
    return build("youtube", "v3", credentials=creds)


def st_session_token():
    try:
        import streamlit as st
        return st.session_state.get("google_token_json") or _secret_json("GOOGLE_TOKEN_JSON")
    except Exception:
        return _secret_json("GOOGLE_TOKEN_JSON")


def channel_info(youtube):
    data = youtube.channels().list(part="snippet,statistics", mine=True).execute()
    items = data.get("items", [])
    return items[0] if items else None


def upload_video(youtube, video_path, title, description, tags, privacy="private", publish_at=None, category_id="22"):
    body = {"snippet": {"title": title[:100], "description": description[:5000], "tags": tags[:500], "categoryId": category_id}, "status": {"privacyStatus": "private" if publish_at else privacy}}
    if publish_at:
        dt = datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        body["status"]["publishAt"] = dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    media = MediaFileUpload(video_path, chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response.get("id")
