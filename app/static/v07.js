// Deterministic ingestion stays at v0.8.4; v1.1 adds first-class lineage + job history.
(() => {
  const metric = document.querySelector('.intake-summary-grid .intake-metric:nth-child(3) strong');
  if (metric) metric.textContent = 'v0.8.4';
  const eyebrow = document.querySelector('.ingestion-lab .eyebrow');
  if (eyebrow) eyebrow.textContent = 'INGESTION INTELLIGENCE · v0.8.4';
})();

import('/static/v081.js?v=1100')
  .then(() => import('/static/v083.js?v=1100'))
  .then(() => import('/static/v084.js?v=1100'))
  .then(() => import('/static/v09.js?v=1100'))
  .then(() => import('/static/v091.js?v=1100'))
  .then(() => import('/static/v092.js?v=1100'))
  .then(() => import('/static/v093.js?v=1100'))
  .then(() => import('/static/v094.js?v=1100'))
  .then(() => import('/static/v100.js?v=1100'))
  .then(() => import('/static/v101.js?v=1100'))
  .then(() => import('/static/v103-ui.js?v=1100'))
  .then(() => import('/static/v110-ui.js?v=1100'))
  .catch((err) => {
    const box = document.getElementById('ingestion-error');
    if (box) {
      box.textContent = `Ingestion engine failed to load: ${err?.message || err}`;
      box.classList.add('active');
    }
  });
