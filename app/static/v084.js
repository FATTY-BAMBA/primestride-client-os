(() => {
  const lab = document.getElementById('ingestion-lab');
  if (!lab) return;

  const VERSION = '0.8.4';
  const categorySelect = document.getElementById('inspection-category');
  const qualityBox = document.getElementById('quality-list');
  const detectedBody = document.getElementById('detected-fields-body');
  const evidenceBox = document.getElementById('evidence-suggestions');
  const previewTable = document.getElementById('preview-table');

  const metric = document.querySelector('.intake-summary-grid .intake-metric:nth-child(3) strong');
  if (metric) metric.textContent = `v${VERSION}`;
  const eyebrow = document.querySelector('.ingestion-lab .eyebrow');
  if (eyebrow) eyebrow.textContent = `INGESTION INTELLIGENCE · v${VERSION}`;

  const norm = value => String(value ?? '').trim().toLowerCase().replace(/[\s_\-\/()（）:：.]+/g, ' ');
  const statusNorm = value => {
    const s = norm(value);
    if (['completed','complete','done','finished','完成','已完成','完工','已完工'].includes(s)) return 'COMPLETED';
    if (['in progress','進行中','加工中','生產中'].includes(s)) return 'IN_PROGRESS';
    if (['pending','待處理','待加工','等待'].includes(s)) return 'PENDING';
    if (['delayed','delay','延誤','延期'].includes(s)) return 'DELAYED';
    if (['rework','重工','返工'].includes(s)) return 'REWORK';
    return s ? s.toUpperCase().replace(/\s+/g, '_') : '';
  };

  function currentCategory() {
    return categorySelect?.value || 'other';
  }

  function rowsFromPreview() {
    if (!previewTable) return { headers: [], rows: [] };
    const headers = [...previewTable.querySelectorAll('thead th')].map(x => x.textContent.trim());
    const rows = [...previewTable.querySelectorAll('tbody tr')].map(tr => [...tr.querySelectorAll('td')].map(td => td.textContent.trim()));
    return { headers, rows };
  }

  function findIndex(headers, aliases) {
    const wanted = aliases.map(norm);
    return headers.findIndex(h => wanted.includes(norm(h)));
  }

  function addQuality(level, title, detail, key) {
    if (!qualityBox || qualityBox.querySelector(`[data-ps084="${key}"]`)) return;
    const div = document.createElement('div');
    div.className = `quality-item ${level}`;
    div.dataset.ps084 = key;
    div.innerHTML = `<span>${level === 'ok' ? '✓' : '△'}</span><div><b>${title}</b><small>${detail}</small></div>`;
    qualityBox.appendChild(div);
  }

  function removeGenericMissingWarning(pattern) {
    if (!qualityBox) return;
    for (const item of [...qualityBox.querySelectorAll('.quality-item')]) {
      const title = item.querySelector('b')?.textContent || '';
      if (pattern.test(title)) item.remove();
    }
  }

  function contextualMappings() {
    if (!detectedBody || currentCategory() !== 'work_orders') return;
    for (const row of [...detectedBody.querySelectorAll('tr')]) {
      const cells = row.querySelectorAll('td');
      if (cells.length < 3) continue;
      const source = norm(cells[0].querySelector('b')?.textContent || '');
      const target = cells[1].querySelector('.mapping-target');
      const confidence = cells[2].querySelector('.confidence');
      if (!target) continue;

      if (['數量','quantity','qty','訂購數量'].includes(source)) {
        target.textContent = 'WorkOrderLine.quantity';
        target.dataset.ps084Target = 'WorkOrderLine.quantity';
      }

      if (['品名 規格','品名規格','product specification','product spec'].includes(source) || source.includes('品名 規格')) {
        target.textContent = 'Product.name + Specification.value ?';
        target.dataset.ps084Target = 'Product.name + Specification.value';
        target.classList.remove('high');
        if (confidence) {
          confidence.textContent = 'Needs review';
          confidence.classList.remove('high');
          confidence.classList.add('medium');
        }
        row.title = 'Compound source field detected. Keep the raw value, then split product name/specification only after review.';
      }
    }

    if (evidenceBox) {
      for (const label of [...evidenceBox.querySelectorAll('.evidence-suggestion')]) {
        const small = label.querySelector('small');
        if (!small) continue;
        small.textContent = small.textContent.replace(/QuoteLine\.quantity/g, 'WorkOrderLine.quantity');
      }
    }
  }

  function semanticQuality() {
    if (!qualityBox || currentCategory() !== 'work_orders') return;
    const { headers, rows } = rowsFromPreview();
    if (!headers.length || !rows.length) return;

    const statusI = findIndex(headers, ['目前狀態','狀態','status','current status']);
    const completionI = findIndex(headers, ['完成時間','實際完成','end time','actual end','completed at','completion date']);
    const exceptionI = findIndex(headers, ['例外備註','異常原因','延誤原因','重工原因','exception','exception note','delay reason','rework reason']);
    if (statusI < 0) return;

    const variants = new Map();
    for (const row of rows) {
      const raw = row[statusI] || '';
      if (!raw) continue;
      const canonical = statusNorm(raw);
      if (!variants.has(raw)) variants.set(raw, canonical);
    }
    if (variants.size) {
      const text = [...variants.entries()].map(([raw, canonical]) => `${raw} → ${canonical}`).join(' · ');
      addQuality('ok', 'Proposed status normalization', text, 'status-normalization');
    }

    if (completionI >= 0) {
      removeGenericMissingWarning(/high missing rate:\s*(完成時間|實際完成|completion|completed|end time)/i);
      const completed = rows.filter(r => statusNorm(r[statusI]) === 'COMPLETED');
      const missingCompleted = completed.filter(r => !(r[completionI] || '').trim());
      const activeMissing = rows.filter(r => statusNorm(r[statusI]) !== 'COMPLETED' && !(r[completionI] || '').trim()).length;
      if (missingCompleted.length) {
        addQuality('warn', 'Completed jobs missing completion time', `${missingCompleted.length} completed preview row(s) have no completion timestamp. ${activeMissing} blank completion time(s) belong to non-completed rows and may be expected.`, 'completion-context');
      } else {
        addQuality('ok', 'Completion-time blanks are status-consistent', `All ${completed.length} completed preview row(s) have completion timestamps. ${activeMissing} blank completion time(s) belong to non-completed rows and are treated as expected in this preview.`, 'completion-context');
      }
    }

    if (exceptionI >= 0) {
      removeGenericMissingWarning(/high missing rate:\s*(例外備註|異常|exception|delay|rework)/i);
      const exceptionRows = rows.filter(r => ['DELAYED','REWORK'].includes(statusNorm(r[statusI])));
      const missingException = exceptionRows.filter(r => !(r[exceptionI] || '').trim());
      if (!exceptionRows.length) {
        addQuality('ok', 'No exception-status rows in preview', 'Blank exception notes are not treated as missing business data when the job has no exception status.', 'exception-context');
      } else if (missingException.length) {
        addQuality('warn', 'Exception rows missing explanation', `${missingException.length} of ${exceptionRows.length} delayed/rework preview row(s) have no exception note.`, 'exception-context');
      } else {
        addQuality('ok', 'Exception notes complete where required', `All ${exceptionRows.length} delayed/rework preview row(s) include an exception explanation. Blank notes on normal jobs are treated as expected.`, 'exception-context');
      }
    }
  }

  function refreshQualityStat() {
    const stat = document.getElementById('stat-quality');
    if (!stat || !qualityBox) return;
    const issues = [...qualityBox.querySelectorAll('.quality-item')].filter(item => !item.classList.contains('ok')).length;
    stat.textContent = String(issues);
  }

  function apply() {
    contextualMappings();
    semanticQuality();
    refreshQualityStat();
  }

  // Persist the contextual mapping/provenance that the reviewer actually saw.
  const previousFetch = window.fetch.bind(window);
  window.fetch = function(input, init = {}) {
    try {
      if (init?.body instanceof URLSearchParams) {
        const category = currentCategory();
        const notes = init.body.get('notes');
        if (notes) {
          let value = notes.replaceAll('v0.8.1', `v${VERSION}`).replaceAll('v0.8.3', `v${VERSION}`);
          if (category === 'work_orders') {
            value = value
              .replace(/數量→QuoteLine\.quantity/g, '數量→WorkOrderLine.quantity')
              .replace(/Quantity→QuoteLine\.quantity/g, 'Quantity→WorkOrderLine.quantity')
              .replace(/品名\/規格→Product\.name/g, '品名/規格→Product.name + Specification.value');
          }
          init.body.set('notes', value);
        }
      }
    } catch (_) {}
    return previousFetch(input, init);
  };

  categorySelect?.addEventListener('change', () => setTimeout(apply, 0));

  const observer = new MutationObserver(() => {
    requestAnimationFrame(apply);
  });
  if (detectedBody) observer.observe(detectedBody, { childList: true, subtree: true });
  if (qualityBox) observer.observe(qualityBox, { childList: true, subtree: true });
  if (evidenceBox) observer.observe(evidenceBox, { childList: true, subtree: true });
  if (previewTable) observer.observe(previewTable, { childList: true, subtree: true });

  apply();
})();
