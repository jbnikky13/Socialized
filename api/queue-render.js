const { createClient } = require('@supabase/supabase-js');

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST required' });
  const { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } = process.env;
  if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) return res.status(500).json({ error: 'Supabase server configuration missing' });
  const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });
  try {
    const body = req.body || {};
    if (!body.payload || !body.payload.image_url) return res.status(400).json({ error: 'payload.image_url is required' });
    const { data, error } = await sb.from('render_jobs').insert({ campaign_id: body.campaign_id || null, job_type: 'ambient_render', priority: body.priority || 100, payload: body.payload }).select().single();
    if (error) throw error;
    return res.status(202).json({ job: data });
  } catch (e) { return res.status(500).json({ error: e.message }); }
};
