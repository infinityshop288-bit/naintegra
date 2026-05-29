const CACHE = "naintegra-lex-v24";
const DATA_CACHE = "naintegra-lex-data-v2";
const API_CACHE = "naintegra-lex-api-v1";

const SHELL = [
  "./",
  "./index.html",
  "./css/styles.css",
  "./manifest.json",
  "./favicon-32.png",
  "./favicon-16.png",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/apple-touch-icon.png",
  "./images/lex-logo-icon.png",
  "./js/config.js",
  "./js/offline-store.js",
  "./js/auth.js",
  "./js/auth-ui.js",
  "./js/subscription.js",
  "./js/content-protection.js",
  "./js/legis-meta.js",
  "./js/lex-format.js",
  "./js/flashcards-user.js",
  "./js/questao-comentarios.js",
  "./js/data.js",
  "./js/search.js",
  "./js/section-search.js",
  "./js/study-plans.js",
  "./js/app.js",
  "./js/user-sync.js",
  "./data/corpus.json",
  "./data/legis_catalog.json",
  "./data/legis_bodies.json",
  "./data/legis_summaries.json",
  "./data/legis_known_meta.json",
  "./data/flashcards.json",
  "./data/juris_bodies.json",
  "./data/sumulas_catalog.json",
  "./data/temas_catalog.json",
  "./data/questoes_catalog.json",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches
      .open(CACHE)
      .then((c) =>
        Promise.allSettled(SHELL.map((url) => c.add(new Request(url, { cache: "reload" }))))
      )
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => ![CACHE, DATA_CACHE, API_CACHE].includes(k)).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

function isLexAsset(url) {
  return url.pathname.includes("/lex/") || url.pathname.endsWith("/index.html");
}

function isDataRequest(url) {
  return url.pathname.includes("/data/") && url.pathname.endsWith(".json");
}

async function cacheFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  const res = await fetch(request);
  if (res.ok) cache.put(request, res.clone());
  return res;
}

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const res = await fetch(request);
    if (res.ok) cache.put(request, res.clone());
    return res;
  } catch (_) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw _;
  }
}

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);

  if (url.origin.includes("supabase.co")) {
    e.respondWith(networkFirst(e.request, API_CACHE));
    return;
  }

  if (isDataRequest(url)) {
    if (
      url.pathname.endsWith("/flashcards.json") ||
      url.pathname.endsWith("/flashcards_catalog.json") ||
      url.pathname.includes("/flashcards/decks/")
    ) {
      e.respondWith(networkFirst(e.request, DATA_CACHE));
      return;
    }
    e.respondWith(cacheFirst(e.request, DATA_CACHE));
    return;
  }

  if (!isLexAsset(url) && !url.pathname.includes("/js/") && !url.pathname.includes("/css/")) return;

  e.respondWith(
    caches.match(e.request).then((cached) => {
      const fetchPromise = fetch(e.request)
        .then((res) => {
          if (res.ok) {
            caches.open(CACHE).then((c) => c.put(e.request, res.clone()));
          }
          return res;
        })
        .catch(() => cached);
      return cached || fetchPromise;
    })
  );
});
