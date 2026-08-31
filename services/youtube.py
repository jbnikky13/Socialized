from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
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
OAUTH_STATE_MAX_AGE = 10 * 60


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
    return os.getenv("GOOGLE_REDIRECT_URI") or DEFAULT_REDIRECT_URI


def _state_secret():
    """Use a dedicated secret when supplied; otherwise derive one from the OAuth client secret."""
    configured = _secret_json("GOOGLE_OAUTH_STATE_SECRET")
    if configured:
        return str(configured).encode("utf-8")
    config = _client_config()
    client = config.get("web") or config.get("installed") or config
    secret = client.get("client_secret")
    if not secret:
        raise RuntimeError("Google OAuth client secret is missing from GOOGLE_CLIENT_JSON.")
    return str(secret).encode("utf-8")


def _make_state():
    """Create a signed OAuth state so the callback can be verified even after Streamlit reconnects."""
    nonce = secrets.token_urlsafe(24)
    issued = str(int(time.time()))
    payload = f"{issued}.{nonce}"
    signature = hmac.new(_state_secret(), payload.encode("utf-8"), hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{payload}.{encoded}"


def _validate_state(state):
    if not state:
        raise RuntimeError("Missing OAuth state. Please start the YouTube connection again.")
    parts = state.split(".")
    if len(parts) != 3:
        raise RuntimeError("Invalid OAuth state. Please start the YouTube connection again.")
    issued, nonce, signature = parts
    try:
        issued_at = int(issued)
    except ValueError as exc:
        raise RuntimeError("Invalid OAuth state timestamp.") from exc
    if abs(int(time.time()) - issued_at) > OAUTH_STATE_MAX_AGE:
        raise RuntimeError("The Google authorization request expired. Please connect YouTube again.")
    payload = f"{issued}.{nonce}"
    expected = base64.urlsafe_b64encode(
        hmac.new(_state_secret(), payload.encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    if not hmac.compare_digest(signature, expected):
        raise RuntimeError("Invalid OAuth state. Please start the YouTube connection again.")


def begin_oauth():
    """Start YouTube OAuth and always show Google's account chooser."""
    redirect_uri = _redirect_uri()
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=redirect_uri)
    state = _make_state()
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account consent",
        state=state,
    )
    return authorization_url, state


def finish_oauth(code, state):
    """Exchange the OAuth code, save credentials, and identify the selected YouTube channel."""
    import streamlit as st
    _validate_state(state)
    redirect_uri = _redirect_uri()
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state, redirect_uri=redirect_uri)
    flow.fetch_token(code=code)
    token_json = flow.credentials.to_json()
    st.session_state["google_token_json"] = token_json

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
    return token_json, connection


def _complete_pending_callback():
    """Complete a Google callback even if Streamlit created a fresh WebSocket session."""
    try:
        import streamlit as st
        params = st.query_params
        code = params.get("code")
        state = params.get("state")
        if not code or not state:
            return None
        result = finish_oauth(code, state)
        st.query_params.clear()
        return result
    except Exception:
        raise


def get_service(token_json=None):
    # OAuth redirects can create a new Streamlit session, so the old
    # st.session_state youtube_oauth_state may no longer exist. Complete the
    # callback from the URL before looking for an existing token.
    try:
        callback_result = _complete_pending_callback()
        if callback_result:
            token_json = callback_result[0]
    except Exception:
        # Only suppress callback processing when there is no callback in the URL.
        # If code/state were present, surface the actual authorization error.
        try:
            import streamlit as st
            if st.query_params.get("code") or st.query_params.get("state"):
                raise
        except ImportError:
            pass

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
