from __future__ import annotations
import base64, hashlib, json, os, tempfile
from pathlib import Path
import requests
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
SCOPES=['https://www.googleapis.com/auth/youtube.upload','https://www.googleapis.com/auth/youtube.readonly']
URL=os.environ['SUPABASE_URL'].rstrip('/'); KEY=os.environ['SUPABASE_SERVICE_ROLE_KEY']; BUCKET=os.getenv('SUPABASE_STORAGE_BUCKET','media-assets')
H={'apikey':KEY,'Authorization':f'Bearer {KEY}','Content-Type':'application/json'}
def get(path,params=None):
 r=requests.get(f'{URL}/rest/v1/{path}',headers=H,params=params,timeout=30);r.raise_for_status();return r.json()
def patch(path,params,data):
 r=requests.patch(f'{URL}/rest/v1/{path}',headers={**H,'Prefer':'return=minimal'},params=params,json=data,timeout=30);r.raise_for_status()
def cipher(): return Fernet(base64.urlsafe_b64encode(hashlib.sha256(KEY.encode()).digest()))
def download(url,path):
 with requests.get(url,stream=True,timeout=(15,300)) as r:
  r.raise_for_status()
  with path.open('wb') as f:
   for c in r.iter_content(1024*1024):
    if c:f.write(c)
def main():
 jobs=get('youtube_publish_jobs',{'select':'*','status':'eq.queued','order':'created_at.asc','limit':'1'})
 if not jobs: print('No queued YouTube jobs.'); return
 job=jobs[0]; patch('youtube_publish_jobs',{'id':f"eq.{job['id']}", 'status':'eq.queued'},{'status':'processing'})
 try:
  conn=get('youtube_connections',{'select':'token_json,channel_title','channel_id':f"eq.{job['channel_id']}",'limit':'1'})[0]
  token=cipher().decrypt(conn['token_json'].encode()).decode(); creds=Credentials.from_authorized_user_info(json.loads(token),SCOPES)
  if creds.expired and creds.refresh_token: creds.refresh(Request())
  if not creds.valid: raise RuntimeError('YouTube authorization expired; reconnect the channel.')
  yt=build('youtube','v3',credentials=creds)
  result=job.get('result') or {}; video_url=result.get('video_url') or result.get('public_url'); thumb_url=result.get('thumbnail_url')
  if not video_url: raise RuntimeError('Render job has no video URL.')
  with tempfile.TemporaryDirectory() as td:
   video=Path(td)/'video.mp4'; download(video_url,video)
   body={'snippet':{'title':str(job.get('title') or result.get('title') or 'Ambient World')[:100],'description':str(job.get('description') or '')[:5000],'tags':(job.get('tags') or [])[:500]},'status':{'privacyStatus':job.get('privacy_status') or 'private'}}
   req=yt.videos().insert(part='snippet,status',body=body,media_body=MediaFileUpload(str(video),chunksize=8*1024*1024,resumable=True)); response=None
   while response is None: _,response=req.next_chunk()
   vid=response['id']
   if thumb_url:
    thumb=Path(td)/'thumb.jpg'; download(thumb_url,thumb); yt.thumbnails().set(videoId=vid,media_body=MediaFileUpload(str(thumb),mimetype='image/jpeg')).execute()
  patch('youtube_publish_jobs',{'id':f"eq.{job['id']}"},{'status':'completed','youtube_video_id':vid,'youtube_url':f'https://www.youtube.com/watch?v={vid}'})
 except Exception as e:
  patch('youtube_publish_jobs',{'id':f"eq.{job['id']}"},{'status':'failed','error':str(e)}); raise
if __name__=='__main__': main()
