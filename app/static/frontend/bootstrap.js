// PrimeStride Client OS stable Data Intake frontend bootstrap.
// v1.4.0: templates load one stable module. Release-numbered browser modules are
// contained behind four domain boundaries while behavior remains unchanged.
import { bootDeterministic } from './deterministic.js';
import { bootAi } from './ai.js';
import { bootSource } from './source.js';
import { bootWorkspace } from './workspace.js';

const RELEASE = '1.4.0';
const CACHE = '1400';

const metric = document.querySelector('.intake-summary-grid .intake-metric:nth-child(3) strong');
if (metric) metric.textContent = 'v0.8.4';
const eyebrow = document.querySelector('.ingestion-lab .eyebrow');
if (eyebrow) eyebrow.textContent = 'INGESTION INTELLIGENCE · v0.8.4';

async function boot() {
  // Ordering is intentional because later UI layers augment DOM created by earlier ones.
  await bootDeterministic(CACHE);
  await bootAi(CACHE);
  await bootSource(CACHE);
  await bootWorkspace(CACHE);
  document.documentElement.dataset.psIntakeRelease = RELEASE;
  document.documentElement.dataset.psFrontendArchitecture = 'stable-domain-bootstrap';
}

boot().catch((err) => {
  const box = document.getElementById('ingestion-error');
  if (box) {
    box.textContent = `Ingestion application failed to load: ${err?.message || err}`;
    box.classList.add('active');
  }
  console.error('[PrimeStride intake frontend]', err);
});
