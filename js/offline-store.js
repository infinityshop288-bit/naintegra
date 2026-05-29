/** Cache persistente (IndexedDB) para uso offline do NaIntegra Lex. */
(function () {
  const DB_NAME = "naintegra-lex-offline";
  const DB_VERSION = 2;
  const CATALOG_META_VERSION = 3;
  const STORES = {
    catalog: "catalog",
    bodies: "bodies",
    questions: "questions",
    meta: "meta",
  };

  let dbPromise = null;

  function openDb() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      if (!("indexedDB" in window)) {
        reject(new Error("IndexedDB indisponível"));
        return;
      }
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onerror = () => reject(req.error || new Error("IndexedDB open failed"));
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORES.catalog)) db.createObjectStore(STORES.catalog);
        if (!db.objectStoreNames.contains(STORES.bodies)) db.createObjectStore(STORES.bodies);
        if (!db.objectStoreNames.contains(STORES.questions)) db.createObjectStore(STORES.questions);
        if (!db.objectStoreNames.contains(STORES.meta)) db.createObjectStore(STORES.meta);
      };
      req.onsuccess = () => resolve(req.result);
    });
    return dbPromise;
  }

  function tx(store, mode) {
    return openDb().then((db) => db.transaction(store, mode).objectStore(store));
  }

  function bodyKeys(doc) {
    const keys = [
      doc?.lex_route_id,
      doc?.external_id,
      doc?.doc_key,
      doc?.url,
      doc?.meta?.doc_key,
    ].filter(Boolean);
    return [...new Set(keys.map(String))];
  }

  async function get(store, key) {
    try {
      const s = await tx(store, "readonly");
      return await new Promise((resolve, reject) => {
        const req = s.get(key);
        req.onsuccess = () => resolve(req.result ?? null);
        req.onerror = () => reject(req.error);
      });
    } catch (err) {
      console.warn("Lex offline get", store, key, err);
      return null;
    }
  }

  async function put(store, key, value) {
    try {
      const s = await tx(store, "readwrite");
      await new Promise((resolve, reject) => {
        const req = s.put(value, key);
        req.onsuccess = () => resolve();
        req.onerror = () => reject(req.error);
      });
    } catch (err) {
      console.warn("Lex offline put", store, key, err);
    }
  }

  async function loadCatalog() {
    const row = await get(STORES.catalog, "documents");
    if (!row?.documents?.length) return null;
    if ((row.version || 0) < CATALOG_META_VERSION) return null;
    return row.documents;
  }

  async function saveCatalog(documents, source) {
    if (!Array.isArray(documents) || !documents.length) return;
    await put(STORES.catalog, "documents", {
      version: CATALOG_META_VERSION,
      documents,
      source: source || "unknown",
      savedAt: new Date().toISOString(),
      count: documents.length,
    });
  }

  async function saveDocumentBody(doc, body) {
    if (!doc || !body || typeof body !== "string" || !body.trim()) return;
    const payload = {
      body,
      savedAt: new Date().toISOString(),
      title: doc.title || null,
    };
    await Promise.all(bodyKeys(doc).map((key) => put(STORES.bodies, key, payload)));
  }

  async function loadDocumentBody(doc) {
    for (const key of bodyKeys(doc)) {
      const row = await get(STORES.bodies, key);
      if (row?.body) return row.body;
    }
    return null;
  }

  async function saveQuestions(questions) {
    if (!Array.isArray(questions) || !questions.length) return;
    await put(STORES.questions, "all", {
      questions,
      savedAt: new Date().toISOString(),
      count: questions.length,
    });
  }

  async function loadQuestions() {
    const row = await get(STORES.questions, "all");
    return row?.questions || null;
  }

  async function getMeta(key) {
    return get(STORES.meta, key);
  }

  async function setMeta(key, value) {
    return put(STORES.meta, key, value);
  }

  window.LexOffline = {
    saveCatalog,
    loadCatalog,
    saveDocumentBody,
    loadDocumentBody,
    saveQuestions,
    loadQuestions,
    getMeta,
    setMeta,
    bodyKeys,
  };
})();
