# YouTube Content Bot

A deployable Streamlit dashboard for planning, generating, reviewing, and publishing YouTube content. It supports AI-assisted scripts and metadata, RSS-based topic research, approval queues, YouTube OAuth uploads, and optional scheduled publishing through GitHub Actions.

## Features

- Channel/niche configuration
- Topic research from RSS feeds
- AI-assisted video ideas, scripts, titles, descriptions and tags
- Content approval queue
- Local video upload and YouTube publishing
- Scheduled publishing using ISO timestamps
- YouTube channel analytics snapshot
- JSON/SQLite local storage for simple deployments
- Docker support
- GitHub Actions scheduled worker
- No API keys are committed to the repository

## Project structure

```text
app.py
services/
  ai.py
  database.py
  research.py
  youtube.py
.github/workflows/daily_worker.yml
requirements.txt
Dockerfile
.env.example
.gitignore
```

## 1. Install locally

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## 2. AI setup

Create an OpenAI API key and add it as `OPENAI_API_KEY` in your environment. The app also works without it: research and manual planning remain available.

## 3. YouTube API setup

Create a Google Cloud project, enable **YouTube Data API v3**, and create an OAuth client for a desktop application. Download the OAuth client JSON and save it locally as `client_secret.json` for local development.

The first time you connect YouTube, a browser window will open for Google authorization. The resulting token is stored locally in `token.json`.

For a hosted deployment, use Streamlit secrets. Example:

```toml
[secrets]
GOOGLE_CLIENT_JSON = "{...the complete client_secret.json JSON...}"
GOOGLE_TOKEN_JSON = "{...the authorized token.json JSON...}"
OPENAI_API_KEY = "your-key"
```

Do not commit either OAuth file or API key.

## 4. YouTube publishing

In the dashboard, create a content item, attach an MP4, review the generated metadata, then approve and publish or schedule it. YouTube scheduling requires a future UTC timestamp and a channel authorized for uploads.

## 5. GitHub Actions

The included workflow runs once per day. It is intentionally conservative: it only processes approved items that have a local video path and a scheduled time that has arrived. For cloud deployments, replace the local media path with object storage before enabling unattended publishing.

The workflow can also be triggered manually from GitHub Actions.

## 6. Production recommendations

For a serious multi-channel version, add Supabase/Postgres for durable content records, object storage for videos, a queue/worker for rendering, and a dedicated video generation/TTS provider. Keep the approval step enabled until the content quality is reliable.

## Safety and platform compliance

Only upload content you have permission to use. Respect YouTube policies, copyright, privacy, and disclosure requirements. The bot does not attempt to bypass YouTube limits or moderation.
