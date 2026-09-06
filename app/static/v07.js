// Compatibility entrypoint for older Data Intake templates.
// Production frontend architecture moved to /static/frontend/bootstrap.js in v1.4.0.
import('/static/frontend/bootstrap.js?v=1400').catch((err) => {
  const box = document.getElementById('ingestion-error');
  if (box) {
    box.textContent = `Ingestion application failed to load: ${err?.message || err}`;
    box.classList.add('active');
  }
  console.error('[PrimeStride intake bootstrap]', err);
});
