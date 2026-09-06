// PrimeStride Client OS stable Source-First / Source Vault frontend domain.
export async function bootSource(cache = '1400') {
  const modules = [
    'v100.js',
    'v101.js',
  ];
  for (const file of modules) {
    await import(`/static/${file}?v=${cache}`);
  }
}
