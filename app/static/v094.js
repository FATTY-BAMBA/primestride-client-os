(() => {
  const VERSION = '0.9.4';
  const ai = document.getElementById('ai-intake-lab');
  if (!ai) return;

  const eyebrow = ai.querySelector('.ai09-head .eyebrow');
  if (eyebrow) eyebrow.textContent = `AI-ASSISTED MULTIMODAL INTAKE · v${VERSION}`;

  const POLICY = {
    quotes: {
      4: '*',
      6: new Set(['quote_history', 'customer_product', 'time_fields', 'cost', 'margin'])
    },
    work_orders: {
      5: '*',
      6: new Set(['customer_product', 'time_fields', 'production_events'])
    },
    reports: { 6: '*' },
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

  let lastGoverned = null;
  const originalFetch = window.fetch.bind(window);

  function inPrimaryScope(category, item) {
    const moduleRule = (POLICY[category] || POLICY.other)[Number(item.module_no)];
    if (moduleRule === '*') return true;
    return moduleRule instanceof Set ? moduleRule.has(item.criterion) : false;
  }

  function hasActualTimestamps(result) {
    const fieldActual = (result.fields || []).some(f =>
      ['Operation.actual_start', 'Operation.actual_end'].includes(f.canonical_target) && String(f.value || '').trim()
    );
    const opActual = (result.operations || []).some(o =>
      String(o.actual_start || '').trim() || String(o.actual_end || '').trim()
    );
    return fieldActual || opActual;
  }

  function isTopLevelResponsiblePerson(field) {
    const label = String(field.source_label || '').trim().toLowerCase();
    const section = String(field.source_section || '').trim().toLowerCase();
    const responsibilityLabel = /^(負責人|负责人|responsible person|owner|person in charge)$/i.test(label);
    const scheduleContext = /schedule|排程|製程|operation/.test(section);
    return responsibilityLabel && !scheduleContext;
  }

  function govern(data) {
    if (!data?.ok || !data?.result) return data;
    const result = data.result;
    const category = result.category || 'other';

    // Work-order-level responsibility is different from an operation assignee.
    // v0.9.2 deliberately left ambiguous top-level 負責人 fields unmapped; make
    // that distinction explicit without pretending it belongs to a schedule row.
    for (const field of result.fields || []) {
      if (category === 'work_orders' && isTopLevelResponsiblePerson(field)) {
        if (!field.canonical_target || field.canonical_target === 'Operation.assignee') {
          field.canonical_target = 'WorkOrder.responsible_person';
          field.confidence = Math.max(85, Number(field.confidence || 0));
          field.evidence = `${field.evidence || field.source_label}: ${field.value || ''}`.trim();
        }
      }
    }

    const actualVisible = hasActualTimestamps(result);
    for (const item of result.readiness || []) {
      let primary = inPrimaryScope(category, item);
      let reason = '';

      // A single photographed work order is useful evidence, but it is not a
      // historical dataset. Keep the history criterion as supporting evidence.
      if (category === 'work_orders' && Number(item.module_no) === 6 && item.criterion === 'work_order_history') {
        item.status = 'partial';
        primary = false;
        reason = 'A single work-order document is supporting evidence, not work-order history.';
      }

      // Planned schedule timestamps must never satisfy the actual-timestamps gate.
      if (Number(item.module_no) === 5 && item.criterion === 'actual_timestamps' && !actualVisible) {
        item.status = 'partial';
        primary = false;
        reason = 'Only planned timestamps are visible; no actual production event timestamp is evidenced.';
      }

      item.approval_scope = primary ? 'primary' : 'supporting';
      item.default_approve = Boolean(primary && item.status === 'available' && Number(item.confidence || 0) >= 65);
      item.approval_note = reason || (primary
        ? (item.status === 'available' ? 'Primary evidence for this dataset type.' : 'Partial evidence requires explicit review.')
        : 'Detected here, but supporting only for this dataset type.');
    }

    data.version = VERSION;
    lastGoverned = data;
    queueMicrotask(applyApprovalUI);
    setTimeout(applyApprovalUI, 60);
    setTimeout(applyApprovalUI, 220);
    return data;
  }

  window.fetch = async function(input, init = {}) {
    const url = typeof input === 'string' ? input : (input?.url || '');
    const res = await originalFetch(input, init);

    if (url.includes('/ai-intake/analyze')) {
      try {
        const data = await res.clone().json();
        if (data?.ok && data?.result) {
          const governed = govern(data);
          return new Response(JSON.stringify(governed), {
            status: res.status,
            headers: {'Content-Type': 'application/json'}
          });
        }
      } catch (_) {}
    }

    // Keep persisted provenance aligned with the UI that actually governed the review.
    if (init?.body instanceof URLSearchParams) {
      const notes = init.body.get('notes');
      if (notes && /v0\.9(?:\.1|\.2|\.3)?/i.test(notes)) {
        init.body.set('notes', notes.replace(/v0\.9(?:\.1|\.2|\.3)?/gi, `v${VERSION}`));
      }
    }
    return res;
  };

  function applyApprovalUI() {
    const result = lastGoverned?.result;
    const box = document.getElementById('ai09-evidence');
    if (!result || !box) return;

    const labels = [...box.querySelectorAll('.ai09-item')];
    (result.readiness || []).forEach((item, i) => {
      const label = labels[i];
      if (!label) return;
      const checkbox = label.querySelector('input[type="checkbox"]');
      const small = label.querySelector('small');
      if (!checkbox) return;

      checkbox.checked = Boolean(item.default_approve);
      label.dataset.ps094Scope = item.approval_scope || 'supporting';
      label.style.opacity = item.approval_scope === 'primary' ? '' : '0.5';
      label.title = item.approval_note || '';

      let badge = label.querySelector('.ps094-policy-badge');
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'ps094-policy-badge';
        badge.style.cssText = 'display:inline-block;margin-top:5px;padding:2px 5px;border-radius:999px;font-size:7px;font-weight:800;letter-spacing:.03em;background:#f2f5f4;color:#657476';
        label.querySelector('div')?.appendChild(badge);
      }
      if (item.default_approve) {
        badge.textContent = 'PRIMARY · AUTO-CHECKED';
        badge.style.background = '#edf7f3';
        badge.style.color = '#2e6658';
      } else if (item.status === 'partial') {
        badge.textContent = item.approval_scope === 'primary' ? 'PARTIAL · REVIEW FIRST' : 'SUPPORTING · UNCHECKED';
        badge.style.background = '#fff8e8';
        badge.style.color = '#80662f';
      } else {
        badge.textContent = 'SUPPORTING ONLY · UNCHECKED';
        badge.style.background = '#f3f5f4';
        badge.style.color = '#718080';
      }
      if (small && item.approval_note && !small.dataset.ps094) {
        small.dataset.ps094 = '1';
        small.textContent = `${small.textContent} · ${item.approval_note}`;
      }
    });
  }

  const observer = new MutationObserver(() => applyApprovalUI());
  const evidenceBox = document.getElementById('ai09-evidence');
  if (evidenceBox) observer.observe(evidenceBox, {childList:true, subtree:true});

  const policyNote = document.createElement('div');
  policyNote.className = 'ai09-note';
  policyNote.style.marginTop = '8px';
  policyNote.innerHTML = '<b>v0.9.4 approval policy:</b> only primary-scope <b>Available</b> evidence is checked automatically. Partial or cross-module supporting evidence stays unchecked until a reviewer explicitly chooses it.';
  ai.querySelector('.ai09-head')?.insertAdjacentElement('afterend', policyNote);
})();
