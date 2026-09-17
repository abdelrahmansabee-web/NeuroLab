/** Cache-bust reload so iPad Home Screen / Safari pick up a new HF bundle. */

export function buildHardRefreshUrl(locationLike = {}, version, now = Date.now()) {
  const path = locationLike.pathname || "/";
  const hash = locationLike.hash || "";
  const v = String(version || now);
  return `${path}?_v=${encodeURIComponent(v)}&_r=${encodeURIComponent(String(now))}${hash}`;
}

export async function clearAppRuntimeCaches() {
  try {
    if (typeof navigator !== "undefined" && navigator.serviceWorker?.getRegistrations) {
      const regs = await navigator.serviceWorker.getRegistrations();
      await Promise.all(regs.map((reg) => reg.unregister()));
    }
  } catch {
    /* ignore */
  }
  try {
    if (typeof caches !== "undefined" && caches.keys) {
      const keys = await caches.keys();
      await Promise.all(keys.map((key) => caches.delete(key)));
    }
  } catch {
    /* ignore */
  }
}

export function readDocumentNlVersion(doc = typeof document !== "undefined" ? document : null) {
  try {
    return doc?.querySelector?.('meta[name="nl-version"]')?.content || "";
  } catch {
    return "";
  }
}

export function performHardRefresh(opts = {}) {
  const loc = opts.location || (typeof window !== "undefined" ? window.location : { pathname: "/", hash: "" });
  const version = opts.version || readDocumentNlVersion() || String(Date.now());
  const url = buildHardRefreshUrl(loc, version, opts.now || Date.now());
  const navigate = opts.replace || ((next) => {
    if (typeof window !== "undefined") window.location.replace(next);
  });
  const go = () => {
    navigate(url);
    return url;
  };
  if (opts.skipCacheClear) return Promise.resolve(go());
  return Promise.race([
    clearAppRuntimeCaches(),
    new Promise((resolve) => setTimeout(resolve, 400)),
  ]).then(go, go);
}
