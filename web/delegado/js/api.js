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

    const res = await fetch(cfg.apiBaseUrl.replace(/\/$/, "") + path, {
      ...options,
      headers,
    });

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

  window.DelegadoApi = {
    me: () => apiFetch("/auth/me"),
    overview: () => apiFetch("/overview"),
    debugToken: () => apiFetch("/meta/debug-token"),
    generateIdeas: (tema, formato) =>
      apiFetch("/content/ideas", {
        method: "POST",
        body: JSON.stringify({ tema, formato }),
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
