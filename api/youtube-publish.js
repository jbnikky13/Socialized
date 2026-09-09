const { createClient } = require('@supabase/supabase-js');
function cookies(req){const out={};String(req.headers.cookie||'').split(';').forEach(p=>{const i=p.indexOf('=');if(i>0)out[p.slice(0,i).trim()]=decodeURIComponent(p.slice(i+1).trim())});return out}
module.exports=async(req,res)=>{
 if(req.method!=='POST')return res.status(405).json({error:'POST required'});
 const {SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY}=process.env;
 if(!SUPABASE_URL||!SUPABASE_SERVICE_ROLE_KEY)return res.status(500).json({error:'Supabase server configuration missing'});
 try{
  const c=cookies(req), key=c.youtube_connection_key, channel=c.youtube_selected;
  if(!key||!channel)return res.status(400).json({error:'Connect YouTube and select a channel first.'});
  const body=typeof req.body==='string'?JSON.parse(req.body||'{}'):(req.body||{});
  if(!body.render_job_id)return res.status(400).json({error:'render_job_id is required'});
  const sb=createClient(SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY,{auth:{persistSession:false}});
  const {data:render,error:renderError}=await sb.from('render_jobs').select('id,status,result,payload').eq('id',body.render_job_id).single();
  if(renderError)throw renderError;
  if(render.status!=='completed')return res.status(409).json({error:'Render must be completed before publishing.'});
  const {data:conn,error:connError}=await sb.from('youtube_connections').select('channel_id,channel_title,connection_key').eq('connection_key',key).eq('channel_id',channel).eq('active',false).single();
  if(connError)throw connError;
  const title=String(body.title||render.result?.title||render.payload?.title||'Ambient World').slice(0,100);
  const description=String(body.description||'').slice(0,5000);
  const tags=Array.isArray(body.tags)?body.tags.map(String).slice(0,30):[];
  const privacy=['private','unlisted','public'].includes(body.privacy_status)?body.privacy_status:'private';
  const {data:job,error}=await sb.from('youtube_publish_jobs').insert({render_job_id:render.id,channel_id:channel,title,description,tags,privacy_status:privacy,status:'queued'}).select().single();
  if(error)throw error;
  return res.status(202).json({job,channel:{id:conn.channel_id,title:conn.channel_title}});
 }catch(e){console.error('youtube-publish failed:',e);return res.status(500).json({error:e.message||'Could not queue YouTube publish'});}
};
