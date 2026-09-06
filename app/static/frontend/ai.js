// PrimeStride Client OS stable multimodal-AI frontend domain.
// Preserves the validated v0.9.x browser UX while hiding release-numbered wiring
// behind a stable module boundary.
export async function bootAi(cache = '1400') {
  const modules = [
    'v09.js',
    'v091.js',
    'v092.js',
    'v093.js',
    'v094.js',
  ];
  for (const file of modules) {
    await import(`/static/${file}?v=${cache}`);
  }
}
