# Socialized — YouTube Growth & Content Engine

A deployable Streamlit dashboard for researching, validating, generating, reviewing, rendering and publishing YouTube content. The existing campaign workflow remains intact, with a new **YouTube Growth Intelligence** page for demand discovery and topic validation.

## Growth Intelligence upgrade

The new `pages/01_YouTube_Growth_Intelligence.py` adds:

- Google Trends Trending Now discovery by market
- YouTube public-search opportunity checks through the YouTube Data API
- Reproducible 0–100 opportunity scoring using demand, YouTube performance, monetization, competition and freshness
- AI-assisted title generation with a local headline-quality score
- Campaign generation and direct saving into the existing Socialized campaign system
- A Canva-style 1280×720 thumbnail template generator
- Optional human validation using vidIQ and AMI scores without fragile browser scraping

Google Trends is used for discovery; it is not treated as a precise search-volume API. YouTube Data API is used for public search and video statistics. Google documents the Data API and its API-key/OAuth requirements in its developer documentation.

## Existing features

- Channel/niche configuration
- RSS topic research
- Gemini-assisted ideas, scripts, titles, descriptions and tags
- Supabase campaign storage
- Content approval queue
- Automatic voiceover, thumbnail and MP4 generation
- YouTube OAuth uploads
- X publishing
- Scheduled GitHub Actions worker
- YouTube analytics snapshot
- Docker support
- No secrets committed to the repository

## Project structure

```text
app.py
pages/
  01_YouTube_Growth_Intelligence.py
services/
  ai.py
  campaigns.py
  growth_intelligence.py
  research.py
  auto_media.py
  youtube.py
.github/workflows/daily_worker.yml
requirements.txt
Dockerfile
.env.example
.gitignore
```

## Required secrets

Existing publishing secrets remain unchanged. For the new Growth Intelligence page, add:

```toml
GEMINI_API_KEY = "..."
YOUTUBE_API_KEY = "..."
```

`YOUTUBE_API_KEY` is used only for public YouTube search/statistics checks. Publishing still uses the existing OAuth flow.

## vidIQ and AMI

Socialized deliberately does **not** scrape logged-in vidIQ or AMI pages. Their scores can be used as optional human validation inputs while the application keeps its own reproducible scoring layer. This avoids brittle browser automation and account/session dependencies.

## Thumbnail workflow

The built-in generator creates a clean, high-contrast creator template. It can be downloaded and further customized in Canva when desired. The content pipeline remains usable without Canva credentials.

## YouTube publishing note

YouTube's Data API supports video insertion and metadata updates, but Google currently requires authorization for write operations. Unverified API projects may also have upload visibility restrictions until the project is audited. Keep the approval gate enabled until the channel workflow is proven stable.

## Safety and platform compliance

Only upload content you have permission to use. Respect YouTube policies, copyright, privacy, disclosure requirements and API quotas. Socialized does not attempt to bypass platform limits or moderation.
