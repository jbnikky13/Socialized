const { createClient } = require('@supabase/supabase-js');

module.exports = async (req, res) => {
  if (req.method !== 'GET') return res.status(405).json({ error: 'GET required' });
  const { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } = process.env;
  if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) return res.status(500).json({ error: 'Supabase server configuration missing' });
  const id = String(req.query?.id || '').trim();
  if (!/^[0-9a-f-]{36}$/i.test(id)) return res.status(400).json({ error: 'Valid render ID required' });
  try {
    const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });
    const { data: job, error } = await sb.from('render_jobs').select('id,status,payload,result').eq('id', id).eq('job_type', 'ambient_render').eq('status', 'completed').maybeSingle();
    if (error) throw error;
    if (!job) return res.status(404).json({ error: 'Rendered video not found' });
    const result = job.result || {};
    const bucket = process.env.SUPABASE_STORAGE_BUCKET || 'media-assets';
    const storagePath = result.video_storage_path || `jobs/${id}/ambient.mp4`;
    const filename = String(result.title || job.payload?.title || 'socialized-ambient').replace(/[^a-z0-9._-]+/gi, '-').replace(/^-+|-+$/g, '') || 'socialized-ambient';
    const { data, error: signError } = await sb.storage.from(bucket).createSignedUrl(storagePath, 300);
    if (signError || !data?.signedUrl) throw signError || new Error('Could not create download URL');
    const upstream = await fetch(data.signedUrl);
    if (!upstream.ok || !upstream.body) throw new Error(`Supabase download failed (${upstream.status})`);
    res.statusCode = 200;
    res.setHeader('Content-Type', 'video/mp4');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}.mp4"; filename*=UTF-8''${encodeURIComponent(filename)}.mp4`);
    res.setHeader('Cache-Control', 'private, no-store, max-age=0');
    res.setHeader('Accept-Ranges', 'bytes');
    const length = upstream.headers.get('content-length');
    if (length) res.setHeader('Content-Length', length);
    const reader = upstream.body.getReader();
    req.on('close', () => { try { reader.cancel(); } catch {} });
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (!res.write(Buffer.from(value))) await new Promise(resolve => res.once('drain', resolve));
    }
    return res.end();
  } catch (e) {
    console.error('download-rendered-video failed:', e);
    if (!res.headersSent) return res.status(500).json({ error: e.message || 'Could not download video' });
    try { res.destroy(e); } catch {}
  }
};
