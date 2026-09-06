// PrimeStride Client OS stable intake-workspace frontend domain.
// Owns progressive disclosure, lineage/job controls, and source lifecycle UI wiring.
export async function bootWorkspace(cache = '1400') {
  const modules = [
    'v103-ui.js',
    'v110-ui.js',
    'v111-ui.js',
  ];
  for (const file of modules) {
    await import(`/static/${file}?v=${cache}`);
  }
}
