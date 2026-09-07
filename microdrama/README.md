# AI Photoreal Microdrama Engine

This module adds a provider-neutral GPU generation layer to Socialized. The Streamlit app remains the control plane; a rented GPU runs the heavy generation jobs only when requested.

## Architecture

```text
Streamlit / Vercel UI
        |
        v
  Supabase job record
        |
        v
   GPU worker API
        |
        +--> story/scene plan
        +--> character references
        +--> image generation
        +--> video generation
        +--> voice/audio
        +--> FFmpeg assembly
        |
        v
 Supabase Storage
        |
        v
 YouTube publishing
```

## GPU strategy

The worker is provider-neutral. Start with an RTX 4090 24GB class instance on RunPod or Vast.ai. Do not keep the GPU running when the queue is empty.

The worker deliberately does not contain provider credentials. Provider-specific provisioning should be handled by the deployment platform, while this repository only receives jobs and produces assets.

## First MVP

1. Generate a microdrama brief from a premise.
2. Split the story into short scenes.
3. Keep character descriptions stable across scenes.
4. Send scene jobs to the GPU worker.
5. Generate visual/audio assets with locally hosted/open-source models.
6. Assemble the final MP4 with FFmpeg.
7. Upload the finished asset to Supabase Storage.
8. Keep YouTube publishing behind the existing approval gate.

## Cost control

`GPU_IDLE_TIMEOUT_SECONDS` is used by the worker/orchestrator so a worker can be shut down after the queue becomes empty. The application never assumes a permanently running GPU.

## Model policy

Models are loaded from local/open-weight checkpoints configured at deployment time. No per-generation credit API is required by this architecture. Check each model's license before commercial use and keep any required attribution/disclosure.
