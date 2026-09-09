from __future__ import annotations
import os, time, uuid, tempfile, traceback
from pathlib import Path
from supabase import create_client
from services.ambient import generate_ambient_audio, make_ambient_thumbnail, render_ambient_video

SUPABASE_URL=os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
WORKER_ID=os.getenv("WORKER_ID", f"worker-{uuid.uuid4().hex[:8]}")
POLL_SECONDS=float(os.getenv("POLL_SECONDS", "5"))
sb=create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def claim_job():
    result=sb.rpc("claim_render_job", {"p_worker_id": WORKER_ID}).execute()
    return result.data[0] if result.data else None

def process(job):
    payload=job.get("payload") or {}
    if job.get("job_type") != "ambient_render": raise ValueError(f"Unsupported job type: {job.get('job_type')}")
    image_url=payload.get("image_url")
    if not image_url: raise ValueError("payload.image_url is required")
    import requests
    work=Path(tempfile.mkdtemp(prefix="socialized_ambient_")); image=work/"world.jpg"; audio=work/"ambience.wav"; thumb=work/"thumbnail.jpg"; video=work/"ambient.mp4"
    response=requests.get(image_url,timeout=60); response.raise_for_status(); image.write_bytes(response.content)
    hours=float(payload.get("duration_hours",1)); layers=payload.get("layers") or ["rain","fireplace","room_tone"]
    sb.table("render_jobs").update({"progress":5}).eq("id",job["id"]).execute()
    generate_ambient_audio(str(audio),hours,layers)
    sb.table("render_jobs").update({"progress":30}).eq("id",job["id"]).execute()
    make_ambient_thumbnail(payload.get("thumbnail_text") or payload.get("title","Ambient World"),str(image),str(thumb))
    sb.table("render_jobs").update({"progress":40}).eq("id",job["id"]).execute()
    render_ambient_video(str(image),str(audio),str(video),hours)
    sb.table("render_jobs").update({"progress":95}).eq("id",job["id"]).execute()
    return {"video_path":str(video),"thumbnail_path":str(thumb),"audio_path":str(audio),"worker_id":WORKER_ID}

def fail(job, exc):
    attempts=job.get("attempts",1); max_attempts=job.get("max_attempts",3); status="failed" if attempts>=max_attempts else "queued"
    sb.table("render_jobs").update({"status":status,"error":str(exc),"available_at":"now()","updated_at":"now()"}).eq("id",job["id"]).execute()

def main():
    print(f"Socialized worker {WORKER_ID} online")
    while True:
        try:
            job=claim_job()
            if not job: time.sleep(POLL_SECONDS); continue
            try:
                result=process(job); sb.table("render_jobs").update({"status":"completed","progress":100,"result":result,"completed_at":"now()","error":None}).eq("id",job["id"]).execute()
            except Exception as exc: traceback.print_exc(); fail(job,exc)
        except Exception: traceback.print_exc(); time.sleep(POLL_SECONDS)

if __name__ == "__main__": main()
