const { createClient } = require('@supabase/supabase-js');
module.exports = async (req, res) => {
  if (req.method !== 'GET') return res.status(405).json({ error: 'GET required' });
  const id = req.query.id;
  if (!id) return res.status(400).json({ error: 'id required' });
  const { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } = process.env;
  if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) return res.status(500).json({ error: 'Supabase server configuration missing' });
  const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });
  const { data, error } = await sb.from('render_jobs').select('id,status,progress,result,error,created_at,started_at,completed_at').eq('id', id).single();
  if (error) return res.status(404).json({ error: error.message });
  return res.status(200).json({ job: data });
};
