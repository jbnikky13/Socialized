from __future__ import annotations
import os
import subprocess
from pathlib import Path
import requests

# Keep the existing renderer/classifier intact, but replace the fragile final
# upload with a small, independently testable safety layer.
import workers.ambient_worker_v2 as base

MAX_VIDEO_MB = int(os.getenv('MAX_VIDEO_MB', '45'))
SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
BUCKET = os.getenv('SUPABASE_STORAGE_BUCKET', 'media-assets')


def _public(path: str) -> str:
    return f'{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}'


def _update(job_id, **fields):
    try:
        base.update_job(job_id, **fields)
    except Exception:
        pass


def _shrink_video(path: Path, job_id: str) -> None:
    limit = MAX_VIDEO_MB * 1024 * 1024
    if path.stat().st_size <= limit:
        return

    # Ambient scenes are intentionally low-motion. Re-encode only when needed,
    # keeping 1280x720/H.264/AAC and faststart for browser playback.
    attempts = [(33, '900k', '80k'), (35, '700k', '64k'), (37, '550k', '56k')]
    for idx, (crf, rate, audio) in enumerate(attempts, 1):
        temp = path.with_name(f'{path.stem}.safe{idx}.mp4')
        print(f'Safe compression {idx}: {path.stat().st_size/1024/1024:.1f} MB -> <= {MAX_VIDEO_MB} MB')
        cmd = [
            'ffmpeg', '-y', '-i', str(path),
            '-map', '0:v:0', '-map', '0:a:0?',
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', str(crf),
            '-maxrate', rate, '-bufsize', str(int(rate[:-1]) * 2) + 'k',
            '-pix_fmt', 'yuv420p', '-profile:v', 'main', '-level', '4.0',
            '-c:a', 'aac', '-b:a', audio, '-ar', '44100',
            '-movflags', '+faststart', str(temp)
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if p.returncode != 0:
            temp.unlink(missing_ok=True)
            raise RuntimeError(f'Safe compression failed: {p.stderr[-3000:]}')
        if temp.exists() and temp.stat().st_size <= limit:
            temp.replace(path)
            print(f'Safe compression complete: {path.stat().st_size/1024/1024:.1f} MB')
            return
        temp.unlink(missing_ok=True)
    raise RuntimeError(f'Video is still too large after safe compression: {path.stat().st_size/1024/1024:.1f} MB')


def safe_upload(path: Path, storage_path: str, content_type: str, job_id=None, progress_start=75, progress_end=95):
    if content_type == 'video/mp4':
        _shrink_video(path, job_id or '')
    url = f'{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}'
    size = path.stat().st_size
    headers = {
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'apikey': SUPABASE_KEY,
        'Content-Type': content_type,
        'x-upsert': 'true',
    }
    for attempt in range(5):
        try:
            with path.open('rb') as fh:
                r = requests.post(url, headers=headers, data=fh, timeout=900)
            if r.status_code in (200, 201):
                break
            if r.status_code == 413 and content_type == 'video/mp4':
                # A proxy/storage limit is lower than expected; force the next
                # encode pass before retrying rather than repeatedly sending it.
                raise RuntimeError(f'Supabase still rejected video with 413 at {size/1024/1024:.1f} MB: {r.text[:500]}')
            if attempt == 4:
                raise RuntimeError(f'Supabase upload failed ({r.status_code}): {r.text[:1000]}')
            print(f'Upload attempt {attempt + 1} failed ({r.status_code}); retrying.')
        except requests.RequestException as exc:
            if attempt == 4:
                raise RuntimeError(f'Supabase upload request failed: {exc}')
            print(f'Upload attempt {attempt + 1} failed: {exc}; retrying.')
        import time
        time.sleep(2 ** attempt)

    public = _public(storage_path)
    h = requests.head(public, timeout=30)
    if h.status_code != 200:
        raise RuntimeError(f'Upload completed but verification returned HTTP {h.status_code}.')
    remote = int(h.headers.get('content-length', '0') or 0)
    if remote and remote != size:
        raise RuntimeError(f'Uploaded size mismatch: local {size}, remote {remote}.')
    if content_type == 'video/mp4':
        probe = requests.get(public, headers={'Range': 'bytes=0-31'}, timeout=30)
        if probe.status_code not in (200, 206) or len(probe.content) < 12 or probe.content[4:8] != b'ftyp':
            raise RuntimeError('Uploaded MP4 failed the playback header check.')
    return public


# process() in v2 resolves upload() from its own module globals. Replace that
# reference before entering the existing pipeline.
base.upload = safe_upload

if __name__ == '__main__':
    base.main()
