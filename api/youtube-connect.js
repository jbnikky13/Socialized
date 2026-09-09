const crypto = require('crypto');

export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });
  const clientId = process.env.GOOGLE_CLIENT_ID;
  const redirectUri = process.env.GOOGLE_REDIRECT_URI || 'https://socialized-self.vercel.app/api/youtube-callback';
  if (!clientId) return res.status(500).json({ error: 'GOOGLE_CLIENT_ID is not configured' });
  const state = crypto.randomBytes(24).toString('hex');
  res.setHeader('Set-Cookie', `youtube_oauth_state=${state}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=600`);
  const params = new URLSearchParams({ client_id: clientId, redirect_uri: redirectUri, response_type: 'code', access_type: 'offline', prompt: 'select_account consent', include_granted_scopes: 'true', scope: 'openid email https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly', state });
  return res.redirect(302, `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`);
}
