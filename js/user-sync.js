/** Persistência local + sync automático com Supabase (lex.user_content_marks, progresso, flashcards). */
(function () {
  const cfg = window.LEX_CONFIG;
  const LS = {
    highlights: "lex_highlights",
    notes: "lex_notes",
    progress: "lex_reading_progress",
    studied: "lex_studied_items",
    flashReviews: "lex_flashcard_reviews",
    fontSize: "lex_font_size",
    recentReads: "lex_recent_reads",
  };

  let session = null;
  let syncTimer = null;
  const pendingMarks = new Map();
  const pendingProgress = new Map();

  function loadJson(key, fallback) {
    try {
      return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
    } catch {
      return fallback;
    }
  }

  function saveJson(key, val) {
    localStorage.setItem(key, JSON.stringify(val));
  }

  function markKey(docType, docId, blockKey) {
    return `${docType}::${docId}::${blockKey}`;
  }

  function lexHeaders(token) {
    return {
      apikey: cfg.supabaseAnonKey,
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/json",
      "Accept-Profile": cfg.lexSchema,
      "Content-Profile": cfg.lexSchema,
      Prefer: "resolution=merge-duplicates,return=minimal",
    };
  }

  async function lexRequest(path, token, init) {
    const res = await fetch(`${cfg.supabaseUrl}/rest/v1/${path}`, {
      ...init,
      headers: { ...lexHeaders(token), ...(init?.headers || {}) },
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(`Lex sync ${path}: ${res.status} ${detail}`);
    }
    if (res.status === 204) return null;
    const text = await res.text();
    return text ? JSON.parse(text) : null;
  }

  function isLoggedIn() {
    return Boolean(session?.user?.id && session.access_token);
  }

  function scheduleSync() {
    if (!isLoggedIn()) return;
    clearTimeout(syncTimer);
    syncTimer = setTimeout(flushSync, 700);
  }

  async function flushSync() {
    if (!isLoggedIn()) return;
    const token = session.access_token;
    const userId = session.user.id;

    const marks = [...pendingMarks.values()];
    pendingMarks.clear();
    if (marks.length) {
      await lexRequest("user_content_marks", token, {
        method: "POST",
        body: JSON.stringify(
          marks.map((m) => ({
            user_id: userId,
            doc_type: m.docType,
            doc_id: m.docId,
            block_key: m.blockKey,
            highlight_html: m.highlightHtml ?? null,
            note_text: m.noteText ?? null,
            updated_at: new Date().toISOString(),
          }))
        ),
      });
    }

    const progressRows = [...pendingProgress.values()];
    pendingProgress.clear();
    for (const row of progressRows) {
      await lexRequest("user_reading_progress", token, {
        method: "POST",
        headers: { Prefer: "resolution=merge-duplicates,return=minimal" },
        body: JSON.stringify({
          user_id: userId,
          document_external_id: row.docId,
          percent_read: row.pct,
          last_article: JSON.stringify(row.read || []),
          updated_at: new Date().toISOString(),
        }),
      });
    }
  }

  function queueMark(docType, docId, blockKey, patch) {
    const key = markKey(docType, docId, blockKey);
    const prev = pendingMarks.get(key) || { docType, docId, blockKey };
    pendingMarks.set(key, { ...prev, ...patch });
    scheduleSync();
  }

  function docTypeForRoute(kind) {
    if (kind === "flash") return "flashcard";
    if (kind === "juris") return "jurisprudencia";
    return "legislacao";
  }

  function getHighlights(docId, docType) {
    const all = loadJson(LS.highlights, {});
    const type = docType || "legislacao";
    if (all[type]?.[docId]) return all[type][docId];
    if (all[docId] && typeof all[docId] === "object" && !Array.isArray(all[docId])) return all[docId];
    return {};
  }

  function setHighlight(docId, artId, html, docType) {
    const type = docType || "legislacao";
    const all = loadJson(LS.highlights, {});
    if (!all[type]) all[type] = {};
    if (!all[type][docId]) all[type][docId] = {};
    all[type][docId][artId] = html;
    saveJson(LS.highlights, all);
    queueMark(type, docId, String(artId), { highlightHtml: html });
  }

  function getNotes(docId, docType) {
    const all = loadJson(LS.notes, {});
    const type = docType || "legislacao";
    if (all[type]?.[docId]) return all[type][docId];
    if (all[docId] && typeof all[docId] === "object") return all[docId];
    return {};
  }

  function setNote(docId, blockKey, text, docType) {
    const type = docType || "legislacao";
    const all = loadJson(LS.notes, {});
    if (!all[type]) all[type] = {};
    if (!all[type][docId]) all[type][docId] = {};
    all[type][docId][blockKey] = text;
    saveJson(LS.notes, all);
    const hl = getHighlights(docId, type)[blockKey];
    queueMark(type, docId, String(blockKey), { noteText: text, highlightHtml: hl || null });
  }

  function readingProgress(docId) {
    const all = loadJson(LS.progress, {});
    return all[docId] || { read: [], pct: 0 };
  }

  function setReadingProgress(docId, readIds, total) {
    const all = loadJson(LS.progress, {});
    const pct = total ? Math.round((readIds.length / total) * 100) : 0;
    all[docId] = { read: readIds, pct };
    saveJson(LS.progress, all);
    pendingProgress.set(docId, { docId, read: readIds, pct });
    scheduleSync();
  }

  function isStudied(id) {
    return (loadJson(LS.studied, []) || []).includes(id);
  }

  function toggleStudied(id) {
    let list = loadJson(LS.studied, []) || [];
    if (list.includes(id)) list = list.filter((x) => x !== id);
    else list.push(id);
    saveJson(LS.studied, list);
    if (isLoggedIn()) {
      const token = session.access_token;
      const userId = session.user.id;
      if (list.includes(id)) {
        lexRequest("user_studied_items", token, {
          method: "POST",
          body: JSON.stringify({ user_id: userId, item_type: "juris", item_id: id }),
        }).catch(console.warn);
      } else {
        lexRequest(
          `user_studied_items?user_id=eq.${userId}&item_id=eq.${encodeURIComponent(id)}`,
          token,
          { method: "DELETE" }
        ).catch(console.warn);
      }
    }
  }

  function flashReviews() {
    return loadJson(LS.flashReviews, {});
  }

  function scheduleFlash(key, due, rating) {
    const reviews = loadJson(LS.flashReviews, {});
    reviews[key] = { due, rating };
    saveJson(LS.flashReviews, reviews);
    scheduleSync();
  }

  function trackRecentRead(doc, route) {
    if (!doc) return;
    const type = doc.doc_type;
    if (type !== "legislacao" && type !== "jurisprudencia" && type !== "sumula") return;
    const routeId = doc.lex_route_id || doc.external_id;
    const backRoute = route || (type === "legislacao" ? "lei-seca" : "jurisprudencia");
    const list = loadJson(LS.recentReads, []);
    const entry = {
      id: routeId,
      external_id: doc.external_id,
      route: backRoute,
      doc_type: type,
      at: Date.now(),
    };
    const next = [
      entry,
      ...list.filter((x) => x.id !== routeId && x.external_id !== doc.external_id),
    ].slice(0, 8);
    saveJson(LS.recentReads, next);
  }

  function getRecentReads() {
    return loadJson(LS.recentReads, []);
  }

  function mergeMarksRemote(rows) {
    const highlights = loadJson(LS.highlights, {});
    const notes = loadJson(LS.notes, {});
    for (const row of rows || []) {
      const { doc_type: type, doc_id: docId, block_key: blockKey } = row;
      if (!highlights[type]) highlights[type] = {};
      if (!highlights[type][docId]) highlights[type][docId] = {};
      if (!notes[type]) notes[type] = {};
      if (!notes[type][docId]) notes[type][docId] = {};
      if (row.highlight_html) highlights[type][docId][blockKey] = row.highlight_html;
      if (row.note_text) notes[type][docId][blockKey] = row.note_text;
    }
    saveJson(LS.highlights, highlights);
    saveJson(LS.notes, notes);
  }

  function mergeProgressRemote(rows) {
    const all = loadJson(LS.progress, {});
    for (const row of rows || []) {
      let read = [];
      try {
        read = JSON.parse(row.last_article || "[]");
      } catch {
        read = [];
      }
      all[row.document_external_id] = {
        read: Array.isArray(read) ? read : [],
        pct: Number(row.percent_read) || 0,
      };
    }
    saveJson(LS.progress, all);
  }

  function mergeStudiedRemote(rows) {
    const ids = (rows || []).map((r) => r.item_id);
    if (ids.length) {
      const local = loadJson(LS.studied, []) || [];
      saveJson(LS.studied, [...new Set([...local, ...ids])]);
    }
  }

  async function pullRemote(sess) {
    if (!sess?.access_token) return;
    const token = sess.access_token;
    const userId = sess.user.id;
    const [marks, progress, studied] = await Promise.all([
      lexRequest(
        `user_content_marks?user_id=eq.${userId}&select=doc_type,doc_id,block_key,highlight_html,note_text,updated_at`,
        token,
        { method: "GET" }
      ),
      lexRequest(
        `user_reading_progress?user_id=eq.${userId}&select=document_external_id,percent_read,last_article`,
        token,
        { method: "GET" }
      ),
      lexRequest(`user_studied_items?user_id=eq.${userId}&select=item_id`, token, { method: "GET" }),
    ]);
    mergeMarksRemote(marks);
    mergeProgressRemote(progress);
    mergeStudiedRemote(studied);
  }

  async function pushLocalMarks(sess) {
    if (!sess?.access_token) return;
    const highlights = loadJson(LS.highlights, {});
    const notes = loadJson(LS.notes, {});
    const types = new Set([...Object.keys(highlights), ...Object.keys(notes)]);
    for (const type of types) {
      const docs = { ...(highlights[type] || {}), ...(notes[type] || {}) };
      for (const docId of Object.keys(docs)) {
        const hlDoc = highlights[type]?.[docId] || {};
        const noteDoc = notes[type]?.[docId] || {};
        const blocks = new Set([...Object.keys(hlDoc), ...Object.keys(noteDoc)]);
        for (const blockKey of blocks) {
          queueMark(type, docId, blockKey, {
            highlightHtml: hlDoc[blockKey] || null,
            noteText: noteDoc[blockKey] || null,
          });
        }
      }
    }
    const progress = loadJson(LS.progress, {});
    for (const [docId, val] of Object.entries(progress)) {
      pendingProgress.set(docId, { docId, read: val.read || [], pct: val.pct || 0 });
    }
    await flushSync();
  }

  async function setSession(sess) {
    session = sess;
    if (!sess?.user) return;
    migrateLegacyStorage();
    try {
      await pullRemote(sess);
      await pushLocalMarks(sess);
    } catch (err) {
      console.warn("LexStore sync:", err);
    }
  }

  function migrateLegacyStorage() {
    const highlights = loadJson(LS.highlights, {});
    if (highlights.legislacao || highlights.jurisprudencia || highlights.flashcard) return;
    const sample = highlights[Object.keys(highlights)[0]];
    if (sample && typeof sample === "object") {
      saveJson(LS.highlights, { legislacao: highlights });
    }
    const notes = loadJson(LS.notes, {});
    if (!notes.legislacao && !notes.jurisprudencia && notes[Object.keys(notes)[0]]) {
      saveJson(LS.notes, { legislacao: notes });
    }
  }

  window.LexStore = {
    LS,
    loadJson,
    saveJson,
    setSession,
    isLoggedIn,
    getHighlights,
    setHighlight,
    getNotes,
    setNote,
    readingProgress,
    setReadingProgress,
    isStudied,
    toggleStudied,
    flashReviews,
    scheduleFlash,
    docTypeForRoute,
    trackRecentRead,
    getRecentReads,
    flushSync,
  };
})();
