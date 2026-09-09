const { createClient } = require('@supabase/supabase-js');

// Keep the binary request body unparsed so the Vercel Node function can read it as a stream.
module.exports.config = { api: { bodyParser: false } };

module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST required' });

  const { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } = process.env;
  if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) {
    return res.status(500).json({ error: 'Supabase server configuration missing. Add SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to Vercel Production.' });
  }

  const contentType = String(req.headers['content-type'] || '').split(';')[0].toLowerCase();
  const allowed = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif']);
  if (!allowed.has(contentType)) {
    return res.status(400).json({ error: `Unsupported image type: ${contentType || 'unknown'}. Use JPG, PNG, WEBP, or GIF.` });
  }

  // Vercel Functions have a request-body limit; keep this below that limit.
  const MAX_BYTES = 4 * 1024 * 1024;
  try {
    const chunks = [];
    let total = 0;
    for await (const chunk of req) {
      const part = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      total += part.length;
      if (total > MAX_BYTES) {
        return res.status(413).json({ error: 'Image is too large. Please use an image under 4 MB.' });
      }
      chunks.push(part);
    }

    const buffer = Buffer.concat(chunks);
    if (!buffer.length) return res.status(400).json({ error: 'No image data was received. Please choose the image again.' });

    const ext = contentType === 'image/jpeg' ? 'jpg' : contentType.split('/')[1];
    let original = 'environment';
    try { original = decodeURIComponent(String(req.headers['x-filename'] || 'environment')); } catch {}
    const base = original.replace(/\.[^.]+$/, '').replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 60) || 'environment';
    const path = `socialized/${Date.now()}-${base}.${ext}`;

    const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });
    const { error } = await sb.storage.from('media-assets').upload(path, buffer, {
      contentType,
      cacheControl: '3600',
      upsert: false,
    });
    if (error) throw error;

    const { data } = sb.storage.from('media-assets').getPublicUrl(path);
    if (!data || !data.publicUrl) throw new Error('Supabase did not return a public image URL. Make sure media-assets is a public bucket.');

    return res.status(201).json({ public_url: data.publicUrl, path, bytes: buffer.length });
  } catch (e) {
    console.error('upload-image failed:', e);
    return res.status(500).json({ error: e && e.message ? e.message : 'Image upload failed' });
  }
};
