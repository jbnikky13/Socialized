const { parseCookies, supabase } = require('../lib/youtube-oauth.js');
module.exports = async function handler(req,res){
 if(req.method!=='GET') return res.status(405).json({error:'Method not allowed'});
 try{
  const cookies=parseCookies(req); const key=cookies.youtube_connection_key; const selected=cookies.youtube_selected||null;
  if(!key) return res.status(200).json({connections:[],connected:false,selected_channel_id:null});
  const rows=await supabase('youtube_connections?connection_key=eq.'+encodeURIComponent(key)+'&select=channel_id,channel_title,channel_thumbnail_url,google_email,active,updated_at&order=updated_at.desc');
  const connections=(rows||[]).map(row=>({...row,selected:row.channel_id===selected||(!selected&&row.active===true)}));
  const active=connections.find(x=>x.selected)||connections.find(x=>x.active===true)||connections[0];
  return res.status(200).json({connected:Boolean(active),selected_channel_id:active?.channel_id||selected||null,selected_channel_title:active?.channel_title||null,connections});
 }catch(e){console.error('youtube-connections failed:',e);return res.status(500).json({error:e.message,connections:[],connected:false});}
};
