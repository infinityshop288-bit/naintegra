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

/** Carrega recurso ao vivo (api/X) com fallback para JSON estático. */
async function dashLoad(name, opts) {
  const live = "api/" + name.replace(/^\//, "").replace(/\.json$/, "");
  try {
    return await dashFetch(live, opts);
  } catch (_) {}
  return dashFetch(name.replace(/^\//, ""), opts);
}
