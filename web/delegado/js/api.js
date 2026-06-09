(function () {
  const cfg = window.DELEGADO_CONFIG;

  async function apiFetch(path, options = {}) {
    const token = await window.DelegadoAuth.getAccessToken();
    if (!token) throw new Error("Sessão expirada");

    const headers = {
      "Content-Type": "application/json",
      Authorization: "Bearer " + token,
      ...(options.headers || {}),
    };

    let res;
    try {
      res = await fetch(cfg.apiBaseUrl.replace(/\/$/, "") + path, {
        ...options,
        headers,
      });
    } catch (err) {
      throw new Error(apiNetworkError(err));
    }

    const text = await res.text();
    let body = null;
    try {
      body = text ? JSON.parse(text) : null;
    } catch {
      body = { raw: text };
    }

    if (!res.ok) {
      const detail = body?.detail || body?.error || text || res.statusText;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return body;
  }

  async function apiHealth() {
    const base = cfg.apiBaseUrl.replace(/\/$/, "");
    try {
      const res = await fetch(base + "/health", { method: "GET" });
      return res.ok;
    } catch {
      return false;
    }
  }

  function apiNetworkError(err) {
    const msg = err && err.message ? String(err.message) : String(err);
    if (/failed to fetch|networkerror|load failed/i.test(msg)) {
      return (
        "API indisponível em " +
        cfg.apiBaseUrl +
        ". Inicie: PYTHONPATH=src DELEGADO_AI_PROVIDER=ollama naintegra-delegado-api"
      );
    }
    return msg;
  }

  window.DelegadoApi = {
    health: apiHealth,
    apiNetworkError,
    me: () => apiFetch("/auth/me"),
    overview: () => apiFetch("/overview"),
    debugToken: () => apiFetch("/meta/debug-token"),
    contentProviders: () => apiFetch("/content/providers"),
    contentCalendar: (month) =>
      apiFetch("/content/calendar" + (month ? "?month=" + encodeURIComponent(month) : "")),
    marketingLibrary: () => apiFetch("/content/marketing-library"),
    imageProviders: () => apiFetch("/content/image-providers"),
    generateIdeas: (tema, formato, provider) =>
      apiFetch("/content/ideas", {
        method: "POST",
        body: JSON.stringify({ tema, formato, provider: provider || null }),
      }),
    generatePackage: (opts) =>
      apiFetch("/content/package/generate", {
        method: "POST",
        body: JSON.stringify(opts),
      }),
    comparePackages: (tema, formato) =>
      apiFetch("/content/package/compare", {
        method: "POST",
        body: JSON.stringify({ tema, formato }),
      }),
    assetUrl: (path) =>
      cfg.apiBaseUrl.replace(/\/$/, "") + (path.startsWith("/") ? path : "/" + path),
    async fetchAsset(path) {
      const token = await window.DelegadoAuth.getAccessToken();
      if (!token) throw new Error("Sessão expirada");
      const res = await fetch(this.assetUrl(path), {
        headers: { Authorization: "Bearer " + token },
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || "Preview indisponível (" + res.status + ")");
      }
      return res.blob();
    },
    runPipeline: (opts) =>
      apiFetch("/content/pipeline/run", {
        method: "POST",
        body: JSON.stringify(opts || { days: 1, dry_run: false }),
      }),
    patchQueueStatus: (id, status) =>
      apiFetch("/content/queue/" + id + "/status", {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    getQueue: () => apiFetch("/content/queue"),
    saveQueueItem: (item) =>
      apiFetch("/content/queue", { method: "POST", body: JSON.stringify(item) }),
    deleteQueueItem: (id) => apiFetch("/content/queue/" + id, { method: "DELETE" }),
    publishImage: (image_url, caption) =>
      apiFetch("/publish/image", {
        method: "POST",
        body: JSON.stringify({ image_url, caption }),
      }),
    publishReels: (video_url, caption) =>
      apiFetch("/publish/reels", {
        method: "POST",
        body: JSON.stringify({ video_url, caption }),
      }),
    adsCampaigns: () => apiFetch("/ads/campaigns"),
    monitoring: () => apiFetch("/monitoring/insights"),
    comments: (mediaId) => apiFetch("/monitoring/comments/" + mediaId),
    competitors: () => apiFetch("/competitors"),
    automations: () => apiFetch("/automations"),
    pairing: () => apiFetch("/meta/pairing"),
    setAutomationStatus: (id, status) =>
      apiFetch("/automations/" + id, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
  };
})();
