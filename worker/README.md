# Socialized Production Worker

The worker is intentionally separate from Vercel. It owns long-running FFmpeg/audio/video jobs and consumes `public.render_jobs` from Supabase.

## Contract

A queued job contains:

```json
{
  "job_type": "ambient_render",
  "payload": {
    "campaign_id": "uuid",
    "image_url": "https://...",
    "duration_hours": 8,
    "layers": ["rain", "fireplace", "room_tone"],
    "title": "The Last Lantern Tavern"
  }
}
```

The worker claims a job, renders outside the request lifecycle, uploads results to Supabase Storage, and updates `render_jobs.result` and `status`.

## Runtime

Python + FFmpeg. Deploy as a persistent worker/VM/container, not a Vercel serverless function.

Required environment variables:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `WORKER_ID`
- `POLL_SECONDS` (default 5)

YouTube credentials remain isolated from the frontend and should be used only by the worker for approved publishing jobs.
