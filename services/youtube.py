from __future__ import annotations
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]
CLIENT_FILE = Path("client_secret.json")
TOKEN_FILE = Path("token.json")


def _secret_json(name):
    try:
        import streamlit as st
        value = st.secrets.get(name)
        if value:
            return value
    except Exception:
        pass
    return os.getenv(name)


def get_service():
    creds = None
    token_json = _secret_json("GOOGLE_TOKEN_JSON")
    client_json = _secret_json("GOOGLE_CLIENT_JSON")
    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    elif TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            if client_json:
                temp = Path(".client_secret_runtime.json")
                temp.write_text(client_json, encoding="utf-8")
                flow = InstalledAppFlow.from_client_secrets_file(str(temp), SCOPES)
            elif CLIENT_FILE.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
            else:
                raise RuntimeError("Add client_secret.json or GOOGLE_CLIENT_JSON in Streamlit secrets.")
            creds = flow.run_local_server(port=0)
        if not token_json:
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def channel_info(youtube):
    data = youtube.channels().list(part="snippet,statistics", mine=True).execute()
    items = data.get("items", [])
    return items[0] if items else None


def upload_video(youtube, video_path, title, description, tags, privacy="private", publish_at=None, category_id="22"):
    body = {
        "snippet": {"title": title[:100], "description": description[:5000], "tags": tags[:500], "categoryId": category_id},
        "status": {"privacyStatus": "private" if publish_at else privacy},
    }
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
