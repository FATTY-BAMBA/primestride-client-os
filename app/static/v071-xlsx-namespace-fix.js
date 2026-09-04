(() => {
  // v0.7.1 compatibility shim for XLSX XML that uses namespace-prefixed tags
  // such as <x:sheet>, <x:row>, <x:c>, <x:v>. The original v0.7 parser used
  // getElementsByTagName('sheet'), which returns no matches for prefixed XML.
  // This page-local shim preserves normal HTML/XML lookup behavior and falls
  // back to namespace-aware matching only when the direct lookup is empty.
  const patch = (proto) => {
    if (!proto || !proto.getElementsByTagName || proto.__psNamespaceAwareTagLookup) return;
    const original = proto.getElementsByTagName;
    Object.defineProperty(proto, '__psNamespaceAwareTagLookup', { value: true });
    proto.getElementsByTagName = function(name) {
      const direct = original.call(this, name);
      if (direct.length || String(name).includes(':') || !this.getElementsByTagNameNS) return direct;
      try {
        const local = this.getElementsByTagNameNS('*', name);
        return local.length ? local : direct;
      } catch (_) {
        return direct;
      }
    };
  };

  patch(Document.prototype);
  patch(Element.prototype);
})();
