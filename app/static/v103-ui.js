(() => {
  const VERSION = '1.0.3';
  const lab = document.getElementById('ingestion-lab');
  if (!lab) return;

  function moveSourceFirstToTop(){
    const vault = document.getElementById('source-vault-panel');
    if (!vault) return;
    const shell = lab.parentElement;
    if (!shell) return;
    const summary = shell.querySelector('.intake-summary-grid');
    if (summary && summary.nextElementSibling !== vault) {
      summary.insertAdjacentElement('afterend', vault);
    }
    if (!document.getElementById('ps-analysis-divider')) {
      const divider = document.createElement('div');
      divider.id = 'ps-analysis-divider';
      divider.className = 'ps-analysis-divider';
      divider.innerHTML = '<span>Analysis workbenches · automatically routed after retention</span>';
      vault.insertAdjacentElement('afterend', divider);
    }
  }

  function collapseDirectUpload(panel, drop, label){
    if (!panel || !drop || drop.closest('.ps-direct-tools')) return;
    const details = document.createElement('details');
    details.className = 'ps-direct-tools';
    const summary = document.createElement('summary');
    summary.textContent = label;
    drop.parentNode.insertBefore(details, drop);
    details.appendChild(summary);
    details.appendChild(drop);
  }

  function cleanFileInventory(){
    document.querySelectorAll('.file-row').forEach(row => {
      const main = row.querySelector('.file-main');
      if (!main || main.dataset.ps103 === '1') return;
      main.dataset.ps103 = '1';
      const meta = main.querySelector(':scope > small');
      const note = main.querySelector(':scope > p');
      const noteText = note?.textContent?.trim() || '';
      const metaText = meta?.textContent?.trim() || '';
      const chips = document.createElement('div');
      chips.className = 'ps-file-chips';

      const addChip = (text, cls='') => {
        const span = document.createElement('span');
        span.className = `ps-file-chip ${cls}`.trim();
        span.textContent = text;
        chips.appendChild(span);
      };

      if (/Source Vault/i.test(metaText) || /PS_SOURCE_VAULT_V1|Cloudflare R2/i.test(noteText)) addChip('Original retained', 'good');
      if (/AI multimodal|multimodal analysis|model=/i.test(noteText)) addChip('AI analyzed', 'ai');
      if (/messy-data inspection|Local browser inspection|sheet=/i.test(noteText)) addChip('Deterministic inspection');
      const status = row.querySelector('.file-status')?.textContent?.trim();
      if (status) addChip(status === 'Reviewed' ? 'Human reviewed' : status, status === 'Reviewed' ? 'good' : '');

      if (chips.children.length) {
        (meta || main.firstChild)?.after?.(chips);
      }

      if (note && noteText) {
        const details = document.createElement('details');
        details.className = 'ps-file-technical';
        const summary = document.createElement('summary');
        summary.textContent = 'Technical inspection metadata';
        const pre = document.createElement('pre');
        pre.textContent = noteText;
        details.append(summary, pre);
        note.replaceWith(details);
      }
    });
  }

  function relabelPrimaryPanels(){
    const vault = document.getElementById('source-vault-panel');
    if (vault) {
      const badge = vault.querySelector('.sv-badge');
      if (badge && !badge.dataset.ps103) {
        badge.dataset.ps103 = '1';
        badge.title = 'Primary intake door for real client files';
      }
    }
  }

  function apply(){
    moveSourceFirstToTop();
    collapseDirectUpload(lab, document.getElementById('ingestion-drop'), 'Direct structured upload / debug tools');
    collapseDirectUpload(document.getElementById('ai-intake-lab'), document.getElementById('ai09-drop'), 'Direct AI upload / debug tools');
    cleanFileInventory();
    relabelPrimaryPanels();
  }

  apply();
  // Source Vault/AI panels are injected by earlier modules in the import chain;
  // run a few bounded passes instead of observing the whole DOM indefinitely.
  [80, 220, 500, 900].forEach(ms => setTimeout(apply, ms));
})();
