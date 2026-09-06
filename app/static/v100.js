(() => {
  const VERSION = '1.0.0';
  const lab = document.getElementById('ingestion-lab');
  const ai = document.getElementById('ai-intake-lab');
  if (!lab || document.getElementById('source-vault-panel')) return;

  const companyId = lab.dataset.companyId;
  const anchor = ai || lab;
  const categories = [
    ['other','Unclassified / Other · 未分類'],
    ['customers','Customers & Contacts · 客戶與聯絡人'],
    ['products','Products / Specs / Materials · 產品／規格／材料'],
    ['quotes','Quotations / Pricing / Costs · 報價／價格／成本'],
    ['work_orders','Orders / Work Orders · 訂單／工單'],
    ['reports','Management Reports · 管理報表'],
  ];

  const style = document.createElement('style');
  style.textContent = `
    #source-vault-panel{margin-top:16px}.sv-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.sv-badge{font-size:8px;font-weight:800;letter-spacing:.05em;border:1px solid #d7e1dd;background:#f5f8f7;color:#526462;padding:6px 9px;border-radius:999px;white-space:nowrap}.sv-badge.ready{background:#edf7f3;border-color:#c7dfd5;color:#2f6659}.sv-badge.warn{background:#fff8e9;border-color:#eadab2;color:#7c642e}.sv-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:13px}.sv-card{border:1px solid #e1e7e4;border-radius:7px;background:#fff;padding:11px}.sv-card span{display:block;font-size:8px;font-weight:800;letter-spacing:.06em;color:#7a8889}.sv-card b{display:block;font-size:17px;margin-top:5px}.sv-note{font-size:9px;color:#697879;line-height:1.55}.sv-upload{display:grid;grid-template-columns:1fr 220px auto;gap:9px;align-items:end;margin-top:13px;border-top:1px solid #e7ebea;padding-top:12px}.sv-upload label{font-size:8px;font-weight:800;color:#697879;letter-spacing:.05em}.sv-upload input,.sv-upload select{margin-top:5px;width:100%;box-sizing:border-box;border:1px solid #d9e1de;border-radius:6px;padding:8px;background:#fff;font-size:10px}.sv-upload button{border:0;border-radius:6px;background:#1f5f55;color:white;padding:9px 13px;font-weight:800;cursor:pointer;min-width:140px}.sv-upload button:disabled{opacity:.45;cursor:not-allowed}.sv-table{width:100%;border-collapse:collapse;font-size:9px;margin-top:12px}.sv-table th,.sv-table td{text-align:left;padding:8px;border-bottom:1px solid #edf0ef;vertical-align:top}.sv-table th{font-size:8px;color:#6d7b7c}.sv-status{margin-top:9px;padding:8px 10px;border-radius:6px;background:#f4f6f5;font-size:9px;color:#647273}.sv-status.ok{background:#edf7f3;color:#2f6659}.sv-status.err{background:#fff0ee;color:#8a4035}.sv-open{font-size:8px;font-weight:800;text-decoration:none;color:#246257}.sv-unretained{opacity:.58}.sv-sourceid{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:8px}.sv-principle{margin-top:10px;padding:9px 10px;border-radius:6px;background:#fbfaf5;border:1px solid #eee8d8;font-size:9px;color:#6a6658}@media(max-width:900px){.sv-head{flex-direction:column}.sv-metrics{grid-template-columns:1fr}.sv-upload{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  const panel = document.createElement('section');
  panel.id = 'source-vault-panel';
  panel.className = 'panel';
  panel.innerHTML = `
    <div class="sv-head">
      <div>
        <span class="eyebrow">SOURCE VAULT · 原始資料庫 · v${VERSION}</span>
        <h2 style="margin:5px 0 4px">Retain the original → preserve lineage → analyze safely</h2>
        <p class="sv-note" style="margin:0;max-width:800px">For real client files, Source Vault keeps the original privately and links every inspection back to a SHA-256 source record. Analysis can change; the original evidence does not.</p>
      </div>
      <span class="sv-badge" id="sv-config">Checking private storage…</span>
    </div>
    <div class="sv-metrics">
      <div class="sv-card"><span>REGISTERED FILES</span><b id="sv-registered">—</b><div class="sv-note">Client OS inventory</div></div>
      <div class="sv-card"><span>ORIGINALS RETAINED</span><b id="sv-vaulted">—</b><div class="sv-note">Private source objects with lineage</div></div>
      <div class="sv-card"><span>LINEAGE COVERAGE</span><b id="sv-coverage">—</b><div class="sv-note">Retained originals / registered files</div></div>
    </div>
    <div class="sv-principle"><b>PrimeStride rule:</b> messy is acceptable; unverifiable is not. Screenshots, scans, photos, Excel and PDFs are all valid inputs when the original source is retained and reviewable.</div>
    <div class="sv-upload">
      <div><label>ORIGINAL FILE · 原始檔<input type="file" id="sv-file"></label></div>
      <div><label>INITIAL CATEGORY · 初始分類<select id="sv-category">${categories.map(([v,l])=>`<option value="${v}">${l}</option>`).join('')}</select></label></div>
      <button id="sv-upload" disabled>Store Original Privately</button>
    </div>
    <div class="sv-status" id="sv-status">Source Vault is optional in this preview. Existing local/AI analysis remains available.</div>
    <div style="overflow:auto"><table class="sv-table"><thead><tr><th>FILE</th><th>CATEGORY</th><th>SOURCE ID / SHA</th><th>STORAGE</th><th>STATE</th><th></th></tr></thead><tbody id="sv-files"><tr><td colspan="6">Loading source lineage…</td></tr></tbody></table></div>
  `;
  anchor.insertAdjacentElement('afterend', panel);

  const badge = panel.querySelector('#sv-config');
  const uploadBtn = panel.querySelector('#sv-upload');
  const input = panel.querySelector('#sv-file');
  const category = panel.querySelector('#sv-category');
  const status = panel.querySelector('#sv-status');
  const tbody = panel.querySelector('#sv-files');
  let configured = false;
  let storageStatus = null;

  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function fmtBytes(n){const x=Number(n||0);if(x<1024)return `${x} B`;if(x<1024*1024)return `${(x/1024).toFixed(1)} KB`;return `${(x/1024/1024).toFixed(1)} MB`;}
  function setStatus(text,kind=''){status.className=`sv-status ${kind}`.trim();status.textContent=text;}

  async function loadStatus(){
    try{
      const res=await fetch('/api/source-vault/status',{headers:{'Accept':'application/json'}});
      storageStatus=await res.json(); configured=!!storageStatus.configured;
      if(configured){badge.textContent=`PRIVATE STORAGE READY · ${storageStatus.provider}`;badge.className='sv-badge ready';uploadBtn.disabled=!input.files[0];}
      else{badge.textContent='STORAGE FOUNDATION INSTALLED · CONFIGURATION NEEDED';badge.className='sv-badge warn';uploadBtn.disabled=true;setStatus('Source Vault code is live, but no private S3-compatible bucket is configured in this environment yet. Nothing will be uploaded until storage credentials are added.');}
    }catch(err){badge.textContent='SOURCE VAULT STATUS UNAVAILABLE';badge.className='sv-badge warn';setStatus(err.message||String(err),'err');}
  }

  async function loadFiles(){
    try{
      const res=await fetch(`/companies/${companyId}/source-vault/files`,{headers:{'Accept':'application/json'}});
      const data=await res.json(); if(!res.ok) throw new Error(data.error||'Could not load Source Vault inventory.');
      panel.querySelector('#sv-registered').textContent=data.registered_count;
      panel.querySelector('#sv-vaulted').textContent=data.vaulted_count;
      const pct=data.registered_count?Math.round(data.vaulted_count/data.registered_count*100):0;
      panel.querySelector('#sv-coverage').textContent=`${pct}%`;
      const rows=[];
      for(const f of data.vaulted||[]){rows.push(`<tr><td><b>${esc(f.filename)}</b><div class="sv-note">${fmtBytes(f.bytes)} · ${esc(f.content_type||'')}</div></td><td>${esc(f.category)}</td><td><span class="sv-sourceid">${esc(f.source_id||'—')}</span><div class="sv-note">SHA ${esc((f.sha256||'').slice(0,12))}…</div></td><td>${esc(f.storage_provider||'Private object storage')}<div class="sv-note">immutable source</div></td><td>Retained</td><td><a class="sv-open" target="_blank" rel="noopener" href="/companies/${companyId}/source-vault/files/${f.file_id}/open">Open original ↗</a></td></tr>`);}
      for(const f of data.unretained||[]){rows.push(`<tr class="sv-unretained"><td><b>${esc(f.filename)}</b></td><td>${esc(f.category)}</td><td>—</td><td>Original not retained</td><td>${esc(f.status||'Registered')}</td><td></td></tr>`);}
      tbody.innerHTML=rows.join('')||'<tr><td colspan="6">No registered source files yet.</td></tr>';
    }catch(err){tbody.innerHTML=`<tr><td colspan="6">${esc(err.message||String(err))}</td></tr>`;}
  }

  input.addEventListener('change',()=>{uploadBtn.disabled=!configured||!input.files[0];});
  uploadBtn.addEventListener('click',async()=>{
    if(!configured||!input.files[0])return;
    const file=input.files[0]; uploadBtn.disabled=true; setStatus(`Retaining original ${file.name} privately…`);
    try{
      const fd=new FormData();fd.append('file',file,file.name);fd.append('category',category.value);
      const res=await fetch(`/companies/${companyId}/source-vault/upload`,{method:'POST',body:fd});
      let data;try{data=await res.json();}catch{data={error:await res.text()};}
      if(!res.ok)throw new Error(data.error+(data.detail?` · ${data.detail}`:''));
      setStatus(`${data.deduplicated?'Linked existing inventory record to':'Stored'} ${file.name}. Source ${data.file.source_id}; SHA-256 ${(data.file.sha256||'').slice(0,12)}…`,'ok');
      input.value=''; uploadBtn.disabled=true; await loadFiles();
    }catch(err){setStatus(err.message||String(err),'err');uploadBtn.disabled=!configured||!input.files[0];}
  });

  Promise.all([loadStatus(),loadFiles()]);
})();
