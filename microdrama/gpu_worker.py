from __future__ import annotations

import os
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


APP = FastAPI(title="Socialized GPU Worker", version="1.0.0")
JOBS: dict[str, dict[str, Any]] = {}
LOCK = threading.Lock()
SESSION = None


class JobRequest(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)


def _auth(expected: str | None) -> None:
    token = os.getenv("MICRODRAMA_WORKER_TOKEN", "").strip()
    if token and expected != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Invalid worker token.")


def _session():
    global SESSION
    if SESSION is None:
        try:
            from shared.api import init
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "WanGP is not installed. Install the pinned Wan2GP release on the GPU worker."
            ) from exc
        root = Path(os.getenv("WANGP_ROOT", "/opt/Wan2GP"))
        cli_args = os.getenv("WANGP_CLI_ARGS", "--attention sdpa --profile 4").split()
        SESSION = init(root=root, cli_args=cli_args, console_output=False)
    return SESSION


def _run(job_id: str, settings: dict[str, Any]) -> None:
    try:
        with LOCK:
            JOBS[job_id].update(status="running", progress=0, message="GPU worker started")
        job = _session().submit_task(settings)
        with LOCK:
            JOBS[job_id]["message"] = "Generation queued on WanGP"

        result = job.result()
        if not result.success:
            errors = [getattr(e, "message", str(e)) for e in (result.errors or [])]
            raise RuntimeError("; ".join(errors) or "WanGP generation failed.")

        files = [str(x) for x in (result.generated_files or [])]
        with LOCK:
            JOBS[job_id].update(
                status="completed",
                progress=100,
                message="Generation completed",
                generated_files=files,
            )
    except Exception as exc:
        with LOCK:
            JOBS[job_id].update(status="failed", message=str(exc))


@APP.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "backend": "WanGP", "gpu_worker": True}


@APP.post("/jobs")
def create_job(payload: JobRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _auth(authorization)
    settings = dict(payload.settings)
    if not settings.get("model_type"):
        raise HTTPException(status_code=400, detail="settings.model_type is required.")
    if not settings.get("prompt"):
        raise HTTPException(status_code=400, detail="settings.prompt is required.")

    job_id = uuid.uuid4().hex
    with LOCK:
        JOBS[job_id] = {
            "id": job_id,
            "status": "queued",
            "progress": 0,
            "message": "Queued",
            "generated_files": [],
        }
    threading.Thread(target=_run, args=(job_id, settings), daemon=True).start()
    return JOBS[job_id]


@APP.get("/jobs/{job_id}")
def get_job(job_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _auth(authorization)
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        return dict(job)


@APP.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _auth(authorization)
    # The first MVP keeps cancellation conservative: queued/running jobs are
    # marked as cancellation requested. A future adapter can call job.cancel().
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        job["cancel_requested"] = True
        return dict(job)
