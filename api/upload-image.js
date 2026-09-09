const { createClient } = require('@supabase/supabase-js');

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST required' });

  const { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } = process.env;
  if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
    return res.status(500).json({ error: 'Supabase server configuration missing' });
  }

  const contentType = String(req.headers['content-type'] || '').split(';')[0].toLowerCase();
  const allowed = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif']);
  if (!allowed.has(contentType)) return res.status(400).json({ error: 'Only JPG, PNG, WEBP, and GIF images are supported' });

  const chunks = [];
  let total = 0;
  try {
    for await (const chunk of req) {
      total += chunk.length;
      if (total > 10 * 1024 * 1024) return res.status(413).json({ error: 'Image is too large. Maximum size is 10 MB.' });
      chunks.push(chunk);
    }
    const buffer = Buffer.concat(chunks);
    if (!buffer.length) return res.status(400).json({ error: 'No image was uploaded' });

    const ext = contentType === 'image/jpeg' ? 'jpg' : contentType.split('/')[1];
    const safeName = String(req.headers['x-filename'] || 'environment').replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 80);
    const path = `socialized/${Date.now()}-${safeName.replace(/\.[^.]+$/, '')}.${ext}`;

    const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });
    const { error } = await sb.storage.from('media-assets').upload(path, buffer, { contentType, upsert: false });
    if (error) throw error;

    const { data } = sb.storage.from('media-assets').getPublicUrl(path);
    return res.status(201).json({ public_url: data.publicUrl, path });
  } catch (e) {
    console.error('upload-image failed:', e);
    return res.status(500).json({ error: e.message || 'Image upload failed' });
  }
};
