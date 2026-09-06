(() => {
  const VERSION = '0.9.1';

  // Make AI intake failures readable even when the hosting layer returns a
  // plain-text/HTML timeout page instead of JSON. v0.9's analyze() expects
  // JSON, so normalize only the AI analyze endpoint into a JSON response.
  const originalFetch = window.fetch.bind(window);
  window.fetch = async function(input, init = {}) {
    const url = typeof input === 'string' ? input : (input?.url || '');
    const res = await originalFetch(input, init);
    if (!url.includes('/ai-intake/analyze')) return res;

    const contentType = (res.headers.get('content-type') || '').toLowerCase();
    if (contentType.includes('application/json')) return res;

    const text = await res.text();
    let message = text.trim().replace(/\s+/g, ' ').slice(0, 900);
    if (!message) message = `AI intake request failed with HTTP ${res.status}.`;

    if (res.status === 504 || /timeout|timed out|invocation/i.test(message)) {
      message = 'AI document analysis exceeded the hosting time limit. The request was not saved. Please retry; v0.9.1 allows a longer function duration.';
    } else if (/payload too large/i.test(message)) {
      message = 'The AI intake request was too large for the function. Use a smaller image/PDF; direct object-storage upload is planned for the production intake path.';
    }

    return new Response(JSON.stringify({
      error: message,
      code: 'non_json_host_error',
      http_status: res.status,
    }), {
      status: res.status || 502,
      headers: {'Content-Type': 'application/json'},
    });
  };

  // Keep the multimodal panel version explicit without changing the proven
  // deterministic structured-data version above it.
  const badge = document.querySelector('#ai-intake-lab .eyebrow');
  if (badge) badge.textContent = `AI-ASSISTED MULTIMODAL INTAKE · v${VERSION}`;
})();
