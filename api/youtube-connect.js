import { YOUTUBE_SCOPE, requiredEnv, redirectUri, cookieOptions, randomId, signState } from '../lib/youtube-oauth.js';

export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });
  try {
    requiredEnv('GOOGLE_CLIENT_ID'); requiredEnv('GOOGLE_CLIENT_SECRET'); requiredEnv('SUPABASE_URL'); requiredEnv('SUPABASE_SERVICE_ROLE_KEY');
    const payload = Buffer.from(JSON.stringify({ nonce: randomId(24), createdAt: Date.now() })).toString('base64url');
    const state = signState(payload);
    const params = new URLSearchParams({ client_id: process.env.GOOGLE_CLIENT_ID, redirect_uri: redirectUri(), response_type: 'code', access_type: 'offline', prompt: 'select_account consent', include_granted_scopes: 'true', scope: `openid email profile ${YOUTUBE_SCOPE}`, state });
    res.setHeader('Set-Cookie', `socialized_oauth_state=${encodeURIComponent(state)}; ${cookieOptions(600)}`);
    return res.redirect(302, `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`);
  } catch (e) { return res.status(500).json({ error: e.message }); }
}
