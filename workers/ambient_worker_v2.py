from __future__ import annotations
import os, subprocess, tempfile, random
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image, ImageStat, ImageDraw
import requests
from services.thumbnail import generate_thumbnail

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

def make_weather_overlay(path,kind,width=640,height=360,fps=30,seconds=12):
 count=width//8 if kind=='rain' else width//10
 rng=random.Random(71337 if kind=='rain' else 91337)
 particles=[]
 for _ in range(count):
  particles.append({'x':rng.uniform(0,width),'y':rng.uniform(-height,height),'length':rng.uniform(7,22) if kind=='rain' else rng.uniform(3,9),'speed':rng.uniform(150,270) if kind=='rain' else rng.uniform(35,80),'alpha':rng.randint(45,120),'drift':rng.uniform(-28,-8) if kind=='rain' else rng.uniform(-5,5)})
 frames_dir=path.parent/'weather_frames'; frames_dir.mkdir(exist_ok=True)
 total=int(fps*seconds)
 try:
  for i in range(total):
   t=i/fps; frame=Image.new('RGBA',(width,height),(0,0,0,0)); draw=ImageDraw.Draw(frame)
   for p in particles:
    y=((p['y']+p['speed']*t)%(height+p['length']))-p['length']; x=(p['x']+p['drift']*t)%width
    if kind=='rain':
     dx=-p['length']*0.22; dy=p['length']; draw.line((x,y,x+dx,y+dy),fill=(205,225,255,p['alpha']),width=1)
    else:
     radius=max(1,p['length']/3); draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=(245,250,255,p['alpha']))
   frame.save(frames_dir/f'{i:04d}.png')
  cmd=['ffmpeg','-y','-framerate',str(fps),'-i',str(frames_dir/'%04d.png'),'-c:v','qtrle','-pix_fmt','argb',str(path)]
  subprocess.run(cmd,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 finally:
  for p in frames_dir.glob('*.png'): p.unlink()
  try: frames_dir.rmdir()
  except OSError: pass

def run_ffmpeg(image,output,duration_hours,sound_kind,weather_overlay=None):
 duration=max(15.0,min(float(duration_hours or 1.0)*3600,6*3600)); audio_duration=duration+2
 # Keep input indexes deterministic: 0=image, 1=audio, 2=weather (when present).
 inputs=['-loop','1','-i',str(image),' -f'.strip(),'lavfi','-t',str(audio_duration),'-i',audio_filter(sound_kind)]
 if weather_overlay: inputs += ['-stream_loop','-1','-i',str(weather_overlay)]
 if weather_overlay:
  filter_complex='[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p[base];[2:v]scale=1280:720:flags=bilinear[weather];[base][weather]overlay=shortest=1:format=auto,format=yuv420p[v];[1:a]atrim=0:%s,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=1,afade=t=out:st=%s:d=1,loudnorm=I=-15:LRA=7:TP=-1.5[a]'%(audio_duration,duration-1)
 else:
  filter_complex='[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,format=yuv420p[v];[1:a]atrim=0:%s,asetpts=PTS-STARTPTS,afade=t=in:st=0:d=1,afade=t=out:st=%s:d=1,loudnorm=I=-15:LRA=7:TP=-1.5[a]'%(audio_duration,duration-1)
 cmd=['ffmpeg','-y',*inputs,'-filter_complex',filter_complex,'-map','[v]','-map','[a]','-t',str(duration),'-r','30','-c:v','libx264','-preset','veryfast','-crf','28','-c:a','aac','-b:a','128k','-movflags','+faststart',str(output)]
 subprocess.run(cmd,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

def upload(path,storage_path,content_type):
 url=f'{SUPABASE_URL}/storage/v1/object/{BUCKET}/{storage_path}'; headers={'apikey':SUPABASE_SERVICE_ROLE_KEY,'Authorization':f'Bearer {SUPABASE_SERVICE_ROLE_KEY}','Content-Type':content_type,'x-upsert':'true'}
 with path.open('rb') as fh:r=requests.post(url,headers=headers,data=fh,timeout=600)
 r.raise_for_status(); return f'{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}'

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
  root=Path(td); image=root/'environment.jpg'; output=root/'ambient.mp4'; thumb=root/'thumbnail.jpg'; weather=None
  update_job(job_id,progress=10); download_image(image_url,image); update_job(job_id,progress=25); sound_kind,sound_source=choose_sound(image,title); update_job(job_id,progress=30); generate_thumbnail(image,thumb,title,label); update_job(job_id,progress=35)
  if sound_kind in {'rain','snow'}:
   weather=root/('rain_overlay.mov' if sound_kind=='rain' else 'snow_overlay.mov'); make_weather_overlay(weather,sound_kind); update_job(job_id,progress=42)
  run_ffmpeg(image,output,duration_hours,sound_kind,weather); update_job(job_id,progress=75); video_path=f'jobs/{job_id}/ambient.mp4'; thumb_path=f'jobs/{job_id}/thumbnail.jpg'; video_url=upload(output,video_path,'video/mp4'); thumb_url=upload(thumb,thumb_path,'image/jpeg'); update_job(job_id,status='completed',progress=100,result={'title':title,'public_url':video_url,'video_url':video_url,'thumbnail_url':thumb_url,'video_storage_path':video_path,'thumbnail_storage_path':thumb_path,'duration_hours':duration_hours,'soundscape':sound_kind,'sound_source':sound_source,'loop_ready':True,'visual_motion':'falling_rain' if sound_kind=='rain' else ('falling_snow' if sound_kind=='snow' else 'static')})

def main():
 job=claim_job(RENDER_JOB_ID or None)
 if not job: print('No target/queued ambient render jobs.'); return
 print(f'Processing render job {job["id"]}')
 try: process(job); print(f'Completed render job {job["id"]}')
 except Exception as exc: print(f'Render job failed: {exc}'); update_job(job['id'],status='failed',progress=0,error=str(exc)); raise

if __name__=='__main__':main()
