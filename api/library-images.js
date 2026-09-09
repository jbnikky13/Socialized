const { createClient } = require('@supabase/supabase-js');

module.exports = async (req, res) => {
  if (req.method !== 'GET') return res.status(405).json({ error: 'GET required' });
  const { SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY } = process.env;
  if (!SUPABASE_URL || !SUPABASE_SERVICE_ROLE_KEY) return res.status(500).json({ error: 'Supabase server configuration missing' });
  try {
    const sb = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, { auth: { persistSession: false } });
    const { data, error } = await sb.storage.from('media-assets').list('socialized', {
      limit: 100,
      offset: 0,
      sortBy: { column: 'created_at', order: 'desc' }
    });
    if (error) throw error;
    const images = (data || [])
      .filter(item => item && item.name && !item.id?.endsWith('/'))
      .map(item => {
        const path = `socialized/${item.name}`;
        const { data: urlData } = sb.storage.from('media-assets').getPublicUrl(path);
        return {
          name: item.name,
          path,
          public_url: urlData?.publicUrl || '',
          created_at: item.created_at || null,
          updated_at: item.updated_at || null,
          metadata: item.metadata || null
        };
      })
      .filter(item => item.public_url && /\.(jpe?g|png|webp|gif)$/i.test(item.name));
    return res.status(200).json({ images });
  } catch (e) {
    console.error('library-images failed:', e);
    return res.status(500).json({ error: e?.message || 'Could not load image library' });
  }
};
