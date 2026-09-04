// v0.8 loader: keep the existing template path stable while replacing the old parser.
import('/static/v08.js?v=080').catch((err) => {
  const box = document.getElementById('ingestion-error');
  if (box) {
    box.textContent = `Ingestion engine failed to load: ${err?.message || err}`;
    box.classList.add('active');
  }
});
