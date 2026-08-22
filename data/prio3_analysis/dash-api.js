/** Fetch relativo para deploy em /xxx/ e fallback para snapshots .json (Hostinger). */
async function dashFetch(path, opts) {
  path = String(path || "").replace(/^\//, "");
  const urls = [path, "/" + path, path + ".json", "/" + path + ".json"];
  const tried = new Set();
  for (const url of urls) {
    if (tried.has(url)) continue;
    tried.add(url);
    try {
      const r = await fetch(url, { cache: "no-store", ...(opts || {}) });
      if (r.ok) return await r.json();
    } catch (_) {}
  }
  throw new Error("API indisponível: " + path);
}
