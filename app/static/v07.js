// v0.8.4 loader: messy-data parser + dataset-scoped evidence + contextual mapping + semantic quality.
(() => {
  const metric = document.querySelector('.intake-summary-grid .intake-metric:nth-child(3) strong');
  if (metric) metric.textContent = 'v0.8.4';
  const eyebrow = document.querySelector('.ingestion-lab .eyebrow');
  if (eyebrow) eyebrow.textContent = 'INGESTION INTELLIGENCE · v0.8.4';
})();

import('/static/v081.js?v=084')
  .then(() => import('/static/v083.js?v=084'))
  .then(() => import('/static/v084.js?v=084'))
  .catch((err) => {
    const box = document.getElementById('ingestion-error');
    if (box) {
      box.textContent = `Ingestion engine failed to load: ${err?.message || err}`;
      box.classList.add('active');
    }
  });
