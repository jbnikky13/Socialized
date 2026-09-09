// YouTube connection API boundary.
// OAuth credentials/tokens remain server-side; the browser receives channel metadata only.
export default async function handler(req, res) {
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });
  return res.status(200).json({
    connections: [],
    message: 'Connect YouTube from the production OAuth flow once GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI are configured.'
  });
}
