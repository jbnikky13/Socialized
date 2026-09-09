(() => {
  const mount = () => {
    if (document.getElementById('youtubePanel')) return;
    const section = document.createElement('section'); section.id='youtubePanel';
    section.innerHTML = `<h2>▶️ YouTube publishing</h2><p class="hint">Connect a Google account, choose a YouTube channel, then publish completed ambient renders.</p><button id="youtubeConnect" class="secondary" type="button">🔗 Connect YouTube / Choose Google account</button><div id="youtubeConnections" class="status">Checking connected channels…</div>`;
    document.querySelector('main')?.appendChild(section);
    document.getElementById('youtubeConnect').onclick=()=>{ location.href='/api/youtube-connect'; };
    loadConnections();
  };
  async function loadConnections(){
    const el=document.getElementById('youtubeConnections'); if(!el)return;
    try{const r=await fetch('/api/youtube-connections',{headers:{Accept:'application/json'},cache:'no-store'});const j=await r.json();if(!r.ok)throw new Error(j.error||'Could not load channels');
      if(!j.connections?.length){el.textContent='No YouTube channel connected yet.';return;}
      el.innerHTML='<strong>Connected channels</strong>'+j.connections.map(c=>`<div style="display:flex;align-items:center;gap:10px;margin-top:12px"><img src="${safe(c.channel_thumbnail_url||'')}" style="width:40px;height:40px;border-radius:50%" alt=""><span>${safe(c.channel_title)}<br><small>${safe(c.google_email||'')} ${c.selected?'· Selected':''}</small></span></div>`).join('');
    }catch(e){el.textContent='⚠️ '+e.message;}
  }
  function safe(v){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount();
})();
