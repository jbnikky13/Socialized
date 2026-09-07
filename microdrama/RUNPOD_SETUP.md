# RunPod GPU setup

Use an RTX 4090 24GB Community Cloud pod for the first runtime test. RunPod currently lists the 4090 from about $0.34/hr on Community Cloud; Secure Cloud is about $0.74/hr. Pricing is variable, so confirm the live rate before starting the pod.

## 1. Create the pod

1. Create/sign in to a RunPod account.
2. Add a small amount of credit.
3. Choose **GPU Pods / Community Cloud**.
4. Select **RTX 4090 24GB**.
5. Use a CUDA 12.4-compatible Ubuntu/PyTorch environment with Docker/NVIDIA Container Toolkit available, or use the repository Dockerfile directly.
6. Attach persistent storage of at least 50–100 GB for model weights and temporary outputs.

Do not expose the worker publicly without authentication and HTTPS.

## 2. Build the worker

From the Socialized repository root on the pod:

```bash
docker build -f microdrama/Dockerfile.gpu -t socialized-microdrama-gpu microdrama
```

Run it:

```bash
docker run --gpus all --restart unless-stopped \
  -p 8080:8080 \
  -e MICRODRAMA_WORKER_TOKEN='REPLACE_WITH_A_LONG_RANDOM_TOKEN' \
  -e WANGP_CLI_ARGS='--attention sdpa --profile 4' \
  -v /workspace/models:/opt/Wan2GP/models \
  -v /workspace/output:/tmp/socialized-microdrama \
  socialized-microdrama-gpu
```

The first model initialization can take time and requires downloading model checkpoints. Keep model storage persistent so stopping/restarting the GPU does not force a full model download.

## 3. Validate NVIDIA + worker

```bash
nvidia-smi
curl http://127.0.0.1:8080/health
```

Expected health response contains:

```json
{"ok":true,"backend":"WanGP","gpu_worker":true}
```

## 4. Connect Socialized

Set these in the Socialized deployment environment (for example Streamlit secrets/environment variables):

- `MICRODRAMA_WORKER_URL` = HTTPS URL of the worker
- `MICRODRAMA_WORKER_TOKEN` = exactly the same random token used on the GPU worker
- `MICRODRAMA_MODEL_TYPE` = the exact video model type installed/available in WanGP

Do not commit these values to GitHub.

## 5. First smoke test

Open **Self-Hosted AI Photoreal Microdrama** in Socialized, generate a short romance story, select a 4–8 second scene, then submit it to the GPU.

Start with 480p and a low inference-step count. The goal of the first test is to verify the entire path:

`Socialized -> worker -> WanGP -> MP4 -> Socialized -> Supabase`

Only after this passes should we move to longer scenes, 720p, character reference workflows, voice, music and automatic episode assembly.

## Cost control

Stop the RunPod pod when not generating. RunPod bills active compute time, and Serverless can scale workers to zero if we later package the worker as a serverless endpoint. For the first test, a normal pod is simpler and gives us shell access for debugging.
