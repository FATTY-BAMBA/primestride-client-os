(() => {
  const VERSION = '1.0.1';
  const panel = document.getElementById('source-vault-panel');
  const lab = document.getElementById('ingestion-lab');
  if (!panel || !lab) return;

  const companyId = lab.dataset.companyId;
  const fileInput = panel.querySelector('#sv-file');
  const category = panel.querySelector('#sv-category');
  const oldButton = panel.querySelector('#sv-upload');
  const status = panel.querySelector('#sv-status');
  if (!fileInput || !category || !oldButton || !status) return;

  // v1.0's button already owns a storage-only listener. Clone it so v1.0.1 can
  // replace that split workflow with one source-first action without double upload.
  const button = oldButton.cloneNode(true);
  oldButton.replaceWith(button);
  button.id = 'sv-upload';
  button.textContent = 'Retain + Analyze';

  const headEyebrow = panel.querySelector('.eyebrow');
  if (headEyebrow) headEyebrow.textContent = `SOURCE-FIRST INTAKE · 統一資料入口 · v${VERSION}`;
  const heading = panel.querySelector('h2');
  if (heading) heading.textContent = 'Upload once → retain original → route to the right analysis';
  const intro = panel.querySelector('.sv-head p');
  if (intro) intro.textContent = 'Every new client file is retained privately first. Client OS then routes structured data to the deterministic inspector and PDFs/photos/scans to AI-assisted review.';

  const principle = panel.querySelector('.sv-principle');
  if (principle) principle.innerHTML = '<b>PrimeStride rule:</b> messy is acceptable; unverifiable is not. One upload preserves the original before any interpretation begins.';

  const helper = document.createElement('div');
  helper.className = 'sv-principle';
  helper.style.background = '#f3f8f6';
  helper.innerHTML = '<b>Automatic routing:</b> CSV / TSV / JSON / XLSX → deterministic inspection · PDF / JPG / PNG / WEBP → multimodal AI review · other files → retained safely for manual review.';
  principle?.insertAdjacentElement('afterend', helper);

  const tenantNote = document.createElement('div');
  tenantNote.className = 'sv-note';
  tenantNote.style.marginTop = '7px';
  tenantNote.textContent = 'Resolving tenant storage path…';
  panel.querySelector('.sv-head > div')?.appendChild(tenantNote);

  const structuredExt = new Set(['csv','tsv','json','xlsx']);
  const aiExt = new Set(['pdf','jpg','jpeg','png','webp']);
  let configured = false;

  function ext(file){
    const name = String(file?.name || '');
    const idx = name.lastIndexOf('.');
    return idx >= 0 ? name.slice(idx + 1).toLowerCase() : '';
  }
  function setStatus(text, kind=''){
    status.className = `sv-status ${kind}`.trim();
    status.textContent = text;
  }
  function assignFile(input, file){
    if (!input) return false;
    try {
      const dt = new DataTransfer();
      dt.items.add(file);
      input.files = dt.files;
      input.dispatchEvent(new Event('change', {bubbles:true}));
      return true;
    } catch (_) {
      return false;
    }
  }
  function routeToAnalysis(file){
    const e = ext(file);
    if (structuredExt.has(e)) {
      const target = document.getElementById('ingestion-file');
      const ok = assignFile(target, file);
      document.getElementById('ingestion-lab')?.scrollIntoView({behavior:'smooth', block:'start'});
      return ok ? 'deterministic' : 'retained';
    }
    if (aiExt.has(e) || String(file.type || '').startsWith('image/') || file.type === 'application/pdf') {
      const target = document.getElementById('ai09-file');
      const ok = assignFile(target, file);
      document.getElementById('ai-intake-lab')?.scrollIntoView({behavior:'smooth', block:'start'});
      return ok ? 'ai' : 'retained';
    }
    return 'retained';
  }

  async function refreshVault(){
    try {
      const res = await fetch(`/companies/${companyId}/source-vault/files`, {headers:{'Accept':'application/json'}});
      const data = await res.json();
      if (!res.ok) return;
      const registered = panel.querySelector('#sv-registered');
      const vaulted = panel.querySelector('#sv-vaulted');
      const coverage = panel.querySelector('#sv-coverage');
      if (registered) registered.textContent = data.registered_count;
      if (vaulted) vaulted.textContent = data.vaulted_count;
      if (coverage) coverage.textContent = `${data.registered_count ? Math.round(data.vaulted_count/data.registered_count*100) : 0}%`;

      const tbody = panel.querySelector('#sv-files');
      if (!tbody) return;
      const esc = v => String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
      const fmt = n => {const x=Number(n||0);if(x<1024)return `${x} B`;if(x<1024*1024)return `${(x/1024).toFixed(1)} KB`;return `${(x/1024/1024).toFixed(1)} MB`;};
      const rows = [];
      for (const f of data.vaulted || []) rows.push(`<tr><td><b>${esc(f.filename)}</b><div class="sv-note">${fmt(f.bytes)} · ${esc(f.content_type||'')}</div></td><td>${esc(f.category)}</td><td><span class="sv-sourceid">${esc(f.source_id||'—')}</span><div class="sv-note">SHA ${esc((f.sha256||'').slice(0,12))}…</div></td><td>${esc(f.storage_provider||'Private object storage')}<div class="sv-note">immutable source</div></td><td>Retained</td><td><a class="sv-open" target="_blank" rel="noopener" href="/companies/${companyId}/source-vault/files/${f.file_id}/open">Open original ↗</a></td></tr>`);
      for (const f of data.unretained || []) rows.push(`<tr class="sv-unretained"><td><b>${esc(f.filename)}</b></td><td>${esc(f.category)}</td><td>—</td><td>Original not retained</td><td>${esc(f.status||'Registered')}</td><td></td></tr>`);
      tbody.innerHTML = rows.join('') || '<tr><td colspan="6">No registered source files yet.</td></tr>';
    } catch (_) {}
  }

  async function loadSourceFirstStatus(){
    try {
      const res = await fetch(`/companies/${companyId}/source-first/status`, {headers:{'Accept':'application/json'}});
      const data = await res.json();
      configured = !!data.configured;
      button.disabled = !configured || !fileInput.files[0];
      if (data.tenant_key) tenantNote.textContent = `Tenant storage key: ${data.tenant_key} · ${data.path_pattern}`;
    } catch (_) {
      tenantNote.textContent = 'Tenant path unavailable; Source Vault status will control uploads.';
    }
  }

  fileInput.addEventListener('change', () => {
    button.disabled = !configured || !fileInput.files[0];
    if (fileInput.files[0]) setStatus(`Ready to retain and analyze ${fileInput.files[0].name}.`);
  });

  button.addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!configured || !file) return;
    button.disabled = true;
    setStatus(`1/2 Retaining original ${file.name} privately…`);
    try {
      const fd = new FormData();
      fd.append('file', file, file.name);
      fd.append('category', category.value);
      const res = await fetch(`/companies/${companyId}/source-vault/upload`, {method:'POST', body:fd});
      let data;
      try { data = await res.json(); } catch { data = {error: await res.text()}; }
      if (!res.ok) throw new Error((data.error || 'Source Vault upload failed.') + (data.detail ? ` · ${data.detail}` : ''));

      await refreshVault();
      const route = routeToAnalysis(file);
      const path = data.file?.tenant_key ? ` · ${data.file.tenant_key}` : '';
      if (route === 'deterministic') {
        setStatus(`2/2 Original retained${path}. Routed to deterministic inspection. Source ${data.file?.source_id || 'created'}; SHA ${(data.file?.sha256||'').slice(0,12)}…`, 'ok');
      } else if (route === 'ai') {
        setStatus(`2/2 Original retained${path}. Routed to AI-assisted review in the background. Source ${data.file?.source_id || 'created'}; SHA ${(data.file?.sha256||'').slice(0,12)}…`, 'ok');
      } else {
        setStatus(`Original retained${path}. No automatic parser is assigned to this file type yet; keep it for manual review.`, 'ok');
      }
      fileInput.value = '';
    } catch (err) {
      setStatus(err.message || String(err), 'err');
    } finally {
      button.disabled = !configured || !fileInput.files[0];
    }
  });

  // Legacy direct drop zones remain available for debugging, but clarify that the
  // source-first door above is the normal production workflow.
  const directStructured = document.querySelector('#ingestion-lab .ingestion-drop');
  if (directStructured) directStructured.title = 'Advanced/direct inspection. Prefer Source-First Intake for real client files.';
  const directAI = document.querySelector('#ai09-drop');
  if (directAI) directAI.title = 'Advanced/direct AI inspection. Prefer Source-First Intake for real client files.';

  loadSourceFirstStatus();
})();
