from __future__ import annotations
import os, subprocess, tempfile, time, base64
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image, ImageStat
import requests
from services.thumbnail import generate_thumbnail
from services.scene_motion import make_scene_overlay

SUPABASE_URL=os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_SERVICE_ROLE_KEY=os.environ['SUPABASE_SERVICE_ROLE_KEY']
BUCKET=os.getenv('SUPABASE_STORAGE_BUCKET','media-assets')
MAX_IMAGE_MB=int(os.getenv('MAX_IMAGE_MB','20'))
RENDER_JOB_ID=os.getenv('RENDER_JOB_ID','').strip()
HEADERS={'apikey':SUPABASE_SERVICE_ROLE_KEY,'Authorization':f'Bearer {SUPABASE_SERVICE_ROLE_KEY}','Content-Type':'application/json'}

def sb_get(path,params=None):
 r=requests.get(f'{SUPABASE_URL}/rest/v1/{path}',headers=HEADERS,params=params,timeout=30); r.raise_for_status(); return r.json()
def sb_patch(path,params,payload):
 r=requests.patch(f'{SUPABASE_URL}/rest/v1/{path}',headers={**HEADERS,'Prefer':'return=minimal'},params=params,json=payload,timeout=30); r.raise_for_status()
def update_job(job_id,**fields): sb_patch('render_jobs',{'id':f'eq.{job_id}'},fields)

def download_image(url,destination):
 p=urlparse(str(url).strip())
 if p.scheme not in {'http','https'} or not p.netloc: raise ValueError('Environment image URL must be a complete public http(s) URL.')
 with requests.get(str(url).strip(),stream=True,timeout=(15,60),headers={'User-Agent':'Socialized-Ambient-Worker/2.0'}) as r:
  r.raise_for_status(); ct=(r.headers.get('content-type') or '').lower()
  if not ct.startswith('image/'): raise ValueError(f'Environment URL did not return an image (content-type: {ct or "unknown"}).')
  total=0
  with destination.open('wb') as fh:
   for chunk in r.iter_content(262144):
    if chunk:
     total+=len(chunk)
     if total>MAX_IMAGE_MB*1024*1024: raise ValueError(f'Environment image exceeds {MAX_IMAGE_MB} MB.')
     fh.write(chunk)

def choose_sound(image_path,title=''):
 text=(title or '').lower()
 for words,kind in [(('rain','rainy','storm','window','wet','puddle'),'rain'),(('fireplace','fire','hearth','cabin','cozy','candle'),'fireplace'),(('forest','woods','jungle','garden','green','trees'),'forest'),(('snow','winter','ice','frost','mountain'),'snow'),(('cafe','coffee','library','study','book'),'cafe')]:
  if any(w in text for w in words): return kind,'title'
 try:
  img=Image.open(image_path).convert('RGB').resize((48,48)); r,g,b=ImageStat.Stat(img).mean; brightness=(r+g+b)/3
  if b>r*1.12 and b>g*1.03:return 'rain','image'
  if g>r*1.08 and g>b*1.12:return 'forest','image'
  if r>g*1.10 and r>b*1.25 and brightness<205:return 'fireplace','image'
  if brightness>220 and b>=r*0.95:return 'snow','image'
  if brightness<85:return 'rain','image'
 except Exception as exc: print(f'Audio scene analysis fallback: {exc}')
 return 'room_tone','fallback'

def audio_filter(kind):
 if kind=='rain':return 'anoisesrc=color=white:amplitude=0.055:sample_rate=44100,highpass=f=900,lowpass=f=9000,volume=0.72'
 if kind=='fireplace':return 'anoisesrc=color=brown:amplitude=0.07:sample_rate=44100,lowpass=f=1800,highpass=f=90,volume=0.78'
 if kind=='forest':return 'anoisesrc=color=pink:amplitude=0.055:sample_rate=44100,lowpass=f=1400,highpass=f=120,volume=0.72'
 if kind=='snow':return 'anoisesrc=color=pink:amplitude=0.045:sample_rate=44100,lowpass=f=850,volume=0.70'
 if kind=='cafe':return 'anoisesrc=color=brown:amplitude=0.045:sample_rate=44100,lowpass=f=2400,highpass=f=100,volume=0.68'
 return 'anoisesrc=color=brown:amplitude=0.038:sample_rate=44100,lowpass=f=900,volume=0.68'

def run_ffmpeg(image,output,duration_hours,sound_kind,scene_overlay=None,job_id=None):
 duration=max(15.0,min(float(duration_hours or 1.0)*3600,6*3600)); audio_duration=duration+2
 inputs=['-loop','1','-i',str(image),'-f','lavfi','-t',str(audio_duration),'-i',audio_filter(sound_kind)]
 if scene_overlay: inputs += ['-stream_loop','-1','-i',str(scene_overlay)]
 if scene_overlay:
  filter_complex='[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2[base];[2:v]scale=1280:720:flags=bilinear[scene];[base][scene]overlay=shortest=1:format=auto,format=yuv420p[v];[1:a]atrim=0:%s,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=1,afade=t=out:st=%s:d=1,loudnorm=I=-15:LRA=7:TP=-1.5[a]'%(audio_duration,duration-1)
 else:
  filter_complex='[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p[v];[1:a]atrim=0:%s,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=1,afade=t=out:st=%s:d=1,loudnorm=I=-15:LRA=7:TP=-1.5[a]'%(audio_duration,duration-1)
 cmd=['ffmpeg','-y',*inputs,'-filter_complex',filter_complex,'-map','[v]','-map','[a]','-t',str(duration),'-r','30','-c:v','libx264','-preset','veryfast','-crf','28','-c:a','aac','-b:a','128k','-movflags','+faststart','-progress','pipe:1','-nostats',str(output)]
 proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
 last_progress=42
 if proc.stdout:
  for line in proc.stdout:
   line=line.strip()
   if line.startswith('out_time_ms='):
    try: out_time=int(line.split('=',1)[1])/1_000_000
    except ValueError: continue
    pct_int=int(42+min(33,max(0,(out_time/max(duration,1))*33)))
    if job_id and pct_int>=last_progress+2:
     try: update_job(job_id,progress=pct_int)
     except Exception as exc: print(f'Progress update warning: {exc}')
     last_progress=pct_int
 rc=proc.wait()
 if rc!=0:
  err=(proc.stderr.read() if proc.stderr else '')[-6000:]
  raise RuntimeError(f'ffmpeg failed with exit code {rc}: {err}')
 if job_id: update_job(job_id,progress=75)

def _storage_upload_endpoint():
 host=urlparse(SUPABASE_URL).netloc
 if host.endswith('.supabase.co'):
  project=host[:-len('.supabase.co')]
  return f'https://{project}.storage.supabase.co/storage/v1/upload/resumable'
 return f'{SUPABASE_URL}/storage/v1/upload/resumable'

def _public_url(storage_path):
 return f'{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}'

def _standard_upload(path,storage_path,content_type,job_id=None,progress_start=75,progress_end=95):
 url=f'{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}'
 size=path.stat().st_size
 with path.open('rb') as fh:
  for attempt in range(4):
   try:
    rr=requests.post(url,headers={'Authorization':f'Bearer {SUPABASE_SERVICE_ROLE_KEY}','apikey':SUPABASE_SERVICE_ROLE_KEY,'Content-Type':content_type,'x-upsert':'true'},data=fh,timeout=600)
    if rr.status_code in (200,201): return _public_url(storage_path)
    if attempt==3: raise RuntimeError(f'Supabase standard upload failed ({rr.status_code}): {rr.text[:1000]}')
   except requests.RequestException:
    if attempt==3: raise
    fh.seek(0); time.sleep(2**attempt)
 return _public_url(storage_path)

def upload(path,storage_path,content_type,job_id=None,progress_start=75,progress_end=95):
 size=path.stat().st_size
 endpoint=_storage_upload_endpoint()
 # TUS Upload-Metadata is comma-separated with NO whitespace after commas.
 # Values must be base64; a space after a comma becomes part of the next key and
 # causes Supabase Storage to reject the entire upload with 400 Invalid upload-metadata.
 metadata=','.join([
  'bucketName '+base64.b64encode(BUCKET.encode()).decode(),
  'objectName '+base64.b64encode(storage_path.encode()).decode(),
  'contentType '+base64.b64encode(content_type.encode()).decode(),
  'cacheControl '+base64.b64encode(b'3600').decode()
 ])
 headers={'Authorization':f'Bearer {SUPABASE_SERVICE_ROLE_KEY}','apikey':SUPABASE_SERVICE_ROLE_KEY,'Tus-Resumable':'1.0.0','Upload-Length':str(size),'Upload-Metadata':metadata,'x-upsert':'true'}
 try:
  r=requests.post(endpoint,headers=headers,timeout=60)
  if r.status_code not in (201,204):
   raise RuntimeError(f'Supabase resumable upload init failed ({r.status_code}): {r.text[:1000]}')
  upload_url=r.headers.get('Location')
  if not upload_url: raise RuntimeError('Supabase resumable upload did not return an upload URL.')
  offset=0; chunk_size=6*1024*1024; last_pct=progress_start
  with path.open('rb') as fh:
   while offset<size:
    chunk=fh.read(chunk_size)
    if not chunk: break
    sent=False
    for attempt in range(5):
     try:
      rr=requests.patch(upload_url,headers={'Authorization':f'Bearer {SUPABASE_SERVICE_ROLE_KEY}','apikey':SUPABASE_SERVICE_ROLE_KEY,'Tus-Resumable':'1.0.0','Upload-Offset':str(offset),'Content-Type':'application/offset+octet-stream'},data=chunk,timeout=180)
      if rr.status_code in (204,200):
       offset=int(rr.headers.get('Upload-Offset',offset+len(chunk))); sent=True; break
      if attempt==4: raise RuntimeError(f'Supabase resumable upload chunk failed ({rr.status_code}): {rr.text[:1000]}')
     except requests.RequestException:
      if attempt==4: raise
      time.sleep(2**attempt)
    if not sent: raise RuntimeError('Supabase resumable upload chunk could not be sent.')
    if job_id and size:
     pct=progress_start+int((offset/size)*(progress_end-progress_start))
     if pct>=last_pct+2:
      try: update_job(job_id,progress=min(progress_end,pct))
      except Exception as exc: print(f'Upload progress warning: {exc}')
      last_pct=pct
  return _public_url(storage_path)
 except Exception as exc:
  print(f'Resumable upload failed; retrying with standard Supabase upload: {exc}')
  return _standard_upload(path,storage_path,content_type,job_id,progress_start,progress_end)

def claim_job(job_id=None):
 params={'select':'*','status':'eq.queued','limit':'1'}
 if job_id: params['id']=f'eq.{job_id}'
 else: params['order']='created_at.asc'
 rows=sb_get('render_jobs',params)
 if not rows:return None
 job=rows[0]; update_job(job['id'],status='processing',progress=5); return job

def process(job):
 job_id=job['id']; payload=job.get('payload') or {}; image_url=str(payload.get('image_url') or ''); duration_hours=float(payload.get('duration_hours',1.0)); title=str(payload.get('title') or 'Ambient World'); label=str(payload.get('thumbnail_label') or 'SOCIALIZED AMBIENT WORLDS')
 with tempfile.TemporaryDirectory(prefix='socialized-') as td:
  root=Path(td); image=root/'environment.jpg'; output=root/'ambient.mp4'; thumb=root/'thumbnail.jpg'; scene=None
  update_job(job_id,progress=10); download_image(image_url,image); update_job(job_id,progress=25); sound_kind,sound_source=choose_sound(image,title); update_job(job_id,progress=30); generate_thumbnail(image,thumb,title,label); update_job(job_id,progress=35)
  if sound_kind in {'rain','snow','fireplace','candle','forest','cafe'}:
   scene=root/'scene_overlay.mov'; make_scene_overlay(scene,sound_kind); update_job(job_id,progress=42)
  run_ffmpeg(image,output,duration_hours,sound_kind,scene,job_id); video_path=f'jobs/{job_id}/ambient.mp4'; thumb_path=f'jobs/{job_id}/thumbnail.jpg'; video_url=upload(output,video_path,'video/mp4',job_id,75,96); thumb_url=upload(thumb,thumb_path,'image/jpeg',job_id,96,99); motion={'rain':'falling_rain','snow':'falling_snow','fireplace':'fire_glow','candle':'candle_flicker','forest':'forest_sway','cafe':'rising_steam'}.get(sound_kind,'static'); update_job(job_id,status='completed',progress=100,result={'title':title,'public_url':video_url,'video_url':video_url,'thumbnail_url':thumb_url,'video_storage_path':video_path,'thumbnail_storage_path':thumb_path,'duration_hours':duration_hours,'soundscape':sound_kind,'sound_source':sound_source,'loop_ready':True,'visual_motion':motion})

def main():
 job=claim_job(RENDER_JOB_ID or None)
 if not job: print('No target/queued ambient render jobs.'); return
 print(f'Processing render job {job["id"]}')
 try: process(job); print(f'Completed render job {job["id"]}')
 except Exception as exc: print(f'Render job failed: {exc}'); update_job(job['id'],status='failed',progress=0,error=str(exc)); raise

if __name__=='__main__':main()
