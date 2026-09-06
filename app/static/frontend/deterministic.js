// PrimeStride Client OS stable deterministic-intake frontend domain.
// Keeps the proven v0.8.4 browser inspector behavior behind one stable boundary.
export async function bootDeterministic(cache = '1400') {
  const modules = [
    'v081.js',
    'v083.js',
    'v084.js',
  ];
  for (const file of modules) {
    await import(`/static/${file}?v=${cache}`);
  }
}
