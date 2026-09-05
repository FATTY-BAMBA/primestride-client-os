(() => {
  if (!location.pathname.includes('/data-intake')) return;

  // v0.7.1 compatibility shim for XLSX XML that uses namespace-prefixed tags
  // such as <x:sheet>, <x:row>, <x:c>, <x:v>. The original v0.7 parser used
  // getElementsByTagName('sheet'), which returns no matches for prefixed XML.
  // This page-local shim preserves normal lookup behavior and falls back to
  // namespace-aware matching only when the direct lookup is empty.
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

  // v0.7.2 compatibility fix: XLSX rows can contain intentionally blank columns.
  // The lightweight parser represents those as sparse arrays. Native Array
  // iteration yields `undefined` for a sparse slot, while the v0.7 readiness
  // mapper expects every iterated column to be a profile object. On this page,
  // make sparse-array iteration skip only missing slots. Dense arrays are
  // unchanged. This keeps blank spreadsheet columns from crashing inspection.
  if (!Array.prototype.__psSparseIteratorFix) {
    const nativeIterator = Array.prototype[Symbol.iterator];
    Object.defineProperty(Array.prototype, '__psSparseIteratorFix', { value: true });
    Array.prototype[Symbol.iterator] = function* () {
      let sparse = false;
      for (let i = 0; i < this.length; i++) {
        if (!(i in this)) { sparse = true; break; }
      }
      if (!sparse) {
        yield* nativeIterator.call(this);
        return;
      }
      for (let i = 0; i < this.length; i++) {
        if (i in this) yield this[i];
      }
    };
  }
})();
