(() => {
  const VERSION = '0.9.2';
  const ai = document.getElementById('ai-intake-lab');
  if (!ai) return;

  const eyebrow = ai.querySelector('.ai09-head .eyebrow');
  if (eyebrow) eyebrow.textContent = `AI-ASSISTED MULTIMODAL INTAKE · v${VERSION}`;

  const style = document.createElement('style');
  style.textContent = `
    .ai092-structured{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(280px,.6fr);gap:12px;margin-top:12px}
    .ai092-table{width:100%;border-collapse:collapse;font-size:9px}.ai092-table th,.ai092-table td{padding:7px 8px;border-bottom:1px solid #edf0ef;text-align:left;vertical-align:top}.ai092-table th{font-size:8px;color:#697879}.ai092-kind{display:inline-block;font-size:8px;font-weight:800;border:1px solid #d7e3de;border-radius:999px;padding:3px 6px;background:#f5faf8;color:#42675f}.ai092-kind.constraint{background:#fff8ea;border-color:#e9d8ac;color:#79602b}.ai092-kind.exception,.ai092-kind.incident{background:#fff0ee;border-color:#e6c5bf;color:#8b4438}.ai092-empty{font-size:9px;color:#778587;padding:8px 0}.ai092-section-note{font-size:8px;color:#7a8889;margin-top:2px}@media(max-width:900px){.ai092-structured{grid-template-columns:1fr}}
  `;
  document.head.appendChild(style);

  const originalFetch = window.fetch.bind(window);
  let lastAnalysis = null;
  window.fetch = async function(input, init = {}) {
    const res = await originalFetch(input, init);
    try {
      const url = typeof input === 'string' ? input : (input?.url || '');
      if (url.includes('/ai-intake/analyze')) {
        const clone = res.clone();
        const data = await clone.json();
        if (data?.ok && data?.result) {
          lastAnalysis = data;
          queueMicrotask(renderStructured);
          setTimeout(renderStructured, 40);
        }
      }
      if (init?.body instanceof URLSearchParams) {
        const notes = init.body.get('notes');
        if (notes && /v0\.9(?:\.1)?/i.test(notes)) {
          init.body.set('notes', notes.replace(/v0\.9(?:\.1)?/gi, `v${VERSION}`));
        }
      }
    } catch (_) {}
    return res;
  };

  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function val(v){return v && String(v).trim() ? esc(v) : '<span style="color:#a1aaaa">—</span>';}

  function renderStructured(){
    if (!lastAnalysis?.result) return;
    const results = document.getElementById('ai09-results');
    const savebar = results?.querySelector('.ai09-save');
    if (!results || !savebar) return;

    let wrap = document.getElementById('ai092-structured');
    if (!wrap) {
      wrap = document.createElement('div');
      wrap.id = 'ai092-structured';
      wrap.className = 'ai092-structured';
      savebar.insertAdjacentElement('beforebegin', wrap);
    }

    const r = lastAnalysis.result;
    const ops = r.operations || [];
    const instructions = r.instructions || [];

    wrap.innerHTML = `
      <section class="ai09-card">
        <h3 class="ai09-section-title">Structured Operations · 結構化製程</h3>
        <div class="ai092-section-note">Schedule rows reconstructed as operations. Planned and actual timestamps stay separate.</div>
        ${ops.length ? `<div style="overflow:auto;margin-top:7px"><table class="ai092-table"><thead><tr><th>#</th><th>STAGE</th><th>PLANNED START</th><th>PLANNED END</th><th>ACTUAL START</th><th>ACTUAL END</th><th>ASSIGNEE</th><th>MACHINE</th><th>NOTE</th><th>CONF.</th></tr></thead><tbody>${ops.map((o,i)=>`<tr><td>${i+1}</td><td><b>${val(o.stage)}</b></td><td>${val(o.planned_start)}</td><td>${val(o.planned_end)}</td><td>${val(o.actual_start)}</td><td>${val(o.actual_end)}</td><td>${val(o.assignee)}</td><td>${val(o.machine)}</td><td>${val(o.note)}</td><td><b>${Number(o.confidence||0)}%</b></td></tr>`).join('')}</tbody></table></div>` : '<div class="ai092-empty">No operation table reconstructed from this document.</div>'}
      </section>
      <section class="ai09-card">
        <h3 class="ai09-section-title">Instructions / Constraints / Exceptions · 指示與例外</h3>
        <div class="ai09-list" style="margin-top:7px">
          ${instructions.length ? instructions.map(x=>`<div class="ai09-item"><div><span class="ai092-kind ${esc(x.kind)}">${esc(x.kind)}</span><b style="margin-top:6px">${esc(x.text)}</b><small>${x.canonical_target?esc(x.canonical_target)+' · ':''}${Number(x.confidence||0)}% · ${esc(x.evidence||'')}</small></div></div>`).join('') : '<div class="ai092-empty">No instruction/constraint/exception items separated from general notes.</div>'}
        </div>
      </section>
    `;

    // Make section/semantic context visible in the existing field table without
    // replacing v0.9's review UI.
    const rows = document.querySelectorAll('#ai09-fields tr');
    (r.fields || []).forEach((f, i) => {
      const td = rows[i]?.querySelector('td');
      if (!td || td.querySelector('.ai092-section-note')) return;
      const note = document.createElement('div');
      note.className = 'ai092-section-note';
      note.textContent = [f.source_section, f.semantic_role].filter(Boolean).join(' · ');
      td.appendChild(note);
    });
  }

  const observer = new MutationObserver(() => {
    if (lastAnalysis) renderStructured();
  });
  const results = document.getElementById('ai09-results');
  if (results) observer.observe(results, {childList:true, subtree:true, attributes:true, attributeFilter:['class']});
})();
