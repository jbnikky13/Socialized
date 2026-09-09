from __future__ import annotations
import os, subprocess, tempfile
from pathlib import Path
from urllib.parse import urlparse
import requests
from services.thumbnail import generate_thumbnail
SUPABASE_URL=os.environ['SUPABASE_URL'].rstrip('/')
SUPABASE_SERVICE_ROLE_KEY=os.environ['SUPABASE_SERVICE_ROLE_KEY']
BUCKET=os.getenv('SUPABASE_STORAGE_BUCKET','media-assets')
MAX_IMAGE_MB=int(os.getenv('MAX_IMAGE_MB','20'))
HEADERS={'apikey':SUPABASE_SERVICE_ROLE_KEY,'Authorization':f'Bearer {SUPABASE_SERVICE_ROLE_KEY}','Content-Type':'application/json'}
def sb_get(path,params=None):
 r=requests.get(f'{SUPABASE_URL}/rest/v1/{path}',headers=HEADERS,params=params,timeout=30); r.raise_for_status(); return r.json()
def sb_patch(path,params,payload):
 r=requests.patch(f'{SUPABASE_URL}/rest/v1/{path}',headers={**HEADERS,'Prefer':'return=minimal'},params=params,json=payload,timeout=30); r.raise_for_status()
def update_job(job_id,**fields): sb_patch('render_jobs',{'id':f'eq.{job_id}'},fields)
def validate_image_url(value):
 p=urlparse(value.strip())
 if p.scheme not in {'http','https'} or not p.netloc: raise ValueError('Environment image URL must be a complete public http(s) URL.')
 return value.strip()
def download_image(url,destination):
 with requests.get(url,stream=True,timeout=(15,60),headers={'User-Agent':'Socialized-Ambient-Worker/1.0'}) as r:
  r.raise_for_status(); ct=(r.headers.get('content-type') or '').lower()
  if not ct.startswith('image/'): raise ValueError(f'Environment URL did not return an image (content-type: {ct or "unknown"}).')
  total=0
  with destination.open('wb') as fh:
   for chunk in r.iter_content(1024*256):
    if chunk: total+=len(chunk); 
    if total>MAX_IMAGE_MB*1024*1024: raise ValueError(f'Environment image exceeds {MAX_IMAGE_MB} MB.')
    fh.write(chunk)
def run_ffmpeg(image,output,duration_hours):
 duration=max(1.0,min(float(duration_hours or 0.0167)*3600,6*3600))
 cmd=['ffmpeg','-y','-loop','1','-i',str(image),'-f','lavfi','-i','anoisesrc=color=pink:amplitude=0.025:sample_rate=44100','-filter_complex','[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p[v];[1:a]lowpass=f=700,volume=0.35[a]','-map','[v]','-map','[a]','-t',str(duration),'-r','30','-c:v','libx264','-preset','veryfast','-crf','28','-c:a','aac','-b:a','96k','-movflags','+faststart',str(output)]
 subprocess.run(cmd,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
def upload(path,storage_path,content_type):
 url=f'{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}'; headers={'apikey':SUPABASE_SERVICE_ROLE_KEY,'Authorization':f'Bearer {SUPABASE_SERVICE_ROLE_KEY}','Content-Type':content_type,'x-upsert':'true'}
 with path.open('rb') as fh: r=requests.post(url,headers=headers,data=fh,timeout=300)
 r.raise_for_status(); return f'{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}'
def claim_job():
 rows=sb_get('render_jobs',{'select':'*','status':'eq.queued','order':'created_at.asc','limit':'1'})
 if not rows:return None
 job=rows[0]; update_job(job['id'],status='processing',progress=5); return job
def process(job):
 job_id=job['id']; payload=job.get('payload') or {}; image_url=validate_image_url(payload.get('image_url','')); duration_hours=float(payload.get('duration_hours',0.0167)); title=str(payload.get('title') or 'Ambient World')
 with tempfile.TemporaryDirectory(prefix='socialized-') as td:
  root=Path(td); image=root/'environment.jpg'; output=root/'ambient.mp4'; thumb=root/'thumbnail.jpg'
  update_job(job_id,progress=10); download_image(image_url,image); update_job(job_id,progress=25)
  generate_thumbnail(str(image),str(thumb),title); update_job(job_id,progress=35)
  run_ffmpeg(image,output,duration_hours); update_job(job_id,progress=75)
  video_path=f'jobs/{job_id}/ambient.mp4'; thumb_path=f'jobs/{job_id}/thumbnail.jpg'
  video_url=upload(output,video_path,'video/mp4'); thumb_url=upload(thumb,thumb_path,'image/jpeg')
  update_job(job_id,status='completed',progress=100,result={'title':title,'public_url':video_url,'video_url':video_url,'thumbnail_url':thumb_url,'video_storage_path':video_path,'thumbnail_storage_path':thumb_path,'duration_hours':duration_hours})
def main():
 job=claim_job()
 if not job: print('No queued ambient render jobs.'); return
 print(f'Processing render job {job["id"]}')
 try: process(job); print(f'Completed render job {job["id"]}')
 except Exception as exc: print(f'Render job failed: {exc}'); update_job(job['id'],status='failed',progress=0,error=str(exc)); raise
if __name__=='__main__': main()
