(() => {
  const VERSION = '1.1.1';
  const lab = document.getElementById('ingestion-lab');
  if (!lab) return;
  const companyId = lab.dataset.companyId;

  const stateCopy = {
    active: 'Real/current client evidence. Counts toward readiness and stage gates.',
    test: 'Synthetic or engineering validation. Preserved, but excluded from readiness.',
    archived: 'Historical/audit source. Preserved, but excluded from the current assessment.',
  };

  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

  function mountSummary(data){
    const registry = document.getElementById('ps-lineage-registry');
    if (!registry) return;
    let box = document.getElementById('ps-lifecycle-summary');
    if (!box) {
      box = document.createElement('section');
      box.id = 'ps-lifecycle-summary';
      box.className = 'ps-lifecycle-summary';
      const metrics = registry.querySelector('.ps-lineage-metrics');
      (metrics || registry.querySelector('.ps-lineage-head'))?.insertAdjacentElement('afterend', box);
    }
    const c = data.counts || {active:0,test:0,archived:0};
    box.innerHTML = `
      <div class="ps-lifecycle-summary-head">
        <div><b>Evidence lifecycle · 證據生命週期</b><small style="display:block;margin-top:2px">Only ACTIVE sources affect readiness.</small></div>
        <span class="ps-lifecycle-chip active">v${VERSION}</span>
      </div>
      <div class="ps-lifecycle-counts">
        <div class="ps-lifecycle-count"><span>ACTIVE</span><strong>${Number(c.active||0)}</strong></div>
        <div class="ps-lifecycle-count"><span>TEST</span><strong>${Number(c.test||0)}</strong></div>
        <div class="ps-lifecycle-count"><span>ARCHIVED</span><strong>${Number(c.archived||0)}</strong></div>
      </div>
      <div class="ps-lifecycle-note">TEST and ARCHIVED files keep their SourceReference, R2 original and processing history, but do not change current client counts, stage gates or readiness scores.</div>`;
  }

  function lifecycleChip(state){
    const span=document.createElement('span');
    span.className=`ps-lifecycle-chip ${state}`;
    span.textContent=state==='active'?'ACTIVE · counts toward readiness':state==='test'?'TEST · excluded from readiness':'ARCHIVED · audit only';
    return span;
  }

  function applyFileState(item){
    const row=document.getElementById(`file-${item.intake_file_id}`);
    if(!row) return;
    const main=row.querySelector('.file-main');
    if(!main || main.dataset.psLifecycle==='1') return;
    main.dataset.psLifecycle='1';
    const state=item.state||'active';
    row.classList.toggle('ps-state-test',state==='test');
    row.classList.toggle('ps-state-archived',state==='archived');

    let chips=main.querySelector('.ps-file-chips');
    if(!chips){chips=document.createElement('div');chips.className='ps-file-chips';const meta=main.querySelector(':scope > small');(meta||main.firstChild)?.after?.(chips);}
    chips.appendChild(lifecycleChip(state));

    const control=document.createElement('div');
    control.className='ps-lifecycle-control';
    control.innerHTML=`
      <label>EVIDENCE STATE · 證據狀態
        <select data-ps-lifecycle-select>
          <option value="active" ${state==='active'?'selected':''}>Active · 真實有效</option>
          <option value="test" ${state==='test'?'selected':''}>Test · 測試資料</option>
          <option value="archived" ${state==='archived'?'selected':''}>Archived · 封存</option>
        </select>
      </label>
      <small data-ps-lifecycle-help>${esc(stateCopy[state]||stateCopy.active)}</small>`;
    const technical=main.querySelector('.ps-file-technical');
    if(technical) technical.insertAdjacentElement('beforebegin',control); else main.appendChild(control);

    const selectEl=control.querySelector('[data-ps-lifecycle-select]');
    const help=control.querySelector('[data-ps-lifecycle-help]');
    selectEl.addEventListener('change',async()=>{
      const next=selectEl.value;
      help.textContent='Saving lifecycle state…';selectEl.disabled=true;
      try{
        const fd=new FormData();fd.append('state',next);
        const res=await fetch(`/companies/${companyId}/intake-files/${item.intake_file_id}/lifecycle`,{method:'POST',body:fd,headers:{'Accept':'application/json'}});
        let data;try{data=await res.json();}catch{data={error:await res.text()};}
        if(!res.ok)throw new Error(data.error||'Could not update lifecycle state.');
        help.textContent=stateCopy[next]||stateCopy.active;
        // Counts, stage and readiness are server-derived, so reload after a
        // successful state change instead of trying to maintain duplicate truth.
        window.location.reload();
      }catch(err){
        help.textContent=err.message||String(err);selectEl.value=state;selectEl.disabled=false;
      }
    });
  }

  async function load(){
    try{
      const res=await fetch(`/companies/${companyId}/source-lifecycle`,{headers:{'Accept':'application/json'}});
      let data;try{data=await res.json();}catch{data={error:await res.text()};}
      if(!res.ok)throw new Error(data.error||'Lifecycle registry unavailable.');
      mountSummary(data);
      (data.items||[]).forEach(applyFileState);
    }catch(err){
      console.warn('[PrimeStride lifecycle]',err);
    }
  }

  load();
  [180,500,900].forEach(ms=>setTimeout(load,ms));
})();
