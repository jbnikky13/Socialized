from __future__ import annotations
import os, subprocess, time
from pathlib import Path
import requests
import workers.ambient_worker_v2 as base

MAX_VIDEO_MB = int(os.getenv('MAX_VIDEO_MB', '200'))
SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
BUCKET = os.getenv('SUPABASE_STORAGE_BUCKET', 'media-assets')


def _public(path):
    return f'{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}'


def _duration(path):
    p = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)], capture_output=True, text=True, timeout=60)
    if p.returncode != 0: raise RuntimeError(f'Could not determine video duration: {p.stderr[-1000:]}')
    return max(1.0, float(p.stdout.strip()))


def _encode_to_target(src, dst, duration, video_kbps, audio_kbps, width, height, fps):
    vf=f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},format=yuv420p'
    cmd=['ffmpeg','-y','-i',str(src),'-map','0:v:0','-map','0:a:0?','-vf',vf,'-r',str(fps),'-c:v','libx264','-preset','slow','-b:v',f'{video_kbps}k','-maxrate',f'{video_kbps}k','-bufsize',f'{video_kbps*2}k','-pix_fmt','yuv420p','-profile:v','high','-c:a','aac','-b:a',f'{audio_kbps}k','-ar','44100','-t',str(duration),'-movflags','+faststart',str(dst)]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=1800)
    if p.returncode!=0: raise RuntimeError(f'Compression failed: {p.stderr[-4000:]}')


def _upgrade_to_1080(path):
    duration=_duration(path)
    temp=path.with_name(f'{path.stem}.1080.mp4')
    print(f'Upgrading sleep video to 1920x1080: {duration/3600:.2f}h')
    _encode_to_target(path,temp,duration,1800,96,1920,1080,30)
    temp.replace(path)


def _shrink_video(path, job_id):
    limit=int(MAX_VIDEO_MB*0.90*1024*1024)
    if path.stat().st_size <= limit: return
    duration=_duration(path)
    target_total_kbps=max(160,int((limit*8)/(duration*1000)))
    audio_kbps=64 if target_total_kbps>=240 else 48
    video_kbps=max(80,target_total_kbps-audio_kbps-5)
    profiles=[(1920,1080,30),(1920,1080,24),(1280,720,24)]
    for idx,(w,h,fps) in enumerate(profiles,1):
        temp=path.with_name(f'{path.stem}.safe{idx}.mp4')
        print(f'Sleep-video size encode {idx}: duration={duration/3600:.2f}h total={target_total_kbps}kbps video={video_kbps}k audio={audio_kbps}k {w}x{h}@{fps}')
        _encode_to_target(path,temp,duration,video_kbps,audio_kbps,w,h,fps)
        size=temp.stat().st_size
        print(f'Sleep-video size result {idx}: {size/1024/1024:.2f} MB')
        if size <= limit:
            temp.replace(path)
            return
        temp.unlink(missing_ok=True)
        target_total_kbps=max(120,int(target_total_kbps*0.78))
        audio_kbps=48
        video_kbps=max(64,target_total_kbps-audio_kbps-5)
    raise RuntimeError(f'Video remains too large after deterministic size targeting: {path.stat().st_size/1024/1024:.1f} MB')


def safe_upload(path, storage_path, content_type, job_id=None, progress_start=75, progress_end=95):
    if content_type=='video/mp4':
        _upgrade_to_1080(path)
        if job_id: base.update_job(job_id, progress=82)
        _shrink_video(path, job_id or '')
        if job_id: base.update_job(job_id, progress=88)
    url=f'{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}'
    size=path.stat().st_size
    headers={'Authorization':f'Bearer {SUPABASE_KEY}','apikey':SUPABASE_KEY,'Content-Type':content_type,'x-upsert':'true'}
    for attempt in range(4):
        try:
            with path.open('rb') as fh: r=requests.post(url,headers=headers,data=fh,timeout=900)
            if r.status_code in (200,201): break
            if attempt==3: raise RuntimeError(f'Supabase upload failed ({r.status_code}): {r.text[:1000]}')
        except requests.RequestException as exc:
            if attempt==3: raise RuntimeError(f'Supabase upload request failed: {exc}')
        time.sleep(2**attempt)
    public=_public(storage_path)
    h=requests.head(public,timeout=30)
    if h.status_code!=200: raise RuntimeError(f'Upload completed but verification returned HTTP {h.status_code}.')
    remote=int(h.headers.get('content-length','0') or 0)
    if remote and remote!=size: raise RuntimeError(f'Uploaded size mismatch: local {size}, remote {remote}.')
    if content_type=='video/mp4':
        probe=requests.get(public,headers={'Range':'bytes=0-31'},timeout=30)
        if probe.status_code not in (200,206) or len(probe.content)<12 or probe.content[4:8]!=b'ftyp': raise RuntimeError('Uploaded MP4 failed playback header check.')
    return public

base.upload=safe_upload
if __name__=='__main__': base.main()
