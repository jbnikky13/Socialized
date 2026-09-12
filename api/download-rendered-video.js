const { createClient } = require('@supabase/supabase-js');

module.exports = async (req, res) => {
  if (req.method !== 'GET') return res.status(405).json({ error: 'GET required' });
  const { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } = process.env;
  if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
    return res.status(500).json({ error: 'Supabase server configuration missing' });
  }

  const id = String(req.query?.id || '').trim();
  if (!/^[0-9a-f-]{36}$/i.test(id)) return res.status(400).json({ error: 'Valid render ID required' });

  try {
    const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });
    const { data: job, error } = await sb
      .from('render_jobs')
      .select('id,status,payload,result')
      .eq('id', id)
      .eq('job_type', 'ambient_render')
      .eq('status', 'completed')
      .maybeSingle();
    if (error) throw error;
    if (!job) return res.status(404).json({ error: 'Rendered video not found' });

    const result = job.result || {};
    const storagePath = result.video_storage_path || `jobs/${id}/ambient.mp4`;
    const title = String(result.title || job.payload?.title || 'socialized-ambient')
      .replace(/[^a-z0-9._-]+/gi, '-').replace(/^-+|-+$/g, '') || 'socialized-ambient';

    const { data, error: signError } = await sb.storage
      .from(process.env.SUPABASE_STORAGE_BUCKET || 'media-assets')
      .createSignedUrl(storagePath, 300, { download: `${title}.mp4` });
    if (signError || !data?.signedUrl) throw signError || new Error('Could not create download URL');

    res.setHeader('Cache-Control', 'private, no-store');
    return res.redirect(302, data.signedUrl);
  } catch (e) {
    console.error('download-rendered-video failed:', e);
    return res.status(500).json({ error: e.message || 'Could not prepare video download' });
  }
};
