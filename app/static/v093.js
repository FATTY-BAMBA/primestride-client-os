(() => {
  const VERSION = '0.9.3';
  const ai = document.getElementById('ai-intake-lab');
  if (!ai) return;

  const eyebrow = ai.querySelector('.ai09-head .eyebrow');
  if (eyebrow) eyebrow.textContent = `AI-ASSISTED MULTIMODAL INTAKE · v${VERSION}`;

  const statusEl = document.getElementById('ai09-status');
  const originalFetch = window.fetch.bind(window);
  let finalAnalysis = null;

  function sleep(ms){ return new Promise(resolve => setTimeout(resolve, ms)); }
  function jsonResponse(data, status=200){
    return new Response(JSON.stringify(data), {status, headers:{'Content-Type':'application/json'}});
  }
  function setProgress(text){
    if (!statusEl) return;
    statusEl.className = 'ai09-status';
    statusEl.textContent = text;
  }

  // Replace only the long synchronous AI analyze request. v0.9's existing UI
  // still owns file selection, rendering and save review; it simply receives the
  // final JSON after this wrapper completes the background polling loop.
  window.fetch = async function(input, init = {}) {
    const url = typeof input === 'string' ? input : (input?.url || '');
    if (!url.includes('/ai-intake/analyze') || String(init?.method || 'GET').toUpperCase() !== 'POST') {
      return originalFetch(input, init);
    }

    try {
      const startUrl = url.replace('/ai-intake/analyze', '/ai-intake/start');
      setProgress('Uploading securely for AI analysis…');
      const startRes = await originalFetch(startUrl, init);
      let startData;
      try { startData = await startRes.clone().json(); }
      catch { startData = {error: (await startRes.text()).slice(0,900)}; }
      if (!startRes.ok || !startData?.job_id) {
        return jsonResponse(startData || {error:'AI background job could not be started.'}, startRes.status || 502);
      }

      const jobId = startData.job_id;
      const companyMatch = url.match(/\/companies\/(\d+)\/ai-intake\/analyze/);
      const companyId = companyMatch ? companyMatch[1] : null;
      if (!companyId) return jsonResponse({error:'Could not determine company id for AI polling.', code:'missing_company_id'}, 500);

      const started = Date.now();
      const maxWaitMs = 180000;
      let pollCount = 0;
      try { sessionStorage.setItem(`ps_ai_job_${companyId}`, JSON.stringify({jobId, started, version:VERSION})); } catch (_) {}

      while (Date.now() - started < maxWaitMs) {
        pollCount++;
        const elapsed = Math.max(1, Math.round((Date.now()-started)/1000));
        setProgress(`AI is analyzing in the background… ${elapsed}s · you can stay on this page; Client OS is not blocked.`);
        await sleep(pollCount < 3 ? 1200 : 1800);

        const pollRes = await originalFetch(`/companies/${companyId}/ai-intake/jobs/${encodeURIComponent(jobId)}`, {headers:{'Accept':'application/json'}});
        let pollData;
        try { pollData = await pollRes.clone().json(); }
        catch { pollData = {error:(await pollRes.text()).slice(0,900)}; }

        if (!pollRes.ok) {
          try { sessionStorage.removeItem(`ps_ai_job_${companyId}`); } catch (_) {}
          return jsonResponse(pollData || {error:'AI background polling failed.'}, pollRes.status || 502);
        }

        if (pollData?.status === 'completed' && pollData?.result) {
          finalAnalysis = pollData;
          try { sessionStorage.removeItem(`ps_ai_job_${companyId}`); } catch (_) {}
          queueMicrotask(renderStructuredFromFinal);
          setTimeout(renderStructuredFromFinal, 80);
          return jsonResponse({
            ...pollData,
            filename: startData.filename,
            mime_type: startData.mime_type,
            model: pollData.model || startData.model,
          }, 200);
        }
      }

      return jsonResponse({
        error:'AI analysis is still running after 3 minutes. Nothing was saved. Please retry or return shortly; the app no longer waits on one long server request.',
        code:'background_job_timeout',
        job_id: jobId,
      }, 504);
    } catch (err) {
      return jsonResponse({error:err?.message || String(err), code:'background_client_error'}, 502);
    }
  };

  // v0.9.2's structured renderer cannot see the synthetic final response because
  // we no longer call the old /analyze route. Mirror the same structured display
  // from the final background result.
  function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function val(v){return v && String(v).trim() ? esc(v) : '<span style="color:#a1aaaa">—</span>';}
  function renderStructuredFromFinal(){
    if (!finalAnalysis?.result) return;
    const results = document.getElementById('ai09-results');
    const savebar = results?.querySelector('.ai09-save');
    if (!results || !savebar || !results.classList.contains('active')) { setTimeout(renderStructuredFromFinal, 120); return; }

    let wrap = document.getElementById('ai092-structured');
    if (!wrap) {
      wrap = document.createElement('div');
      wrap.id = 'ai092-structured';
      wrap.className = 'ai092-structured';
      savebar.insertAdjacentElement('beforebegin', wrap);
    }
    const r = finalAnalysis.result;
    const ops = r.operations || [];
    const instructions = r.instructions || [];
    wrap.innerHTML = `
      <section class="ai09-card">
        <h3 class="ai09-section-title">Structured Operations · 結構化製程</h3>
        <div class="ai092-section-note">Background AI reconstruction. Planned and actual timestamps stay separate.</div>
        ${ops.length ? `<div style="overflow:auto;margin-top:7px"><table class="ai092-table"><thead><tr><th>#</th><th>STAGE</th><th>PLANNED START</th><th>PLANNED END</th><th>ACTUAL START</th><th>ACTUAL END</th><th>ASSIGNEE</th><th>MACHINE</th><th>NOTE</th><th>CONF.</th></tr></thead><tbody>${ops.map((o,i)=>`<tr><td>${i+1}</td><td><b>${val(o.stage)}</b></td><td>${val(o.planned_start)}</td><td>${val(o.planned_end)}</td><td>${val(o.actual_start)}</td><td>${val(o.actual_end)}</td><td>${val(o.assignee)}</td><td>${val(o.machine)}</td><td>${val(o.note)}</td><td><b>${Number(o.confidence||0)}%</b></td></tr>`).join('')}</tbody></table></div>` : '<div class="ai092-empty">No operation table reconstructed from this document.</div>'}
      </section>
      <section class="ai09-card">
        <h3 class="ai09-section-title">Instructions / Constraints / Exceptions · 指示與例外</h3>
        <div class="ai09-list" style="margin-top:7px">
          ${instructions.length ? instructions.map(x=>`<div class="ai09-item"><div><span class="ai092-kind ${esc(x.kind)}">${esc(x.kind)}</span><b style="margin-top:6px">${esc(x.text)}</b><small>${x.canonical_target?esc(x.canonical_target)+' · ':''}${Number(x.confidence||0)}% · ${esc(x.evidence||'')}</small></div></div>`).join('') : '<div class="ai092-empty">No instruction/constraint/exception items separated from general notes.</div>'}
        </div>
      </section>`;

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

  const helper = document.createElement('div');
  helper.className = 'ai09-note';
  helper.style.marginTop = '8px';
  helper.textContent = 'v0.9.3 runs long AI document analysis as a background job, so the Client OS page stays responsive while results are polled.';
  ai.querySelector('.ai09-head')?.insertAdjacentElement('afterend', helper);
})();
