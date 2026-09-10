const { createClient } = require('@supabase/supabase-js');
const { dispatchRenderRequested } = require('../lib/github-app.js');
function parseJsonBody(req){if(!req.body)return {};if(typeof req.body==='object')return req.body;try{return JSON.parse(req.body)}catch{throw new Error('Invalid JSON request body')}}
function validateHttpUrl(value){if(typeof value!=='string'||!value.trim())return false;try{const u=new URL(value.trim());return u.protocol==='http:'||u.protocol==='https:'}catch{return false}}
module.exports=async(req,res)=>{
 if(req.method!=='POST')return res.status(405).json({error:'POST required'});
 const {SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY}=process.env;
 if(!SUPABASE_URL||!SUPABASE_SERVICE_ROLE_KEY)return res.status(500).json({error:'Supabase server configuration missing'});
 const sb=createClient(SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY,{auth:{persistSession:false}});
 try{
  const body=parseJsonBody(req),payload=body.payload||{},imageUrl=typeof payload.image_url==='string'?payload.image_url.trim():'';
  if(!validateHttpUrl(imageUrl))return res.status(400).json({error:'payload.image_url must be a complete http(s) URL.'});
  const requestedDuration=Number(payload.duration_hours);
  const durationHours=Number.isFinite(requestedDuration)&&requestedDuration>0?requestedDuration:1;
  const cleanPayload={...payload,image_url:imageUrl,title:String(payload.title||'Ambient World').trim().slice(0,200)||'Ambient World',duration_hours:Math.min(Math.max(durationHours,1/3600),6),layers:Array.isArray(payload.layers)?payload.layers.map(String).slice(0,20):[],thumbnail_text:String(payload.thumbnail_text||'').slice(0,200)};
  const {data,error}=await sb.from('render_jobs').insert({campaign_id:body.campaign_id||null,job_type:'ambient_render',priority:Number(body.priority)||100,payload:cleanPayload,status:'queued',progress:0}).select().single();
  if(error)throw error;
  try{const worker=await dispatchRenderRequested(data.id);return res.status(202).json({job:data,worker})}
  catch(dispatchError){console.error('GitHub App dispatch failed:',dispatchError);await sb.from('render_jobs').update({status:'failed',error:`Worker dispatch failed: ${dispatchError.message||'unknown error'}`}).eq('id',data.id);return res.status(502).json({error:'Render job was created, but GitHub Actions could not be started.',detail:dispatchError.message||'GitHub App dispatch failed',job_id:data.id})}
 }catch(e){console.error('queue-render failed:',e);return res.status(500).json({error:e.message||'Queue failed'})}
};
