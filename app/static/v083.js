(() => {
  const lab = document.getElementById('ingestion-lab');
  if (!lab) return;

  const VERSION = '0.8.3';
  const categorySelect = document.getElementById('inspection-category');
  const evidenceBox = document.getElementById('evidence-suggestions');
  const qualityBox = document.getElementById('quality-list');

  // Keep every visible ingestion label on the same version.
  const metric = document.querySelector('.intake-summary-grid .intake-metric:nth-child(3) strong');
  if (metric) metric.textContent = `v${VERSION}`;
  const eyebrow = document.querySelector('.ingestion-lab .eyebrow');
  if (eyebrow) eyebrow.textContent = `INGESTION INTELLIGENCE · v${VERSION}`;

  const POLICY = {
    quotes: {
      4: '*',
      6: new Set(['quote_history', 'customer_product', 'time_fields', 'cost', 'margin'])
    },
    work_orders: {
      5: '*',
      6: new Set(['work_order_history', 'customer_product', 'time_fields', 'production_events'])
    },
    reports: {
      6: '*'
    },
    customers: {
      4: new Set(['customer_identity']),
      6: new Set(['customer_product'])
    },
    products: {
      4: new Set(['product_spec']),
      5: new Set(['product_spec'])
    },
    other: {}
  };

  function parseEvidence(label) {
    const title = label.querySelector('b')?.textContent || '';
    const match = title.match(/Module\s+0?(\d+)\s*·\s*([\w-]+)/i);
    if (!match) return null;
    return { moduleNo: Number(match[1]), criterion: match[2] };
  }

  function inScope(category, item) {
    const byModule = POLICY[category] || POLICY.other;
    const rule = byModule[item.moduleNo];
    if (rule === '*') return true;
    return rule instanceof Set ? rule.has(item.criterion) : false;
  }

  function scopeEvidence() {
    if (!evidenceBox || !categorySelect) return;
    const category = categorySelect.value || 'other';
    const labels = [...evidenceBox.querySelectorAll('.evidence-suggestion')];
    for (const label of labels) {
      const item = parseEvidence(label);
      if (!item) continue;
      const checkbox = label.querySelector('input[type="checkbox"]');
      if (!checkbox) continue;
      const scoped = inScope(category, item);
      if (!label.dataset.ps083Scoped) {
        label.dataset.ps083Scoped = '1';
        label.dataset.ps083OriginalChecked = checkbox.checked ? '1' : '0';
      }
      if (!scoped) {
        checkbox.checked = false;
        label.style.opacity = '0.48';
        label.title = 'Detected, but not primary readiness evidence for this dataset type. You can still re-check it manually.';
        const em = label.querySelector('em');
        if (em && !em.dataset.ps083Label) {
          em.dataset.ps083Label = em.textContent || '';
          em.textContent = 'supporting only';
        }
      } else {
        label.style.opacity = '';
        label.title = '';
        const em = label.querySelector('em');
        if (em?.dataset.ps083Label) em.textContent = em.dataset.ps083Label;
      }
    }
  }

  function denoiseRegionCandidates() {
    if (!qualityBox) return;
    const items = [...qualityBox.querySelectorAll('.quality-item')];
    for (const item of items) {
      const title = item.querySelector('b');
      const detail = item.querySelector('small');
      if (!title || !/alternate table-like region|additional table-like region/i.test(title.textContent || '')) continue;
      title.textContent = 'Additional table candidates scanned';
      if (detail) detail.textContent = 'The selected table alone drives mappings and readiness. Overlapping candidates are treated as scan noise unless a reviewer intentionally inspects another region.';
      item.classList.remove('warn');
      item.classList.add('ok');
      item.dataset.ps083Info = '1';
      const icon = item.querySelector(':scope > span');
      if (icon) icon.textContent = '✓';
    }
    const stat = document.getElementById('stat-quality');
    if (stat) {
      const trueIssues = [...qualityBox.querySelectorAll('.quality-item')].filter(x => !x.dataset.ps083Info && !x.classList.contains('ok')).length;
      stat.textContent = String(trueIssues);
    }
  }

  // v0.8.1 save code builds URLSearchParams immediately before fetch. Patch the
  // request body at call time so persisted provenance reflects the frontend that
  // actually produced the review.
  const originalFetch = window.fetch.bind(window);
  window.fetch = function(input, init = {}) {
    try {
      if (init?.body instanceof URLSearchParams) {
        for (const key of ['notes']) {
          const value = init.body.get(key);
          if (value && value.includes('v0.8.1')) init.body.set(key, value.replaceAll('v0.8.1', `v${VERSION}`));
        }
      }
    } catch (_) {}
    return originalFetch(input, init);
  };

  categorySelect?.addEventListener('change', () => {
    // Re-scope, but never auto-check an item the reviewer manually unchecked.
    scopeEvidence();
  });

  const observer = new MutationObserver(() => {
    scopeEvidence();
    denoiseRegionCandidates();
  });
  if (evidenceBox) observer.observe(evidenceBox, { childList: true, subtree: true });
  if (qualityBox) observer.observe(qualityBox, { childList: true, subtree: true });

  scopeEvidence();
  denoiseRegionCandidates();
})();
