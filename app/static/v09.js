(() => {
  const lab = document.getElementById('ingestion-lab');
  if (!lab || document.getElementById('ai-intake-lab')) return;

  const companyId = lab.dataset.companyId;
  const categories = [
    ['customers','Customers & Contacts · 客戶與聯絡人'],
    ['products','Products / Specs / Materials · 產品／規格／材料'],
    ['quotes','Quotations / Pricing / Costs · 報價／價格／成本'],
    ['work_orders','Orders / Work Orders · 訂單／工單'],
    ['reports','Management Reports · 管理報表'],
    ['other','Other Process Material · 其他流程資料'],
  ];

  const style = document.createElement('style');
  style.textContent = `
    #ai-intake-lab{margin-top:16px}.ai09-head{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.ai09-badge{font-size:9px;font-weight:800;letter-spacing:.05em;border:1px solid #bed5cd;background:#eef7f3;color:#285c50;padding:6px 9px;border-radius:999px;white-space:nowrap}.ai09-drop{display:grid;place-items:center;text-align:center;min-height:150px;border:1px dashed #a9c9bd;border-radius:8px;margin-top:14px;cursor:pointer;background:#fbfdfc;padding:20px}.ai09-drop input{display:none}.ai09-drop strong{font-size:14px}.ai09-drop small{display:block;color:#718083;margin-top:7px;max-width:720px}.ai09-status{margin-top:10px;padding:9px 11px;border-radius:6px;background:#f3f6f5;color:#607073;font-size:10px}.ai09-status.ok{background:#eef7f3;color:#285c50}.ai09-status.err{background:#fff0ee;color:#8b3e32}.ai09-results{display:none;margin-top:14px}.ai09-results.active{display:block}.ai09-top{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}.ai09-card{border:1px solid #e0e6e3;border-radius:7px;padding:11px;background:#fff}.ai09-card span{display:block;font-size:8px;font-weight:800;color:#7b8989;letter-spacing:.07em}.ai09-card b{display:block;margin-top:5px;font-size:13px}.ai09-grid{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(280px,.75fr);gap:12px;margin-top:12px}.ai09-table{width:100%;border-collapse:collapse;font-size:9px}.ai09-table th,.ai09-table td{text-align:left;padding:8px;border-bottom:1px solid #edf0ef;vertical-align:top}.ai09-table th{font-size:8px;color:#697879}.ai09-conf{font-weight:800}.ai09-list{display:grid;gap:7px}.ai09-item{border:1px solid #e5e9e7;border-radius:6px;padding:8px;display:flex;gap:8px;align-items:flex-start}.ai09-item small{display:block;color:#718083;margin-top:3px}.ai09-save{display:flex;justify-content:space-between;gap:15px;align-items:center;border-top:1px solid #e3e8e6;margin-top:14px;padding-top:12px}.ai09-save p{margin:0;font-size:10px;color:#657476;max-width:760px}.ai09-save button{background:#1f5f55;color:white;border:0;border-radius:6px;padding:9px 13px;font-weight:800;cursor:pointer}.ai09-save button:disabled{opacity:.5}.ai09-preview{max-width:180px;max-height:120px;object-fit:contain;border-radius:5px;margin-top:8px;border:1px solid #e0e5e2}.ai09-note{font-size:9px;color:#748184;margin-top:5px}.ai09-muted{opacity:.48}.ai09-section-title{font-size:10px;font-weight:800;margin:0 0 8px}.ai09-summary{font-size:10px;line-height:1.55;color:#4f5d5f;margin:7px 0 0}.ai09-cols{display:grid;gap:10px}.ai09-question{font-size:9px;border-left:2px solid #dfb86f;padding:5px 8px;background:#fffaf1}.ai09-warning{font-size:9px;border-left:2px solid #c78476;padding:5px 8px;background:#fff7f5}@media(max-width:900px){.ai09-top,.ai09-grid{grid-template-columns:1fr}.ai09-head,.ai09-save{align-items:stretch;flex-direction:column}}
  `;
  document.head.appendChild(style);

  const section = document.createElement('section');
  section.id = 'ai-intake-lab';
  section.className = 'panel';
  section.innerHTML = `
    <div class="ai09-head">
      <div>
        <span class="eyebrow">AI-ASSISTED MULTIMODAL INTAKE · v0.9</span>
        <h2 style="margin:5px 0 4px">PDF / Photo / Scan → Extract → Propose → Review</h2>
        <p style="margin:0;color:#637274;font-size:10px;max-width:760px">Use this only when the deterministic structured-data path is not enough. AI extracts visible evidence and proposes canonical mappings; nothing becomes client truth until you approve and save it.</p>
      </div>
      <span class="ai09-badge" id="ai09-config">Checking AI configuration…</span>
    </div>
    <label class="ai09-drop" id="ai09-drop">
      <input id="ai09-file" type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/jpeg,image/png,image/webp">
      <div><strong>Drop a PDF, scan, screenshot or photo here</strong><small>檔案會送到已設定的 AI 模型做一次性分析；Client OS 目前不永久儲存原始位元組。圖片過大時會在瀏覽器中先縮小供分析。</small><div class="ingestion-support" style="margin-top:10px"><span>PDF</span><span>JPG</span><span>PNG</span><span>WEBP</span></div></div>
    </label>
    <div class="ai09-status" id="ai09-status">AI is the fallback semantic layer. CSV/XLSX should continue using the deterministic inspector above.</div>
    <div class="ai09-results" id="ai09-results">
      <div class="ai09-top">
        <div class="ai09-card"><span>DOCUMENT TYPE</span><b id="ai09-type">—</b></div>
        <div class="ai09-card"><span>INFERRED CATEGORY</span><b><select id="ai09-category" style="width:100%;padding:6px;border:1px solid #d9e0dd;border-radius:5px">${categories.map(([v,l])=>`<option value="${v}">${l}</option>`).join('')}</select></b></div>
        <div class="ai09-card"><span>MODEL / SOURCE</span><b id="ai09-model">—</b><div class="ai09-note" id="ai09-filemeta"></div></div>
      </div>
      <div class="ai09-grid">
        <section class="ai09-card"><h3 class="ai09-section-title">Extracted Fields & Canonical Suggestions · 擷取欄位與映射</h3><div style="overflow:auto"><table class="ai09-table"><thead><tr><th>SOURCE / VALUE</th><th>CANONICAL TARGET</th><th>CONF.</th><th>EVIDENCE</th></tr></thead><tbody id="ai09-fields"></tbody></table></div></section>
        <div class="ai09-cols">
          <section class="ai09-card"><h3 class="ai09-section-title">Summary · 摘要</h3><p class="ai09-summary" id="ai09-summary"></p><div id="ai09-preview-wrap"></div></section>
          <section class="ai09-card"><h3 class="ai09-section-title">Suggested Readiness Evidence · 建議證據</h3><div class="ai09-list" id="ai09-evidence"></div></section>
          <section class="ai09-card"><h3 class="ai09-section-title">Uncertainty / Review · 不確定項目</h3><div class="ai09-list" id="ai09-uncertainty"></div></section>
        </div>
      </div>
      <div class="ai09-save"><p><b>Human review remains the gate.</b> Saving registers metadata and only checked evidence. The source file itself is not persisted in this preview; full tenant-isolated object storage comes later.</p><div><button id="ai09-save">Register + Save Approved AI Evidence</button><div id="ai09-save-status" class="ai09-note"></div></div></div>
    </div>
  `;
  lab.insertAdjacentElement('afterend', section);

  const input = section.querySelector('#ai09-file');
  const drop = section.querySelector('#ai09-drop');
  const status = section.querySelector('#ai09-status');
  const config = section.querySelector('#ai09-config');
  const results = section.querySelector('#ai09-results');
  const saveBtn = section.querySelector('#ai09-save');
  let analysis = null;
  let sourceFile = null;
  let sourceHash = null;
  let configured = false;

  fetch('/api/ai-intake/status').then(r=>r.json()).then(s=>{
    configured = !!s.configured;
    config.textContent = configured ? `AI READY · ${s.model}` : 'AI NOT CONFIGURED';
    config.style.opacity = configured ? '1' : '.65';
    if (!configured) status.textContent = 'AI endpoint is installed but OPENAI_API_KEY is not configured in this environment. Deterministic CSV/XLSX ingestion still works.';
  }).catch(()=>{ config.textContent='AI STATUS UNAVAILABLE'; });

  drop.addEventListener('dragover', e=>{e.preventDefault();drop.style.background='#f2f8f5'});
  drop.addEventListener('dragleave', ()=>drop.style.background='');
  drop.addEventListener('drop', e=>{e.preventDefault();drop.style.background='';if(e.dataTransfer.files[0]) analyze(e.dataTransfer.files[0]);});
  input.addEventListener('change', ()=>input.files[0]&&analyze(input.files[0]));

  async function maybeCompressImage(file){
    if(!file.type.startsWith('image/') || file.size <= 2_800_000) return file;
    const url=URL.createObjectURL(file);
    try{
      const img=await new Promise((resolve,reject)=>{const x=new Image();x.onload=()=>resolve(x);x.onerror=reject;x.src=url;});
      const max=1800,scale=Math.min(1,max/Math.max(img.width,img.height));
      const c=document.createElement('canvas');c.width=Math.max(1,Math.round(img.width*scale));c.height=Math.max(1,Math.round(img.height*scale));c.getContext('2d').drawImage(img,0,0,c.width,c.height);
      const blob=await new Promise(r=>c.toBlob(r,'image/jpeg',0.9));
      return blob ? new File([blob], file.name.replace(/\.[^.]+$/, '')+'-ai-preview.jpg',{type:'image/jpeg'}) : file;
    } finally { URL.revokeObjectURL(url); }
  }

  async function sha256(file){const buf=await file.arrayBuffer(),d=await crypto.subtle.digest('SHA-256',buf);return[...new Uint8Array(d)].map(x=>x.toString(16).padStart(2,'0')).join('');}

  async function analyze(file){
    sourceFile=file; sourceHash=await sha256(file); analysis=null; results.classList.remove('active');
    if(!configured){status.className='ai09-status err';status.textContent='AI is not configured in this Vercel environment yet. Add OPENAI_API_KEY before testing multimodal analysis.';return;}
    status.className='ai09-status';status.textContent='Preparing file for AI analysis…';
    try{
      const sendFile=await maybeCompressImage(file);
      if(sendFile.size>3_500_000) throw new Error('This v0.9 preview limits PDF/image analysis to 3.5 MB. Images are compressed automatically; larger PDFs will move to background/object-storage ingestion later.');
      const fd=new FormData();fd.append('file',sendFile,sendFile.name);fd.append('client_context','Printing client. Priority modules: 04 AI Quoting, 05 Work Order & Production, 06 AI Analytics. Preserve source evidence and do not invent missing business rules.');
      status.textContent='AI is reading the document…';
      const res=await fetch(`/companies/${companyId}/ai-intake/analyze`,{method:'POST',body:fd});
      const data=await res.json();if(!res.ok)throw new Error(data.error+(data.detail?` · ${String(data.detail).slice(0,500)}`:''));
      analysis=data;render(file);status.className='ai09-status ok';status.textContent='AI extraction complete. Review every mapping/evidence item before saving.';
    }catch(err){status.className='ai09-status err';status.textContent=err.message||String(err);}
  }

  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function render(file){
    const r=analysis.result;results.classList.add('active');
    section.querySelector('#ai09-type').textContent=r.document_type||'Unknown';
    section.querySelector('#ai09-category').value=r.category||'other';
    section.querySelector('#ai09-model').textContent=analysis.model||'Configured AI';
    section.querySelector('#ai09-filemeta').textContent=`${file.name} · ${(file.size/1024).toFixed(1)} KB · SHA-256 ${sourceHash.slice(0,12)}…`;
    section.querySelector('#ai09-summary').textContent=r.summary||'No summary returned.';
    section.querySelector('#ai09-fields').innerHTML=(r.fields||[]).map(f=>`<tr><td><b>${esc(f.source_label||'')}</b><small style="display:block;margin-top:3px">${esc(f.value||'')}</small></td><td>${f.canonical_target?`<span class="mapping-target">${esc(f.canonical_target)}</span>`:'<span class="mapping-target none">Needs review</span>'}</td><td class="ai09-conf">${Number(f.confidence||0)}%</td><td>${esc(f.evidence||'')}</td></tr>`).join('')||'<tr><td colspan="4">No fields confidently extracted.</td></tr>';
    section.querySelector('#ai09-evidence').innerHTML=(r.readiness||[]).map((e,i)=>`<label class="ai09-item ${Number(e.confidence)<65?'ai09-muted':''}"><input type="checkbox" data-ai09-evidence="${i}" ${Number(e.confidence)>=65?'checked':''}><div><b>Module 0${e.module_no} · ${esc(e.criterion)}</b><small>${esc(e.status)} · ${Number(e.confidence)}% · ${esc(e.reason)}</small></div></label>`).join('')||'<div class="ai09-note">No readiness evidence proposed.</div>';
    const uncertainty=[...(r.quality_flags||[]).map(x=>['warn',x]),...(r.questions||[]).map(x=>['q',x]),...(r.do_not_infer||[]).map(x=>['warn','Do not infer: '+x])];
    section.querySelector('#ai09-uncertainty').innerHTML=uncertainty.map(([t,x])=>`<div class="${t==='q'?'ai09-question':'ai09-warning'}">${esc(x)}</div>`).join('')||'<div class="ai09-note">No additional uncertainty reported.</div>';
    const wrap=section.querySelector('#ai09-preview-wrap');wrap.innerHTML='';if(file.type.startsWith('image/')){const img=document.createElement('img');img.className='ai09-preview';img.src=URL.createObjectURL(file);wrap.appendChild(img);}
  }

  saveBtn.addEventListener('click', async()=>{
    if(!analysis||!sourceFile)return;saveBtn.disabled=true;const out=section.querySelector('#ai09-save-status');out.textContent='Saving reviewed proposals…';
    try{
      const r=analysis.result,category=section.querySelector('#ai09-category').value;
      const mappingSummary=(r.fields||[]).filter(f=>f.canonical_target).slice(0,30).map(f=>`${f.source_label}→${f.canonical_target}`).join('; ');
      const notes=`v0.9 AI multimodal proposal | document_type=${r.document_type} | model=${analysis.model} | sha256=${sourceHash} | mappings=${mappingSummary} | summary=${String(r.summary||'').slice(0,500)}`;
      await post(`/companies/${companyId}/data-intake/register`,{filename:sourceFile.name,category,source:'AI multimodal analysis',notes});
      const selected=[...section.querySelectorAll('[data-ai09-evidence]:checked')].map(el=>r.readiness[Number(el.dataset.ai09Evidence)]).filter(Boolean);
      for(const e of selected){await post(`/companies/${companyId}/readiness-evidence`,{module_no:String(e.module_no),criterion_key:e.criterion,status:e.status,source:sourceFile.name,notes:`v0.9 AI-assisted proposal (${e.confidence}% confidence): ${e.reason}. Human-approved before save.`});}
      out.textContent=`Saved metadata + ${selected.length} approved AI evidence item(s). Reloading…`;setTimeout(()=>location.reload(),700);
    }catch(err){out.textContent=err.message||String(err);saveBtn.disabled=false;}
  });

  async function post(url,obj){const body=new URLSearchParams(obj),res=await fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded;charset=UTF-8'},body,redirect:'follow'});if(!res.ok)throw new Error(`Save failed (${res.status})`);}
})();
