const { createClient } = require('@supabase/supabase-js');
module.exports=async(req,res)=>{
 if(req.method!=='DELETE'&&req.method!=='POST') return res.status(405).json({error:'DELETE required'});
 const {SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY}=process.env;
 if(!SUPABASE_URL||!SUPABASE_SERVICE_ROLE_KEY) return res.status(500).json({error:'Supabase server configuration missing'});
 try{
  const body=typeof req.body==='string'?JSON.parse(req.body||'{}'):(req.body||{}); const id=String(body.id||'').trim();
  if(!id) return res.status(400).json({error:'A render job id is required.'});
  const sb=createClient(SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY,{auth:{persistSession:false}});
  const {data:job,error:readError}=await sb.from('render_jobs').select('id,job_type,result').eq('id',id).maybeSingle();
  if(readError) throw readError;
  if(!job||job.job_type!=='ambient_render') return res.status(404).json({error:'Ambient render not found.'});
  const urls=[job.result?.video_url,job.result?.public_url,job.result?.thumbnail_url].filter(Boolean);
  const paths=[];
  for(const url of urls){try{const u=new URL(url);const marker='/storage/v1/object/public/media-assets/';const i=u.pathname.indexOf(marker);if(i>=0)paths.push(decodeURIComponent(u.pathname.slice(i+marker.length)));}catch{}}
  if(paths.length) await sb.storage.from('media-assets').remove([...new Set(paths)]);
  const {error}=await sb.from('render_jobs').delete().eq('id',id).eq('job_type','ambient_render');
  if(error) throw error;
  return res.status(200).json({ok:true,id,deleted_storage_paths:[...new Set(paths)]});
 }catch(e){console.error('delete-rendered-video failed:',e);return res.status(500).json({error:e.message||'Could not delete rendered video'});}
};
