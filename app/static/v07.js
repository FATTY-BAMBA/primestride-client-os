// v0.8.3 loader: messy-data parser + dataset-scoped evidence + review de-noising.
(() => {
  const metric = document.querySelector('.intake-summary-grid .intake-metric:nth-child(3) strong');
  if (metric) metric.textContent = 'v0.8.3';
  const eyebrow = document.querySelector('.ingestion-lab .eyebrow');
  if (eyebrow) eyebrow.textContent = 'INGESTION INTELLIGENCE · v0.8.3';
})();

import('/static/v081.js?v=083')
  .then(() => import('/static/v083.js?v=083'))
  .catch((err) => {
    const box = document.getElementById('ingestion-error');
    if (box) {
      box.textContent = `Ingestion engine failed to load: ${err?.message || err}`;
      box.classList.add('active');
    }
  });
