const { createClient } = require('@supabase/supabase-js');
module.exports=async(req,res)=>{
 if(req.method!=='DELETE'&&req.method!=='POST')return res.status(405).json({error:'DELETE required'});
 const {SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY}=process.env;
 if(!SUPABASE_URL||!SUPABASE_SERVICE_ROLE_KEY)return res.status(500).json({error:'Supabase server configuration missing'});
 try{
  const body=typeof req.body==='string'?JSON.parse(req.body||'{}'):(req.body||{}); let path=String(body.path||'').trim();
  if(!path||!path.startsWith('socialized/')||path.includes('..'))return res.status(400).json({error:'A valid library image path is required.'});
  const sb=createClient(SUPABASE_URL,SUPABASE_SERVICE_ROLE_KEY,{auth:{persistSession:false}});
  const {data,error}=await sb.storage.from('media-assets').remove([path]);
  if(error)throw error;
  return res.status(200).json({ok:true,path,removed:data||[]});
 }catch(e){console.error('delete-image failed:',e);return res.status(500).json({error:e.message||'Could not delete image'})}
};
