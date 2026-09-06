(() => {
  const VERSION = '1.1.2';
  const lab = document.getElementById('ingestion-lab');
  if (!lab) return;
  const companyId = lab.dataset.companyId;

  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function short(v,n=12){const s=String(v||'');return s ? `${s.slice(0,n)}${s.length>n?'…':''}` : '—';}
  function niceType(v){return String(v||'').replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());}

  function mount(){
    const vault = document.getElementById('source-vault-panel');
    if (!vault || document.getElementById('ps-lineage-registry')) return false;
    const metrics = vault.querySelector('.sv-metrics');
    if (!metrics) return false;
    const box = document.createElement('section');
    box.id = 'ps-lineage-registry';
    box.className = 'ps-lineage-registry';
    box.innerHTML = `
      <div class="ps-lineage-head">
        <div><span class="ps-lineage-kicker">LINEAGE REGISTRY · v${VERSION}</span><b>Original sources and processing runs now have first-class records.</b></div>
        <span class="ps-lineage-badge">Checking registry…</span>
      </div>
      <div class="ps-lineage-metrics">
        <div class="ps-lineage-metric"><span>SOURCE RECORDS</span><strong data-ps-source-count>—</strong><small>Immutable SourceReference records</small></div>
        <div class="ps-lineage-metric"><span>INGESTION JOBS</span><strong data-ps-job-count>—</strong><small>Deterministic + AI processing attempts</small></div>
        <div class="ps-lineage-metric"><span>LATEST RUN</span><strong data-ps-latest-status>—</strong><small data-ps-latest-copy>No processing history yet</small></div>
      </div>
      <details class="ps-lineage-details"><summary>Processing history · 處理紀錄</summary><div class="ps-job-list" data-ps-jobs><div class="sv-note">Loading lineage history…</div></div></details>`;
    metrics.insertAdjacentElement('afterend', box);
    box.addEventListener('click', (event) => handleJobAction(event, box));
    load(box);
    return true;
  }

  function actionHtml(j){
    const status=String(j.status||'').toLowerCase();
    const type=String(j.job_type||'').toLowerCase();
    if(type!=='multimodal_ai') return '';
    if(['failed','cancelled','incomplete'].includes(status) && j.source_id){
      return `<button type="button" class="ps-job-action" data-ps-job-action="retry" data-ps-job-key="${esc(j.job_key||'')}">Retry</button>`;
    }
    if(['queued','processing'].includes(status) && j.provider_job_id){
      return `<button type="button" class="ps-job-action secondary" data-ps-job-action="recover" data-ps-job-key="${esc(j.job_key||'')}">Refresh state</button>`;
    }
    return '';
  }

  async function handleJobAction(event, box){
    const button=event.target.closest('[data-ps-job-action]');
    if(!button || button.disabled) return;
    const action=button.dataset.psJobAction;
    const key=button.dataset.psJobKey;
    if(!action || !key) return;
    const original=button.textContent;
    button.disabled=true;
    button.textContent=action==='retry'?'Starting retry…':'Checking…';
    try{
      const res=await fetch(`/companies/${companyId}/ingestion-jobs/${encodeURIComponent(key)}/${action}`,{method:'POST',headers:{'Accept':'application/json'}});
      let data;try{data=await res.json();}catch{data={error:await res.text()};}
      if(!res.ok) throw new Error(data.error||`${niceType(action)} failed.`);
      button.textContent=action==='retry'?'Retry started ✓':(data.status?niceType(data.status):'Updated ✓');
      setTimeout(()=>load(box),500);
    }catch(err){
      button.textContent='Needs attention';
      button.title=err.message||String(err);
      setTimeout(()=>{button.textContent=original;button.disabled=false;},2200);
    }
  }

  async function load(box){
    const badge=box.querySelector('.ps-lineage-badge');
    try{
      const res=await fetch(`/companies/${companyId}/lineage`,{headers:{'Accept':'application/json'}});
      let data;try{data=await res.json();}catch{data={error:await res.text()};}
      if(!res.ok)throw new Error(data.error||'Lineage registry unavailable.');
      badge.textContent='FIRST-CLASS LINEAGE + RETRY READY';
      box.querySelector('[data-ps-source-count]').textContent=data.source_count ?? 0;
      box.querySelector('[data-ps-job-count]').textContent=data.job_count ?? 0;
      const latest=(data.jobs||[])[0];
      box.querySelector('[data-ps-latest-status]').textContent=latest ? niceType(latest.status) : 'No runs';
      box.querySelector('[data-ps-latest-copy]').textContent=latest ? `${niceType(latest.job_type)} · attempt ${latest.attempt||1} · ${latest.engine_version||latest.model||'engine recorded'}` : 'Ready for the next retained source';
      const jobs=box.querySelector('[data-ps-jobs]');
      if(!(data.jobs||[]).length){jobs.innerHTML='<div class="sv-note">No first-class processing runs recorded yet. New analyses will appear here automatically.</div>';return;}
      jobs.innerHTML=(data.jobs||[]).slice(0,12).map(j=>`<div class="ps-job-row"><div class="ps-job-type">${esc(niceType(j.job_type))}</div><div class="ps-job-main"><b>${esc(j.result_summary||j.model||j.engine_version||'Processing attempt')}</b><small>${j.source_id?`Source ${esc(short(j.source_id,18))} · `:''}Attempt ${esc(j.attempt||1)} · ${j.provider_job_id?`Provider ${esc(short(j.provider_job_id,16))} · `:''}${esc(j.updated_at||j.created_at||'')}</small></div><span class="ps-job-status ${esc(j.status||'')}">${esc(niceType(j.status||'unknown'))}</span><div class="ps-job-actions">${actionHtml(j)}</div></div>`).join('');
    }catch(err){
      badge.textContent='LINEAGE REGISTRY NEEDS ATTENTION';
      badge.style.background='#fff3df';badge.style.color='#8a6429';
      const jobs=box.querySelector('[data-ps-jobs]');if(jobs)jobs.innerHTML=`<div class="sv-note">${esc(err.message||String(err))}</div>`;
    }
  }

  if(!mount()) [80,220,500,900].forEach(ms=>setTimeout(mount,ms));
})();
