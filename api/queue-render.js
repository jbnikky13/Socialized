const { createClient } = require('@supabase/supabase-js');

function parseJsonBody(req) {
  if (!req.body) return {};
  if (typeof req.body === 'object') return req.body;
  try { return JSON.parse(req.body); } catch { throw new Error('Invalid JSON request body'); }
}

function validateHttpUrl(value) {
  if (typeof value !== 'string' || !value.trim()) return false;
  try {
    const u = new URL(value.trim());
    return u.protocol === 'http:' || u.protocol === 'https:';
  } catch { return false; }
}

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST required' });
  const { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } = process.env;
  if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) return res.status(500).json({ error: 'Supabase server configuration missing' });
  const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });

  try {
    const body = parseJsonBody(req);
    const payload = body.payload || {};
    const imageUrl = typeof payload.image_url === 'string' ? payload.image_url.trim() : '';
    if (!validateHttpUrl(imageUrl)) {
      return res.status(400).json({ error: 'payload.image_url must be a complete http(s) URL, for example https://example.com/room.jpg' });
    }

    const cleanPayload = {
      ...payload,
      image_url: imageUrl,
      title: String(payload.title || 'Ambient World').trim().slice(0, 200) || 'Ambient World',
      duration_hours: Math.min(Math.max(Number(payload.duration_hours) || 0.0167, 1 / 3600), 6),
      layers: Array.isArray(payload.layers) ? payload.layers.map(String).slice(0, 20) : [],
      thumbnail_text: String(payload.thumbnail_text || '').slice(0, 200),
    };

    const { data, error } = await sb.from('render_jobs').insert({
      campaign_id: body.campaign_id || null,
      job_type: 'ambient_render',
      priority: Number(body.priority) || 100,
      payload: cleanPayload,
      status: 'queued',
      progress: 0,
    }).select().single();

    if (error) throw error;
    return res.status(202).json({ job: data });
  } catch (e) {
    console.error('queue-render failed:', e);
    return res.status(500).json({ error: e.message || 'Queue failed' });
  }
};
