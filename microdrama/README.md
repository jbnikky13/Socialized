# AI Photoreal Microdrama Engine

Socialized now contains a self-hosted GPU generation path for photorealistic microdramas. The Streamlit app is the control plane; a rented GPU runs open-weight video generation only when a job is submitted.

## Architecture

```text
Streamlit / Socialized
        |
        +--> Gemini story + continuity plan
        |
        v
   GPU Worker API
        |
        +--> Wan2GP / WanGP
        |      +--> text-to-video
        |      +--> image-to-video
        |      +--> reference-image workflows
        |      +--> local audio/postprocessing
        |
        v
   MP4 returned to control plane
        |
        v
 Supabase Storage
        |
        v
 YouTube approval + publishing
```

## GPU strategy

Start with an RTX 4090 24GB-class rented instance. RunPod or Vast.ai can be used as the infrastructure provider; the application itself does not use their generation-credit APIs. The GPU worker is designed to be started only when needed and stopped when the queue is empty.

## Worker

`gpu_worker.py` exposes:

- `GET /health` — worker health
- `GET /models` — installed WanGP video models
- `POST /jobs` — submit a generation job
- `GET /jobs/{id}` — poll status
- `GET /jobs/{id}/download` — retrieve the finished MP4
- `POST /jobs/{id}/cancel` — request cancellation

Set `MICRODRAMA_WORKER_TOKEN` on the GPU worker and send the same token from Socialized. The worker can download public Supabase Storage reference images and pass them to WanGP as start/reference images.

## GPU image

`Dockerfile.gpu` builds a CUDA runtime containing Wan2GP plus the lightweight Socialized worker API. The model checkpoints are downloaded/configured by Wan2GP at deployment time rather than stored in this repository.

## Story engine

`services/microdrama.py` creates an original romance premise, characters, continuity bible, scene plan, visual prompts, dialogue and narration using the existing Gemini integration. This is text generation only; video generation happens on the self-hosted GPU.

## Control panel

`pages/4_🎬_Self_Hosted_Microdrama.py` provides the first end-to-end control flow:

1. Write a romance premise.
2. Generate the story and character continuity bible.
3. Choose a WanGP model and output settings.
4. Add character/reference image URLs.
5. Submit a scene to the rented GPU.
6. Poll the worker until the scene finishes.
7. Store the resulting MP4 in Supabase Storage.
8. Reuse the existing Socialized YouTube approval/publishing flow.

## Model policy

Video generation uses locally hosted/open-weight checkpoints. No per-generation video-credit API is required. Check the license of every model/checkpoint/LoRA before commercial use and preserve any required attribution or disclosure. Wan2GP's API documentation also requires products integrating WanGP to disclose that they use WanGP.
