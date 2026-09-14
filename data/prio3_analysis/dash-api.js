/** Fetch relativo para deploy em /xxx/ e fallback para snapshots .json (Hostinger). */
const DASH_EDGE = {
  url: "https://voybsggeedpwcfdadnzt.supabase.co",
  anonKey:
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZveWJzZ2dlZWRwd2NmZGFkbnp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNzU2MTQsImV4cCI6MjA4ODc1MTYxNH0.dy5AgSd1VWdP4WLGXy5V89pA4jgHijngHJjScApOo70",
  fn: "prio3-live",
};

const DASH_LIVE_EDGE = new Set(["live", "multiquotes"]);

async function dashEdgeLive(endpoint, extra) {
  const r = await fetch(`${DASH_EDGE.url}/functions/v1/${DASH_EDGE.fn}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${DASH_EDGE.anonKey}`,
      apikey: DASH_EDGE.anonKey,
    },
    body: JSON.stringify({ endpoint, ...(extra || {}) }),
    cache: "no-store",
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

async function dashFetch(path, opts) {
  path = String(path || "").replace(/^\//, "");
  const urls = [path, "/" + path, path + ".json", "/" + path + ".json"];
  const tried = new Set();
  for (const url of urls) {
    if (tried.has(url)) continue;
    tried.add(url);
    try {
      const r = await fetch(url, { cache: "no-store", ...(opts || {}) });
      if (r.ok) {
        const ct = (r.headers.get("content-type") || "").toLowerCase();
        if (ct.includes("text/html") && path.includes("api/")) continue;
        return await r.json();
      }
    } catch (_) {}
  }
  throw new Error("API indisponível: " + path);
}

/** Carrega recurso: nuvem (live) → api/X → JSON estático. */
async function dashLoad(name, opts) {
  const base = String(name || "")
    .replace(/^\//, "")
    .replace(/^api\//, "")
    .replace(/\.json$/, "");
  if (DASH_LIVE_EDGE.has(base)) {
    try {
      return await dashEdgeLive(base);
    } catch (_) {}
  }
  const live = "api/" + base;
  try {
    return await dashFetch(live, opts);
  } catch (_) {}
  return dashFetch(base, opts);
}

/* ============================================================
   Atualização automática — ativa em qualquer página do painel
   ------------------------------------------------------------
   1. Ao abrir, lê api/meta.json e mostra a idade do snapshot.
   2. Se o snapshot estiver velho, pede um refresh ao servidor
      (edge prio3-live → workflow de atualização).
   3. Enquanto a página fica aberta, verifica a cada 45s se um
      snapshot novo foi publicado e recarrega quando o usuário
      estiver inativo (nunca no meio de um clique/scroll).
   ============================================================ */
const DASH_AUTO = {
  checkMs: 45000,
  idleMs: 20000,
  staleMinsMarket: 30,
  staleMinsOff: 720,
  snapshot: null,
  lastInput: Date.now(),
  pending: false,
  pill: null,
};

function dashPill() {
  if (DASH_AUTO.pill) return DASH_AUTO.pill;
  const el = document.createElement("div");
  el.id = "dashAutoPill";
  el.style.cssText =
    "position:fixed;right:12px;bottom:12px;z-index:9999;font:12px/1.4 -apple-system,Segoe UI,Roboto,sans-serif;" +
    "background:rgba(13,17,23,.92);color:#9aa7b4;border:1px solid rgba(255,255,255,.12);border-radius:999px;" +
    "padding:6px 12px;backdrop-filter:blur(6px);cursor:pointer;max-width:70vw";
  el.title = "Clique para atualizar agora";
  el.onclick = () => location.reload();
  document.body.appendChild(el);
  DASH_AUTO.pill = el;
  return el;
}

function dashPillText(txt, color) {
  const el = dashPill();
  el.innerHTML = txt;
  el.style.color = color || "#9aa7b4";
}

function dashSnapshotAgeMin(generatedAt) {
  const t = Date.parse(generatedAt);
  if (Number.isNaN(t)) return null;
  return (Date.now() - t) / 60000;
}

function dashInMarketHours(d) {
  const day = d.getDay();
  if (day === 0 || day === 6) return false;
  const h = d.getHours();
  return h >= 9 && h < 19;
}

function dashFmtAge(mins) {
  if (mins == null) return "—";
  if (mins < 1) return "agora";
  if (mins < 60) return `${Math.round(mins)} min`;
  const h = mins / 60;
  if (h < 24) return `${h.toFixed(h < 10 ? 1 : 0)} h`;
  return `${Math.round(h / 24)} d`;
}

async function dashRequestServerRefresh(ageMin) {
  const key = "dashRefreshAsked";
  const last = Number(sessionStorage.getItem(key) || 0);
  if (Date.now() - last < 10 * 60000) return;
  sessionStorage.setItem(key, String(Date.now()));
  try {
    const r = await dashEdgeLive("refresh", { age_min: Math.round(ageMin) });
    if (r && r.dispatched) {
      dashPillText("⟳ atualizando dados no servidor…", "#d29922");
    }
  } catch (_) {}
}

async function dashCheckSnapshot(first) {
  let meta = null;
  try {
    meta = await dashFetch("api/meta");
  } catch (_) {
    return;
  }
  const at = meta.generated_at || meta.generatedAt;
  if (!at) return;
  const age = dashSnapshotAgeMin(at);
  const when = new Date(at).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

  if (first) {
    DASH_AUTO.snapshot = at;
    dashPillText(`● dados de ${when} · atualização automática`, "#5bd66b");
    const limit = dashInMarketHours(new Date())
      ? DASH_AUTO.staleMinsMarket
      : DASH_AUTO.staleMinsOff;
    if (age != null && age > limit) {
      dashPillText(`● dados de ${when} (${dashFmtAge(age)}) · pedindo atualização…`, "#d29922");
      dashRequestServerRefresh(age);
    }
    return;
  }

  if (at !== DASH_AUTO.snapshot) {
    DASH_AUTO.pending = true;
    dashPillText("⟳ novos dados publicados · atualizando…", "#d29922");
    dashMaybeReload();
  }
}

function dashMaybeReload() {
  if (!DASH_AUTO.pending) return;
  const idle = Date.now() - DASH_AUTO.lastInput;
  if (document.hidden || idle >= DASH_AUTO.idleMs) {
    location.reload();
    return;
  }
  dashPillText("⟳ novos dados · clique para atualizar", "#d29922");
  setTimeout(dashMaybeReload, 5000);
}

function dashAutoUpdateStart() {
  ["pointerdown", "keydown", "wheel", "touchstart"].forEach((ev) =>
    window.addEventListener(ev, () => {
      DASH_AUTO.lastInput = Date.now();
    }, { passive: true }),
  );
  dashCheckSnapshot(true);
  setInterval(() => dashCheckSnapshot(false), DASH_AUTO.checkMs);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) dashCheckSnapshot(false);
  });
  window.addEventListener("online", () => dashCheckSnapshot(false));
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", dashAutoUpdateStart);
} else {
  dashAutoUpdateStart();
}
