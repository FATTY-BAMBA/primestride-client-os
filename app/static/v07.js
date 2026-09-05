// PrimeStride Client OS stable intake frontend bootstrap.
//
// The browser now has one explicit ordered module registry instead of a long
// promise chain scattered through release shims. Individual legacy modules are
// still loaded for behavior compatibility; consolidation can now happen behind
// this stable entrypoint without changing the Data Intake template again.
(() => {
  const RELEASE = '1.2.0';
  const CACHE = '1200';

  const metric = document.querySelector('.intake-summary-grid .intake-metric:nth-child(3) strong');
  if (metric) metric.textContent = 'v0.8.4';
  const eyebrow = document.querySelector('.ingestion-lab .eyebrow');
  if (eyebrow) eyebrow.textContent = 'INGESTION INTELLIGENCE · v0.8.4';

  const modules = [
    'v081.js',          // local deterministic inspection base
    'v083.js',          // category / mapping improvements
    'v084.js',          // deterministic semantics
    'v09.js',           // multimodal UI base
    'v091.js',          // AI mapping refinements
    'v092.js',          // section-aware operations
    'v093.js',          // background polling
    'v094.js',          // evidence governance
    'v100.js',          // Source Vault UI
    'v101.js',          // Source-First routing
    'v103-ui.js',       // hierarchy/progressive disclosure
    'v110-ui.js',       // lineage + job controls
    'v111-ui.js',       // source lifecycle
  ];

  async function boot() {
    for (const file of modules) {
      await import(`/static/${file}?v=${CACHE}`);
    }
    document.documentElement.dataset.psIntakeRelease = RELEASE;
  }

  boot().catch((err) => {
    const box = document.getElementById('ingestion-error');
    if (box) {
      box.textContent = `Ingestion application failed to load: ${err?.message || err}`;
      box.classList.add('active');
    }
  });
})();
