import { parseCookies, cookieOptions } from '../lib/youtube-oauth.js';

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });
  try {
    const pending = parseCookies(req).youtube_pending;
    const channelId = req.body?.channel_id;
    if (!pending || !channelId) return res.status(400).json({ error: 'No pending YouTube connection was found.' });
    const channels = JSON.parse(Buffer.from(pending, 'base64url').toString());
    const selected = channels.find(c => c.channel_id === channelId);
    if (!selected) return res.status(403).json({ error: 'That YouTube channel was not part of the authenticated Google account.' });
    res.setHeader('Set-Cookie', [`youtube_selected=${encodeURIComponent(channelId)}; ${cookieOptions(31536000)}`, 'youtube_pending=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax']);
    return res.status(200).json({ ok: true, channel: selected });
  } catch (e) { console.error(e); return res.status(500).json({ error: e.message }); }
}
