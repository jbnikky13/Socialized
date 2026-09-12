from __future__ import annotations
import os
import subprocess
from pathlib import Path
import requests
import workers.ambient_worker_v2 as base

MAX_VIDEO_MB = int(os.getenv('MAX_VIDEO_MB', '45'))
SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
BUCKET = os.getenv('SUPABASE_STORAGE_BUCKET', 'media-assets')


def _public(path: str) -> str:
    return f'{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}'


def _shrink_video(path: Path, job_id: str) -> None:
    limit = MAX_VIDEO_MB * 1024 * 1024
    if path.stat().st_size <= limit:
        return
    # A one-hour file must average below ~100 kbps to fit 45 MB.
    # Use a deterministic bitrate ladder rather than CRF guesses.
    attempts = [('640k', '64k', '854:480', '24'), ('420k', '48k', '854:480', '20'), ('300k', '40k', '640:360', '20'), ('220k', '32k', '640:360', '18')]
    for idx, (video_rate, audio_rate, scale, fps) in enumerate(attempts, 1):
        temp = path.with_name(f'{path.stem}.safe{idx}.mp4')
        print(f'Safe compression {idx}: {path.stat().st_size/1024/1024:.1f} MB -> target <= {MAX_VIDEO_MB} MB')
        vf = f'scale={scale}:force_original_aspect_ratio=decrease,pad={scale.split(":")[0]}:{scale.split(":")[1]}:(ow-iw)/2:(oh-ih)/2,format=yuv420p'
        cmd = ['ffmpeg','-y','-i',str(path),'-map','0:v:0','-map','0:a:0?','-vf',vf,'-r',fps,'-c:v','libx264','-preset','veryfast','-b:v',video_rate,'-maxrate',video_rate,'-bufsize',str(int(video_rate[:-1])*2)+'k','-pix_fmt','yuv420p','-profile:v','main','-c:a','aac','-b:a',audio_rate,'-ar','44100','-movflags','+faststart',str(temp)]
        p = subprocess.run(cmd,capture_output=True,text=True,timeout=900)
        if p.returncode != 0:
            temp.unlink(missing_ok=True)
            raise RuntimeError(f'Safe compression failed: {p.stderr[-3000:]}')
        if temp.exists() and temp.stat().st_size <= limit:
            temp.replace(path)
            print(f'Safe compression complete: {path.stat().st_size/1024/1024:.1f} MB')
            return
        temp.unlink(missing_ok=True)
    raise RuntimeError(f'Video remains above {MAX_VIDEO_MB} MB after deterministic compression.')


def safe_upload(path: Path, storage_path: str, content_type: str, job_id=None, progress_start=75, progress_end=95):
    if content_type == 'video/mp4':
        _shrink_video(path, job_id or '')
    url = f'{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}'
    size = path.stat().st_size
    headers = {'Authorization': f'Bearer {SUPABASE_KEY}','apikey': SUPABASE_KEY,'Content-Type': content_type,'x-upsert': 'true'}
    for attempt in range(5):
        try:
            with path.open('rb') as fh:
                r = requests.post(url,headers=headers,data=fh,timeout=900)
            if r.status_code in (200,201): break
            if attempt == 4: raise RuntimeError(f'Supabase upload failed ({r.status_code}): {r.text[:1000]}')
            print(f'Upload attempt {attempt+1} failed ({r.status_code}); retrying.')
        except requests.RequestException as exc:
            if attempt == 4: raise RuntimeError(f'Supabase upload request failed: {exc}')
            print(f'Upload attempt {attempt+1} failed: {exc}; retrying.')
        import time; time.sleep(2 ** attempt)
    public = _public(storage_path)
    h = requests.head(public,timeout=30)
    if h.status_code != 200: raise RuntimeError(f'Upload completed but verification returned HTTP {h.status_code}.')
    remote = int(h.headers.get('content-length','0') or 0)
    if remote and remote != size: raise RuntimeError(f'Uploaded size mismatch: local {size}, remote {remote}.')
    if content_type == 'video/mp4':
        probe = requests.get(public,headers={'Range':'bytes=0-31'},timeout=30)
        if probe.status_code not in (200,206) or len(probe.content)<12 or probe.content[4:8] != b'ftyp': raise RuntimeError('Uploaded MP4 failed playback header check.')
    return public

base.upload = safe_upload

if __name__ == '__main__':
    base.main()
