const { createClient } = require('@supabase/supabase-js');
module.exports=async(req,res)=>{
 if(req.method!=='GET')return res.status(405).json({error:'GET required'});
 const {SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY}=process.env;
 if(!SUPABASE_URL||!SUPABASE_SERVICE_ROLE_KEY)return res.status(500).json({error:'Supabase server configuration missing'});
 try{
  const sb=createClient(SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY,{auth:{persistSession:false}});
  const {data,error}=await sb.from('render_jobs').select('id,created_at,payload,result,status').eq('job_type','ambient_render').eq('status','completed').order('created_at',{ascending:false}).limit(100);
  if(error)throw error;
  const videos=(data||[]).map(j=>({id:j.id,created_at:j.created_at,title:j.result?.title||j.payload?.title||'Ambient World',video_url:j.result?.video_url||j.result?.public_url||'',thumbnail_url:j.result?.thumbnail_url||'',duration_hours:j.result?.duration_hours||j.payload?.duration_hours||0,soundscape:j.result?.soundscape||'',loop_mode:j.result?.loop_mode||j.result?.loop||'seamless'})).filter(x=>x.video_url);
  return res.status(200).json({videos});
 }catch(e){console.error('rendered-videos failed:',e);return res.status(500).json({error:e.message||'Could not load rendered videos',videos:[]})}
};
