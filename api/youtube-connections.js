const { parseCookies, supabase } = require('../lib/youtube-oauth.js');

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });
  try {
    const cookies = parseCookies(req);
    const key = cookies.youtube_connection_key;
    const selected = cookies.youtube_selected || null;
    if (!key) return res.status(200).json({ connections: [], connected: false });

    const rows = await supabase(
      'youtube_connections?connection_key=eq.' + encodeURIComponent(key) +
      '&select=channel_id,channel_title,channel_thumbnail_url,google_email,active,updated_at&order=updated_at.desc'
    );
    return res.status(200).json({
      connected: Boolean(rows?.length),
      selected_channel_id: selected,
      connections: (rows || []).map(row => ({ ...row, selected: row.channel_id === selected }))
    });
  } catch (e) {
    console.error('youtube-connections failed:', e);
    return res.status(500).json({ error: e.message, connections: [], connected: false });
  }
};
