// v0.8.1 loader: messy-data hardening + safer contextual mappings.
(() => {
  const metric = document.querySelector('.intake-summary-grid .intake-metric:nth-child(3) strong');
  if (metric) metric.textContent = 'v0.8.1';
  const eyebrow = document.querySelector('.ingestion-lab .eyebrow');
  if (eyebrow) eyebrow.textContent = 'INGESTION INTELLIGENCE · v0.8.1';
})();

import('/static/v081.js?v=081').catch((err) => {
  const box = document.getElementById('ingestion-error');
  if (box) {
    box.textContent = `Ingestion engine failed to load: ${err?.message || err}`;
    box.classList.add('active');
  }
});
