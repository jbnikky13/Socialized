import { parseCookies, supabase } from '../lib/youtube-oauth.js';

export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });
  try {
    const selected = parseCookies(req).youtube_selected || null;
    const rows = await supabase('youtube_connections?select=channel_id,channel_title,channel_thumbnail_url,google_email,updated_at&order=updated_at.desc');
    return res.status(200).json({ connections: (rows || []).map(row => ({ ...row, selected: row.channel_id === selected })) });
  } catch (e) { console.error(e); return res.status(500).json({ error: e.message, connections: [] }); }
}
