# Socialized — Ambient Worlds Content Engine

Socialized is a production web dashboard for creating and publishing long-form ambient video content. The current architecture uses **Vercel for the web app/API, Supabase for storage and job queues, and GitHub Actions as the production rendering and publishing worker**.

## Product

**Production URL:** https://socialized-self.vercel.app/

Use the production URL above for the live Socialized dashboard.

## Current production architecture

```text
User
  │
  ▼
Vercel — Socialized dashboard + API
  │
  ├── Image upload
  ├── Render job creation
  ├── YouTube OAuth
  └── YouTube channel selection
  │
  ▼
Supabase
  ├── Storage
  ├── render_jobs
  └── youtube_publish_jobs
  │
  ▼
GitHub Actions
  ├── Ambient render worker
  │     ├── FFmpeg
  │     ├── MP4 rendering
  │     └── thumbnail generation
  │
  └── YouTube publisher worker
        ├── OAuth token use
        ├── video upload
        └── thumbnail upload
  │
  ▼
YouTube
```

## Features

### Ambient rendering

- Upload an image directly from a device
- Preview the selected environment image
- Queue a render through the Vercel API
- Store source images and render jobs in Supabase
- GitHub Actions performs the production FFmpeg render
- Generate and store a video thumbnail
- Track render progress and completion
- Preview/download the rendered video

### YouTube connection

- Connect a Google account through OAuth 2.0
- Explicit Google account selection using `select_account`
- Request offline access for background publishing
- Discover the authenticated account's YouTube channels
- Select the channel to publish to
- Store the connection server-side
- Keep OAuth secrets and refresh tokens out of the browser

### YouTube publishing

- Select a connected YouTube channel
- Set video title and description
- Add tags
- Select Public, Unlisted or Private visibility
- Publish the completed render through the GitHub Actions worker
- Upload the generated thumbnail
- Record publishing status, YouTube video ID and URL

## Deployment model

### Vercel

Vercel hosts the Socialized frontend and serverless API routes.

**Production dashboard:** https://socialized-self.vercel.app/

The frontend is intentionally served as the single root `index.html`. There is no second frontend under `public/`.

### Supabase

Supabase is used for persistent application data and object storage, including:

- source images
- rendered videos
- thumbnails
- render jobs
- YouTube connections
- YouTube publishing jobs

### GitHub Actions

GitHub Actions is the production worker. It polls/receives queued work from Supabase and performs the resource-intensive processing that should not run inside Vercel serverless functions.

The worker is responsible for FFmpeg rendering and YouTube publishing.

## Repository structure

```text
index.html
vercel.json
package.json
api/
  upload-image.js
  queue-render.js
  youtube-connect.js
  youtube-callback.js
  youtube-select.js
  youtube-connections.js
  youtube-publish.js
  youtube/
    callback.js
lib/
  youtube-oauth.js
services/
  __init__.py
  ...
workers/
  ...
.github/workflows/
  ambient_render_worker.yml
  youtube_publisher.yml
migrations/
  ...
.env.example
.gitignore
README.md
```

## Important architecture rule

**GitHub Actions is the worker.** Do not reintroduce Render, Railway, Streamlit, or another long-running worker service for the production rendering pipeline.

Vercel handles requests and queue creation. Supabase holds persistent state and files. GitHub Actions performs the background rendering and publishing.

The old Streamlit application/deployment has been removed from the production architecture.

## Required environment variables

### Vercel

Configure the following in the Vercel project environment settings as applicable to the deployed API:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI
```

`GOOGLE_REDIRECT_URI` must exactly match the authorized redirect URI configured in the Google OAuth client.

Production callback:

```text
https://socialized-self.vercel.app/api/youtube/callback
```

### GitHub Actions

Configure the worker secrets in the repository's GitHub Actions secrets:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
```

Add any additional worker-specific secrets required by the current workflow, but never commit credentials to the repository.

## Google OAuth setup

1. Create/select the Google Cloud project used for YouTube publishing.
2. Enable **YouTube Data API v3**.
3. Configure the OAuth consent screen.
4. Use the existing Web application OAuth client when appropriate.
5. Add the production callback URI to the OAuth client's authorized redirect URIs.
6. Add the OAuth credentials to Vercel and GitHub Actions secrets.

Socialized requests account selection so users can choose the Google account they want to authorize. After authorization, Socialized queries the authenticated YouTube account and presents the available channel for selection.

Do not commit `client_secret.json`, OAuth refresh tokens, or any other credentials.

## Job lifecycle

### Render

```text
Upload image
    ↓
Vercel upload API
    ↓
Supabase Storage
    ↓
Create render_jobs record
    ↓
GitHub Actions ambient worker
    ↓
FFmpeg + thumbnail generation
    ↓
Supabase Storage
    ↓
Render marked complete
```

### YouTube publish

```text
Completed render
    ↓
Choose connected channel
    ↓
Create youtube_publish_jobs record
    ↓
GitHub Actions YouTube publisher
    ↓
YouTube videos.insert
    ↓
Upload generated thumbnail
    ↓
Save YouTube video ID/URL
```

## Troubleshooting

### The dashboard appears to be an old version

There must be only one production frontend: `/index.html`.

Do not add a duplicate `public/index.html` or another static frontend. Such duplicates can cause Vercel deployments to serve an outdated interface.

### Render stays at 0%

Check, in order:

1. The Vercel API successfully created a `render_jobs` record.
2. The job has `status = queued`.
3. GitHub Actions can access the Supabase URL/service-role secret.
4. The Ambient Render Worker workflow is enabled and running.
5. The worker can import the Python services package.
6. FFmpeg is installed successfully on the GitHub runner.
7. The worker updates the job status after processing.

### YouTube says no connected account

Check:

1. Google OAuth completed without an error.
2. The callback URI exactly matches Google Cloud configuration.
3. The authenticated channel was selected.
4. The selected channel was persisted to `youtube_connections`.
5. The Vercel API has valid Supabase service-role credentials.
6. The dashboard is reading the same production Supabase project.

### YouTube publishing fails

Check the `youtube_publish_jobs` record and GitHub Actions logs first. Confirm the selected channel, OAuth connection and worker secrets before retrying the job.

## Security

- Never commit API keys, OAuth client secrets or refresh tokens.
- Keep service-role Supabase credentials server-side.
- Do not expose YouTube refresh tokens to browser JavaScript.
- Use the minimum OAuth scopes required for the feature.
- Validate uploaded files and URLs before processing.
- Keep production publishing behind an explicit user action.

## Content and platform compliance

Only upload images, audio and other media that you have permission to use. Respect YouTube copyright, privacy, disclosure, community and API policies. Do not use Socialized to bypass platform limits, moderation or access controls.

## Development principle

Keep the production system simple:

**Vercel = app/API**  
**Supabase = data/storage/queues**  
**GitHub Actions = background worker**  
**YouTube = publishing destination**
