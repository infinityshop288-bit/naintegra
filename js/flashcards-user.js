/** Decks de flashcards criados pelo usuário (localStorage) + importação multi-formato. */
(function () {
  const LS_KEY = "lex_user_flashcard_decks";

  function loadJson(key, fallback) {
    if (window.LexStore?.loadJson) return window.LexStore.loadJson(key, fallback);
    try {
      return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
    } catch {
      return fallback;
    }
  }

  function saveJson(key, val) {
    if (window.LexStore?.saveJson) window.LexStore.saveJson(key, val);
    else localStorage.setItem(key, JSON.stringify(val));
  }

  function slugify(name) {
    const base = String(name || "deck")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 48) || "deck";
    return `u-${base}-${Date.now().toString(36).slice(-5)}`;
  }

  function normalizeCard(raw) {
    const front = String(raw?.front ?? raw?.pergunta ?? raw?.question ?? raw?.q ?? "").trim();
    const back = String(raw?.back ?? raw?.resposta ?? raw?.answer ?? raw?.a ?? "").trim();
    const highlight = raw?.highlight != null ? String(raw.highlight).trim() : null;
    if (!front || !back) return null;
    return { front, back, highlight: highlight || null };
  }

  function parseCsvLine(line, sep) {
    const out = [];
    let cur = "";
    let quoted = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (quoted) {
        if (ch === '"') {
          if (line[i + 1] === '"') {
            cur += '"';
            i++;
          } else quoted = false;
        } else cur += ch;
      } else if (ch === '"') quoted = true;
      else if (ch === sep) {
        out.push(cur.trim());
        cur = "";
      } else cur += ch;
    }
    out.push(cur.trim());
    return out;
  }

  function detectSeparator(headerLine) {
    const counts = [
      [";", (headerLine.match(/;/g) || []).length],
      ["\t", (headerLine.match(/\t/g) || []).length],
      [",", (headerLine.match(/,/g) || []).length],
    ].sort((a, b) => b[1] - a[1]);
    return counts[0][1] > 0 ? counts[0][0] : ",";
  }

  function headerMap(headers) {
    const map = {};
    headers.forEach((h, i) => {
      const k = String(h || "")
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .toLowerCase()
        .trim();
      map[k] = i;
    });
    const pick = (...names) => {
      for (const n of names) {
        if (map[n] != null) return map[n];
      }
      return -1;
    };
    return {
      front: pick("front", "pergunta", "question", "q", "frente", "termo"),
      back: pick("back", "resposta", "answer", "a", "verso", "definicao", "definição"),
      highlight: pick("highlight", "destaque", "grifo"),
      category: pick("categoria", "category", "discipline", "disciplina", "deck", "baralho"),
      deck: pick("deck", "baralho", "deck_name", "nome_deck"),
    };
  }

  function parseCsv(text) {
    const lines = String(text || "")
      .replace(/^\uFEFF/, "")
      .split(/\r?\n/)
      .filter((l) => l.trim() && !/^#/.test(l.trim()));
    if (!lines.length) return { cards: [], decks: [] };

    const sep = detectSeparator(lines[0]);
    const first = parseCsvLine(lines[0], sep);
    const cols = headerMap(first);
    const hasHeader = cols.front >= 0 && cols.back >= 0;
    const rows = hasHeader ? lines.slice(1) : lines;
    const startFront = hasHeader ? cols.front : 0;
    const startBack = hasHeader ? cols.back : 1;

    const cards = [];
    const deckBuckets = new Map();

    for (const line of rows) {
      const cells = parseCsvLine(line, sep);
      if (cells.length < 2) continue;
      const card = normalizeCard({
        front: cells[startFront],
        back: cells[startBack],
        highlight: cols.highlight >= 0 ? cells[cols.highlight] : null,
      });
      if (!card) continue;
      cards.push(card);

      const deckName =
        (cols.deck >= 0 ? cells[cols.deck] : "") ||
        (cols.category >= 0 ? cells[cols.category] : "");
      if (deckName) {
        if (!deckBuckets.has(deckName)) deckBuckets.set(deckName, []);
        deckBuckets.get(deckName).push(card);
      }
    }

    const decks = [...deckBuckets.entries()].map(([name, deckCards]) => ({
      name,
      category: "Meus decks",
      cards: deckCards,
    }));

    return { cards, decks };
  }

  function parseJson(text) {
    const data = JSON.parse(String(text || "").trim());
    if (Array.isArray(data)) {
      const cards = data.map(normalizeCard).filter(Boolean);
      return { cards, decks: cards.length ? [{ name: "Importado", category: "Meus decks", cards }] : [] };
    }
    if (data?.decks && Array.isArray(data.decks)) {
      const decks = data.decks
        .map((d) => ({
          name: String(d.name || d.title || "Deck").trim(),
          category: String(d.category || "Meus decks").trim(),
          cards: (d.cards || []).map(normalizeCard).filter(Boolean),
        }))
        .filter((d) => d.cards.length);
      const cards = decks.flatMap((d) => d.cards);
      return { cards, decks };
    }
    if (Array.isArray(data?.cards)) {
      const cards = data.cards.map(normalizeCard).filter(Boolean);
      return {
        cards,
        decks: [{ name: String(data.name || data.title || "Importado").trim(), category: "Meus decks", cards }],
      };
    }
    const one = normalizeCard(data);
    return one ? { cards: [one], decks: [{ name: "Importado", category: "Meus decks", cards: [one] }] } : { cards: [], decks: [] };
  }

  function parseJsonl(text) {
    const cards = String(text || "")
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter(Boolean)
      .map((line) => {
        try {
          return normalizeCard(JSON.parse(line));
        } catch {
          return null;
        }
      })
      .filter(Boolean);
    return { cards, decks: cards.length ? [{ name: "Importado", category: "Meus decks", cards }] : [] };
  }

  function parseDelimited(text, sep) {
    const cards = [];
    for (const line of String(text || "").split(/\r?\n/)) {
      const t = line.trim();
      if (!t || t.startsWith("#")) continue;
      const idx = t.indexOf(sep);
      if (idx < 0) continue;
      const card = normalizeCard({ front: t.slice(0, idx), back: t.slice(idx + sep.length) });
      if (card) cards.push(card);
    }
    return { cards, decks: cards.length ? [{ name: "Importado", category: "Meus decks", cards }] : [] };
  }

  function parseBlocks(text) {
    const cards = [];
    const blocks = String(text || "")
      .split(/\n\s*\n+/)
      .map((b) => b.trim())
      .filter(Boolean);
    for (const block of blocks) {
      const lines = block.split(/\r?\n/).filter((l) => l.trim());
      if (lines.length < 2) continue;
      const card = normalizeCard({ front: lines[0].replace(/^#+\s*/, ""), back: lines.slice(1).join("\n") });
      if (card) cards.push(card);
    }
    return { cards, decks: cards.length ? [{ name: "Importado", category: "Meus decks", cards }] : [] };
  }

  function detectFormat(text, filename) {
    const ext = String(filename || "").split(".").pop().toLowerCase();
    if (ext === "json") return "json";
    if (ext === "jsonl" || ext === "ndjson") return "jsonl";
    if (ext === "tsv") return "tsv";
    if (ext === "csv") return "csv";
    const t = String(text || "").trim();
    if (!t) return "csv";
    if (t.startsWith("{") || t.startsWith("[")) return "json";
    const lines = t.split(/\r?\n/).filter((l) => l.trim() && !l.trim().startsWith("#"));
    if (lines.length && lines.every((l) => { try { JSON.parse(l); return true; } catch { return false; } })) {
      return "jsonl";
    }
    if (/#separator:tab/i.test(t) || (lines[0] && lines[0].includes("\t"))) return "tsv";
    if (lines.some((l) => l.includes("::"))) return "doublecolon";
    if (lines.some((l) => /\|/.test(l) && !/^[^|]+\|[^|]+\|/.test(l))) return "pipe";
    if (lines.length >= 2 && lines.every((l) => l.includes(";"))) return "csv";
    if (/\n\s*\n/.test(t) && !t.includes(",") && !t.includes(";")) return "blocks";
    return "csv";
  }

  function parseImport(text, opts = {}) {
    const fmt = opts.format || detectFormat(text, opts.filename);
    let result = { cards: [], decks: [] };
    try {
      if (fmt === "json") result = parseJson(text);
      else if (fmt === "jsonl") result = parseJsonl(text);
      else if (fmt === "tsv") result = parseDelimited(text.replace(/#separator:tab[^\n]*\n?/gi, ""), "\t");
      else if (fmt === "doublecolon") result = parseDelimited(text, "::");
      else if (fmt === "pipe") result = parseDelimited(text, "|");
      else if (fmt === "blocks") result = parseBlocks(text);
      else result = parseCsv(text);
    } catch (err) {
      return { cards: [], decks: [], error: err.message || String(err), format: fmt };
    }
    return { ...result, format: fmt, count: result.cards.length };
  }

  function loadCustomDecks() {
    const raw = loadJson(LS_KEY, []);
    if (!Array.isArray(raw)) return [];
    return raw
      .map((d) => ({
        slug: d.slug,
        name: d.name,
        category: d.category || "Meus decks",
        custom: true,
        createdAt: d.createdAt,
        updatedAt: d.updatedAt,
        cards: Array.isArray(d.cards)
          ? d.cards.map(normalizeCard).filter(Boolean)
          : [],
      }))
      .filter((d) => d.slug && d.name);
  }

  function saveCustomDecks(decks) {
    saveJson(LS_KEY, decks);
    notifyDecksChange();
  }

  function notifyDecksChange() {
    if (typeof onDecksChange === "function") onDecksChange();
  }

  function setOnDecksChange(fn) {
    onDecksChange = typeof fn === "function" ? fn : null;
  }

  const cfg = () => window.LEX_CONFIG || {};
  let cloudSession = null;
  let syncTimer = null;
  let syncInFlight = null;
  let onDecksChange = null;
  const pendingUpserts = new Set();
  const pendingDeletes = new Set();

  function isCloudLoggedIn() {
    return Boolean(cloudSession?.user?.id && cloudSession.access_token);
  }

  function cloudHeaders(token, extra) {
    return {
      apikey: cfg().supabaseAnonKey,
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/json",
      "Accept-Profile": cfg().lexSchema,
      "Content-Profile": cfg().lexSchema,
      Prefer: "resolution=merge-duplicates,return=minimal",
      ...(extra || {}),
    };
  }

  async function cloudRequest(path, token, init) {
    const res = await fetch(`${cfg().supabaseUrl}/rest/v1/${path}`, {
      ...init,
      headers: { ...cloudHeaders(token, init?.headers), ...(init?.headers || {}) },
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(`Lex flashcards sync ${path}: ${res.status} ${detail}`);
    }
    if (res.status === 204) return null;
    const text = await res.text();
    return text ? JSON.parse(text) : null;
  }

  function rowToDeck(row) {
    const cards = Array.isArray(row?.cards) ? row.cards : [];
    return {
      slug: row.slug,
      name: row.name,
      category: row.category || "Meus decks",
      createdAt: row.created_at,
      updatedAt: row.updated_at,
      cards: cards.map(normalizeCard).filter(Boolean),
    };
  }

  function deckToRow(deck, userId) {
    const now = new Date().toISOString();
    return {
      user_id: userId,
      slug: deck.slug,
      name: deck.name,
      category: deck.category || "Meus decks",
      cards: (deck.cards || []).map(normalizeCard).filter(Boolean),
      created_at: deck.createdAt || now,
      updated_at: deck.updatedAt || now,
    };
  }

  function mergeDeckLists(localDecks, remoteDecks) {
    const bySlug = new Map();
    for (const deck of remoteDecks || []) {
      if (deck?.slug) bySlug.set(deck.slug, deck);
    }
    for (const deck of localDecks || []) {
      if (!deck?.slug) continue;
      const remote = bySlug.get(deck.slug);
      if (!remote) {
        bySlug.set(deck.slug, deck);
        continue;
      }
      const lt = new Date(deck.updatedAt || 0).getTime();
      const rt = new Date(remote.updatedAt || 0).getTime();
      bySlug.set(deck.slug, lt >= rt ? deck : remote);
    }
    return [...bySlug.values()];
  }

  function scheduleCloudSync() {
    if (!isCloudLoggedIn()) return;
    clearTimeout(syncTimer);
    syncTimer = setTimeout(flushCloudSync, 700);
  }

  async function pullRemoteDecks(token, userId) {
    const rows = await cloudRequest(
      `user_flashcard_decks?user_id=eq.${userId}&select=slug,name,category,cards,created_at,updated_at&order=updated_at.desc`,
      token,
      { method: "GET" }
    );
    return (rows || []).map(rowToDeck).filter((d) => d.slug && d.name);
  }

  async function pushDecks(token, userId, decks) {
    if (!decks.length) return;
    await cloudRequest("user_flashcard_decks", token, {
      method: "POST",
      body: JSON.stringify(decks.map((d) => deckToRow(d, userId))),
    });
  }

  async function deleteRemoteDeck(token, userId, slug) {
    await cloudRequest(
      `user_flashcard_decks?user_id=eq.${userId}&slug=eq.${encodeURIComponent(slug)}`,
      token,
      { method: "DELETE", headers: { Prefer: "return=minimal" } }
    );
  }

  async function flushCloudSync() {
    if (!isCloudLoggedIn()) return;
    if (syncInFlight) return syncInFlight;

    const token = cloudSession.access_token;
    const userId = cloudSession.user.id;
    const upsertSlugs = [...pendingUpserts];
    const deleteSlugs = [...pendingDeletes];
    pendingUpserts.clear();
    pendingDeletes.clear();

    syncInFlight = (async () => {
      for (const slug of deleteSlugs) {
        if (upsertSlugs.includes(slug)) continue;
        await deleteRemoteDeck(token, userId, slug);
      }
      const decks = loadCustomDecks();
      const toPush = decks.filter((d) => upsertSlugs.includes(d.slug));
      if (toPush.length) await pushDecks(token, userId, toPush);
    })();

    try {
      await syncInFlight;
    } catch (err) {
      upsertSlugs.forEach((s) => pendingUpserts.add(s));
      deleteSlugs.forEach((s) => pendingDeletes.add(s));
      console.warn("LexFlashcardsUser sync:", err);
    } finally {
      syncInFlight = null;
    }
  }

  async function syncWithCloud() {
    if (!isCloudLoggedIn()) return false;
    const token = cloudSession.access_token;
    const userId = cloudSession.user.id;
    const local = loadCustomDecks();
    const remote = await pullRemoteDecks(token, userId);
    const merged = mergeDeckLists(local, remote);
    saveJson(LS_KEY, merged);
    await pushDecks(token, userId, merged);
    pendingUpserts.clear();
    pendingDeletes.clear();
    notifyDecksChange();
    return true;
  }

  async function setCloudSession(sess) {
    cloudSession = sess?.user?.id && sess.access_token ? sess : null;
    if (!cloudSession) return;
    try {
      await syncWithCloud();
    } catch (err) {
      console.warn("LexFlashcardsUser cloud sync:", err);
    }
  }

  function queueCloudUpsert(slug) {
    if (!slug) return;
    pendingDeletes.delete(slug);
    pendingUpserts.add(slug);
    scheduleCloudSync();
  }

  function queueCloudDelete(slug) {
    if (!slug) return;
    pendingUpserts.delete(slug);
    pendingDeletes.add(slug);
    scheduleCloudSync();
  }

  function findCustomDeck(slug) {
    return loadCustomDecks().find((d) => d.slug === slug) || null;
  }

  function upsertCustomDeck(deck) {
    const decks = loadCustomDecks();
    const now = new Date().toISOString();
    const idx = decks.findIndex((d) => d.slug === deck.slug);
    const row = {
      slug: deck.slug,
      name: String(deck.name || "Meu deck").trim(),
      category: String(deck.category || "Meus decks").trim(),
      createdAt: deck.createdAt || now,
      updatedAt: now,
      cards: (deck.cards || []).map(normalizeCard).filter(Boolean),
    };
    if (idx >= 0) decks[idx] = { ...decks[idx], ...row };
    else decks.push(row);
    saveCustomDecks(decks);
    queueCloudUpsert(row.slug);
    return row;
  }

  function deleteCustomDeck(slug) {
    saveCustomDecks(loadCustomDecks().filter((d) => d.slug !== slug));
    queueCloudDelete(slug);
  }

  function createDeck({ name, category, cards }) {
    const deck = {
      slug: slugify(name),
      name: String(name || "Meu deck").trim(),
      category: String(category || "Meus decks").trim(),
      createdAt: new Date().toISOString(),
      cards: (cards || []).map(normalizeCard).filter(Boolean),
    };
    return upsertCustomDeck(deck);
  }

  function appendCards(slug, cards) {
    const deck = findCustomDeck(slug);
    if (!deck) return null;
    deck.cards = [...(deck.cards || []), ...cards.map(normalizeCard).filter(Boolean)];
    return upsertCustomDeck(deck);
  }

  function removeCard(slug, index) {
    const deck = findCustomDeck(slug);
    if (!deck) return null;
    deck.cards = (deck.cards || []).filter((_, i) => i !== index);
    return upsertCustomDeck(deck);
  }

  function updateCard(slug, index, patch) {
    const deck = findCustomDeck(slug);
    if (!deck || index < 0 || index >= (deck.cards || []).length) return null;
    const card = normalizeCard({ ...deck.cards[index], ...patch });
    if (!card) return null;
    deck.cards = [...deck.cards];
    deck.cards[index] = card;
    return upsertCustomDeck(deck);
  }

  function mergeDecks(catalogDecks) {
    const custom = loadCustomDecks().filter((d) => d.cards.length);
    const slugs = new Set(custom.map((d) => d.slug));
    const server = (catalogDecks || []).filter((d) => !slugs.has(d.slug));
    return [...custom, ...server];
  }

  function exportDeckJson(deck) {
    return JSON.stringify(
      {
        name: deck.name,
        category: deck.category,
        cards: deck.cards,
      },
      null,
      2
    );
  }

  const FORMAT_HINTS = [
    "CSV — categoria, pergunta, resposta (ou front, back)",
    "JSON — { \"decks\": [{ \"name\", \"cards\": [{ \"front\", \"back\" }] }] }",
    "JSONL — um card por linha: {\"front\":\"…\",\"back\":\"…\"}",
    "TSV / Anki — pergunta[TAB]resposta",
    "Texto — pergunta::resposta ou pergunta|resposta",
    "Blocos — pergunta na 1ª linha, resposta nas seguintes (linha em branco entre cards)",
  ];

  window.LexFlashcardsUser = {
    LS_KEY,
    loadCustomDecks,
    saveCustomDecks,
    findCustomDeck,
    upsertCustomDeck,
    deleteCustomDeck,
    createDeck,
    appendCards,
    removeCard,
    updateCard,
    mergeDecks,
    parseImport,
    detectFormat,
    exportDeckJson,
    normalizeCard,
    FORMAT_HINTS,
    setCloudSession,
    setOnDecksChange,
    syncWithCloud,
    isCloudLoggedIn,
  };
})();
