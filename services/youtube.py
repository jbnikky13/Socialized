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

from services.db import client

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
    configured = _secret_json("GOOGLE_OAUTH_STATE_SECRET")
    if configured:
        return str(configured).encode("utf-8")
    config = _client_config()
    client_config = config.get("web") or config.get("installed") or config
    secret = client_config.get("client_secret")
    if not secret:
        raise RuntimeError("Google OAuth client secret is missing from GOOGLE_CLIENT_JSON.")
    return str(secret).encode("utf-8")


def _state_cipher():
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError("cryptography is required for secure OAuth state handling.") from exc
    key = base64.urlsafe_b64encode(hashlib.sha256(_state_secret()).digest())
    return Fernet(key)


def _make_state(code_verifier: str):
    """Create a signed state and encrypt the PKCE verifier so it survives OAuth redirects."""
    nonce = secrets.token_urlsafe(24)
    issued = str(int(time.time()))
    payload = f"{issued}.{nonce}"
    signature = hmac.new(_state_secret(), payload.encode("utf-8"), hashlib.sha256).digest()
    encoded_sig = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    encrypted_verifier = _state_cipher().encrypt(code_verifier.encode("utf-8")).decode("ascii")
    return f"{payload}.{encoded_sig}.{encrypted_verifier}"


def _validate_state(state):
    if not state:
        raise RuntimeError("Missing OAuth state. Please start the YouTube connection again.")
    parts = state.split(".", 3)
    if len(parts) != 4:
        raise RuntimeError("Invalid OAuth state. Please start the YouTube connection again.")
    issued, nonce, signature, encrypted_verifier = parts
    try:
        issued_at = int(issued)
    except ValueError as exc:
        raise RuntimeError("Invalid OAuth state timestamp.") from exc
    if abs(int(time.time()) - issued_at) > OAUTH_STATE_MAX_AGE:
        raise RuntimeError("The Google authorization request expired. Please connect YouTube again.")
    payload = f"{issued}.{nonce}"
    expected = base64.urlsafe_b64encode(hmac.new(_state_secret(), payload.encode("utf-8"), hashlib.sha256).digest()).decode("ascii").rstrip("=")
    if not hmac.compare_digest(signature, expected):
        raise RuntimeError("Invalid OAuth state. Please start the YouTube connection again.")
    try:
        verifier = _state_cipher().decrypt(encrypted_verifier.encode("ascii")).decode("utf-8")
    except Exception as exc:
        raise RuntimeError("The OAuth PKCE verifier could not be recovered. Please start the YouTube connection again.") from exc
    if not 43 <= len(verifier) <= 128:
        raise RuntimeError("Invalid OAuth PKCE verifier. Please start the YouTube connection again.")
    return verifier


def _token_cipher():
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError("cryptography is required for secure persistent YouTube connections.") from exc
    secret = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY")
    if not secret:
        raise RuntimeError("A server-side Supabase key is required for persistent YouTube connections.")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _encrypt_token(token_json: str) -> str:
    return _token_cipher().encrypt(token_json.encode("utf-8")).decode("utf-8")


def _decrypt_token(value: str) -> str:
    return _token_cipher().decrypt(value.encode("utf-8")).decode("utf-8")


def begin_oauth():
    redirect_uri = _redirect_uri()
    code_verifier = secrets.token_urlsafe(64)
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=redirect_uri, code_verifier=code_verifier)
    state = _make_state(code_verifier)
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="select_account consent",
        state=state,
        code_challenge_method="S256",
    )
    return authorization_url, state


def _channel_connection(info: dict) -> dict:
    snippet = info.get("snippet", {})
    return {"channel_id": info.get("id"), "channel_title": snippet.get("title", "YouTube channel"), "custom_url": snippet.get("customUrl", ""), "thumbnail": (snippet.get("thumbnails", {}).get("default", {}) or {}).get("url", "")}


def save_connection(connection: dict, token_json: str) -> None:
    row = {"channel_id": connection["channel_id"], "channel_title": connection["channel_title"], "custom_url": connection.get("custom_url", ""), "thumbnail": connection.get("thumbnail", ""), "token_json": _encrypt_token(token_json), "updated_at": datetime.now(timezone.utc).isoformat()}
    client().table("youtube_connections").upsert(row, on_conflict="channel_id").execute()


def list_connections() -> list[dict]:
    return client().table("youtube_connections").select("channel_id,channel_title,custom_url,thumbnail,updated_at").order("updated_at", desc=True).execute().data


def load_connection(channel_id: str) -> str:
    rows = client().table("youtube_connections").select("token_json").eq("channel_id", channel_id).limit(1).execute().data
    if not rows:
        raise RuntimeError("Saved YouTube connection not found. Choose the Google account again.")
    return _decrypt_token(rows[0]["token_json"])


def delete_connection(channel_id: str) -> None:
    client().table("youtube_connections").delete().eq("channel_id", channel_id).execute()
    if _session().get("youtube_channel_id") == channel_id:
        for key in ("youtube_channel_id", "youtube_channel", "youtube_connected", "google_token_json"):
            _session().pop(key, None)


def set_active_connection(channel_id: str) -> dict:
    token_json = load_connection(channel_id)
    creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        token_json = creds.to_json()
    if not creds.valid:
        raise RuntimeError("Saved YouTube authorization is no longer valid. Reconnect this account.")
    youtube = build("youtube", "v3", credentials=creds)
    info = channel_info(youtube)
    if not info:
        raise RuntimeError("The saved Google account no longer has an accessible YouTube channel.")
    connection = _channel_connection(info)
    save_connection(connection, token_json)
    s = _session()
    s["google_token_json"] = token_json
    s["youtube_connected"] = True
    s["youtube_channel"] = connection
    s["youtube_channel_id"] = channel_id
    return connection


def finish_oauth(code, state):
    code_verifier = _validate_state(state)
    redirect_uri = _redirect_uri()
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state, redirect_uri=redirect_uri, code_verifier=code_verifier)
    flow.fetch_token(code=code, code_verifier=code_verifier)
    token_json = flow.credentials.to_json()
    youtube = build("youtube", "v3", credentials=flow.credentials)
    info = channel_info(youtube)
    if not info:
        raise RuntimeError("Google authorization succeeded, but this Google account has no accessible YouTube channel. Create or select a YouTube channel and try again.")
    connection = _channel_connection(info)
    save_connection(connection, token_json)
    s = _session()
    s["google_token_json"] = token_json
    s["youtube_connected"] = True
    s["youtube_channel"] = connection
    s["youtube_channel_id"] = connection["channel_id"]
    return token_json, connection


def _session():
    import streamlit as st
    return st.session_state


def _complete_pending_callback():
    params = _session_query_params()
    code = params.get("code")
    state = params.get("state")
    if not code or not state:
        return None
    result = finish_oauth(code, state)
    _session_query_params().clear()
    return result


def _session_query_params():
    import streamlit as st
    return st.query_params


def get_service(token_json=None):
    callback_result = _complete_pending_callback()
    if callback_result:
        token_json = callback_result[0]
    s = _session()
    token_json = token_json or s.get("google_token_json")
    if not token_json and s.get("youtube_channel_id"):
        token_json = load_connection(s["youtube_channel_id"])
    if not token_json:
        raise RuntimeError("YouTube is not connected. Choose a Google account and authorize YouTube.")
    creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        token_json = creds.to_json()
        s["google_token_json"] = token_json
        if s.get("youtube_channel"):
            save_connection(s["youtube_channel"], token_json)
    if not creds.valid:
        raise RuntimeError("YouTube authorization has expired. Choose the Google account again.")
    return build("youtube", "v3", credentials=creds)


def restore_saved_connection(channel_id: str | None = None) -> dict | None:
    """Restore the previously selected channel after a Streamlit session restart."""
    try:
        connections = list_connections()
    except Exception:
        return None
    if not connections:
        return None
    selected = channel_id or _session().get("youtube_channel_id") or connections[0]["channel_id"]
    try:
        return set_active_connection(selected)
    except Exception:
        return None


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
