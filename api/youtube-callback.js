import { createClient } from '@supabase/supabase-js';

function cookieValue(req, name) {
  const raw = req.headers.cookie || '';
  const item = raw.split(';').map(v => v.trim()).find(v => v.startsWith(`${name}=`));
  return item ? decodeURIComponent(item.slice(name.length + 1)) : null;
}

export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });
  const { code, state, error } = req.query;
  if (error) return res.status(400).send(`Google authorization failed: ${error}`);
  if (!code || !state || state !== cookieValue(req, 'youtube_oauth_state')) return res.status(400).send('Invalid or expired OAuth state. Please try again.');
  const clientId = process.env.GOOGLE_CLIENT_ID;
  const clientSecret = process.env.GOOGLE_CLIENT_SECRET;
  const redirectUri = process.env.GOOGLE_REDIRECT_URI || 'https://socialized-self.vercel.app/api/youtube-callback';
  if (!clientId || !clientSecret) return res.status(500).send('Google OAuth server configuration is incomplete.');
  try {
    const tokenResponse = await fetch('https://oauth2.googleapis.com/token', { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams({ code, client_id: clientId, client_secret: clientSecret, redirect_uri: redirectUri, grant_type: 'authorization_code' }) });
    const tokens = await tokenResponse.json();
    if (!tokenResponse.ok) throw new Error(tokens.error_description || tokens.error || 'Token exchange failed');
    const accessToken = tokens.access_token;
    const userResponse = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', { headers: { Authorization: `Bearer ${accessToken}` } });
    const user = await userResponse.json();
    const channelResponse = await fetch('https://www.googleapis.com/youtube/v3/channels?part=snippet,contentDetails&mine=true', { headers: { Authorization: `Bearer ${accessToken}` } });
    const channels = await channelResponse.json();
    if (!channelResponse.ok) throw new Error(channels.error?.message || 'Could not retrieve YouTube channel');
    if (!channels.items?.length) throw new Error('No YouTube channel was found for this Google account.');
    const supabase = createClient(process.env.SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY);
    const refreshToken = tokens.refresh_token;
    if (!refreshToken) throw new Error('Google did not return a refresh token. Reconnect and approve access again.');
    const rows = channels.items.map(channel => ({ google_account_id: user.sub, google_email: user.email || null, channel_id: channel.id, channel_title: channel.snippet?.title || 'YouTube channel', channel_thumbnail_url: channel.snippet?.thumbnails?.default?.url || null, refresh_token: refreshToken, active: false }));
    const { error: dbError } = await supabase.from('youtube_connections').upsert(rows, { onConflict: 'channel_id' });
    if (dbError) throw dbError;
    const query = encodeURIComponent(JSON.stringify(rows.map(({ refresh_token, ...safe }) => safe)));
    res.setHeader('Set-Cookie', 'youtube_oauth_state=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0');
    return res.redirect(302, `/?youtube_connected=1&channels=${query}`);
  } catch (e) {
    return res.status(500).send(`YouTube connection failed: ${e.message}`);
  }
}
