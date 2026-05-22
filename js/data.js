/**
 * Camada de dados NaIntegra Lex.
 *
 * Legislação e jurisprudência/informativos: public.norma_chunks (upsert via normas.py).
 * Flashcards: schema lex (flashcard_decks / flashcards), importados de public.flashcards (NaIntegra Cursos).
 * Questões: public.questoes_banco (NaIntegra Cursos — objetivas e subjetivas).
 * Fallback offline: web/lex/data/corpus.json (export do repositório local).
 */
(function () {
  const cfg = window.LEX_CONFIG;

  function headers(schema) {
    const h = {
      apikey: cfg.supabaseAnonKey,
      Authorization: `Bearer ${cfg.supabaseAnonKey}`,
      "Content-Type": "application/json",
    };
    if (schema && schema !== "public") {
      h["Accept-Profile"] = schema;
      h["Content-Profile"] = schema;
    }
    return h;
  }

  async function publicFetch(path, init) {
    const res = await fetch(`${cfg.supabaseUrl}/rest/v1/${path}`, {
      ...init,
      headers: { ...headers("public"), ...(init?.headers || {}) },
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(`Supabase public ${path}: ${res.status} ${detail}`);
    }
    return res.json();
  }

  async function lexFetch(table, query = "") {
    const res = await fetch(`${cfg.supabaseUrl}/rest/v1/${table}?${query}`, {
      headers: headers(cfg.lexSchema),
    });
    if (!res.ok) throw new Error(`Supabase ${cfg.lexSchema}.${table}: ${res.status}`);
    return res.json();
  }

  async function rpc(name, body, schema) {
    const h = headers(schema || "public");
    const res = await fetch(`${cfg.supabaseUrl}/rest/v1/rpc/${name}`, {
      method: "POST",
      headers: h,
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(`RPC ${name}: ${res.status} ${detail}`);
    }
    return res.json();
  }

  function catalogTitle(row, legisMeta, docType) {
    const meta = row.metadata || {};
    if (meta.titulo) return meta.titulo;
    if (legisMeta?.titulo) return legisMeta.titulo;
    const stub = {
      url: row.url || row.doc_key || "",
      doc_key: row.doc_key,
      doc_type: docType,
      source_system: row.source,
      title: meta.titulo || null,
      organized: { tribunal: meta.tribunal || tribunalFromRow(row) },
    };
    if (window.LexFormat) return window.LexFormat.friendlyTitle(stub);
    return row.url || row.doc_key || "Documento";
  }

  function mapCatalogRow(row) {
    const meta = row.metadata || {};
    const url = row.url || row.doc_key || "";
    const legisMeta = window.LexLegisMeta?.metaFromUrl(url);
    const tribunal = meta.tribunal || tribunalFromRow(row);
    const docType = meta.doc_type || docTypeFromSource(row.source, url);
    const doc = {
      external_id: `${row.source}::${row.doc_key}`,
      doc_type: docType,
      source_system: row.source,
      doc_key: row.doc_key,
      title: catalogTitle(row, legisMeta, docType),
      resumo: meta.resumo || legisMeta?.resumo || null,
      body: null,
      meta: meta,
      organized: {
        tribunal,
        secao_lei_seca: meta.secao_lei_seca || legisMeta?.secao_lei_seca || null,
        corpus: meta.corpus || null,
      },
      url: row.url,
      source_file: row.source_file,
      chunk_count: row.chunk_count,
    };
    return enrichLegisDoc(doc);
  }

  function tribunalFromRow(row) {
    const url = (row.url || row.doc_key || "").toLowerCase();
    if (url.includes("stf-vinculante") || url.includes("/stf") || url.includes("temas-stf")) return "STF";
    if (url.includes("/stj") || url.includes("temas-stj")) return "STJ";
    if (url.includes("/tst") || url.includes("temas-tst")) return "TST";
    if (url.includes("/tse")) return "TSE";
    return "Outros";
  }

  function docTypeFromSource(source, url) {
    if ((cfg.normaSources.legislacao || []).includes(source)) return "legislacao";
    const u = (url || "").toLowerCase();
    if (u.includes("sumula")) return "sumula";
    return "jurisprudencia";
  }

  async function loadCatalog(source) {
    const out = [];
    let offset = 0;
    const limit = 500;
    const maxPages = 20;
    let pages = 0;
    while (pages < maxPages) {
      const rows = await rpc("list_norma_document_catalog", {
        p_source: source,
        p_limit: limit,
        p_offset: offset,
      });
      if (!Array.isArray(rows) || !rows.length) break;
      out.push(...rows.map(mapCatalogRow));
      if (rows.length < limit) break;
      offset += limit;
      pages += 1;
    }
    return out;
  }

  function docRouteId(doc) {
    return doc.lex_route_id || (window.LexFormat && window.LexFormat.buildLexRouteId(doc)) || doc.url;
  }

  function findDocByRouteId(docs, rid) {
    if (!rid) return null;
    return docs.find((d) => docRouteId(d) === rid) || null;
  }

  function enrichFromCatalogEntry(doc, mapped) {
    if (!doc || !mapped) return doc;
    if (!doc.resumo && mapped.resumo) doc.resumo = mapped.resumo;
    if (!doc.body && mapped.body) doc.body = mapped.body;
    if (!doc.juris_card_preview && (mapped.juris_card_preview || mapped.resumo)) {
      doc.juris_card_preview = mapped.juris_card_preview || mapped.resumo;
    }
    if (!doc.catalog_kind && mapped.catalog_kind) doc.catalog_kind = mapped.catalog_kind;
    if (mapped.meta) doc.meta = { ...(doc.meta || {}), ...mapped.meta };
    return doc;
  }

  function mapSumulaCatalogEntry(entry) {
    const previewRaw = entry.preview || "";
    const preview = window.LexFormat ? window.LexFormat.cleanRaw(previewRaw) : previewRaw.replace(/<[^>]+>/g, " ").trim();
    const label = entry.vinculante ? `SV ${entry.numero}` : `Súmula ${entry.numero}`;
    const body = preview
      ? `${label} — ${entry.tribunal}\n\n${preview}`
      : null;
    return {
      external_id: entry.external_id || `trilhante_informativo::${entry.url}`,
      doc_type: "sumula",
      source_system: entry.source_system || "trilhante_informativo",
      doc_key: entry.doc_key || entry.url,
      title: entry.title || `${label} — ${entry.tribunal}`,
      resumo: preview.slice(0, 240),
      juris_card_preview: preview || null,
      body,
      meta: {
        tribunal: entry.tribunal,
        sumula_numero: entry.numero,
        vinculante: entry.vinculante,
      },
      organized: { tribunal: entry.tribunal },
      url: entry.url,
      lex_route_id: entry.lex_route_id,
      catalog_kind: "sumula_individual",
    };
  }

  async function mergeSumulasCatalog(docs) {
    try {
      const res = await fetch(cfg.sumulasCatalogFallback, { cache: "no-store" });
      if (!res.ok) return docs;
      const data = await res.json();
      const entries = data.sumulas || [];
      if (!entries.length) return docs;

      const seen = new Set(docs.map((d) => docRouteId(d)));
      const added = [];
      let enriched = 0;
      for (const entry of entries) {
        const rid = entry.lex_route_id;
        if (!rid) continue;
        const mapped = mapSumulaCatalogEntry(entry);
        if (seen.has(rid)) {
          if (enrichFromCatalogEntry(findDocByRouteId(docs, rid), mapped)) enriched += 1;
          continue;
        }
        seen.add(rid);
        added.push(mapped);
      }
      if (added.length) {
        console.info(`Lex: +${added.length} súmulas (catálogo Trilhante)`);
      }
      if (enriched) console.info(`Lex: ${enriched} súmulas enriquecidas com preview`);
      return [...docs, ...added];
    } catch (err) {
      console.warn("Lex: catálogo de súmulas", err);
      return docs;
    }
  }

  function mapTemaCatalogEntry(entry) {
    const previewRaw = entry.preview || "";
    const preview = window.LexFormat ? window.LexFormat.cleanRaw(previewRaw) : previewRaw.replace(/<[^>]+>/g, " ").trim();
    const body = preview ? `${entry.title}\n\n${preview}` : null;
    return {
      external_id: entry.external_id || `trilhante_informativo::${entry.url}`,
      doc_type: "jurisprudencia",
      source_system: entry.source_system || "trilhante_informativo",
      doc_key: entry.doc_key || entry.url,
      title: entry.title,
      resumo: preview.slice(0, 280),
      juris_card_preview: preview || null,
      body,
      meta: {
        tribunal: entry.tribunal,
        tema_numero: entry.numero,
        tema_categoria: entry.tema_categoria,
        is_repercussao: entry.is_repercussao,
        is_repetitivo: entry.is_repetitivo,
      },
      organized: { tribunal: entry.tribunal },
      url: entry.url,
      lex_route_id: entry.lex_route_id,
      catalog_kind: "tema",
    };
  }

  async function mergeTemasCatalog(docs) {
    try {
      const res = await fetch(cfg.temasCatalogFallback, { cache: "no-store" });
      if (!res.ok) return docs;
      const data = await res.json();
      const entries = data.temas || [];
      if (!entries.length) return docs;

      const seen = new Set(docs.map((d) => docRouteId(d)));
      const added = [];
      let enriched = 0;
      for (const entry of entries) {
        const rid = entry.lex_route_id;
        if (!rid) continue;
        const mapped = mapTemaCatalogEntry(entry);
        if (seen.has(rid)) {
          if (enrichFromCatalogEntry(findDocByRouteId(docs, rid), mapped)) enriched += 1;
          continue;
        }
        seen.add(rid);
        added.push(mapped);
      }
      if (added.length) {
        console.info(`Lex: +${added.length} temas (catálogo Trilhante)`);
      }
      if (enriched) console.info(`Lex: ${enriched} temas enriquecidos com tese`);
      return [...docs, ...added];
    } catch (err) {
      console.warn("Lex: catálogo de temas", err);
      return docs;
    }
  }

  async function mergeJurisCatalogs(docs) {
    let out = await mergeSumulasCatalog(docs);
    out = await mergeTemasCatalog(out);
    return out;
  }

  async function loadDocuments() {
    const sources = [
      ...(cfg.normaSources.legislacao || []),
      ...(cfg.normaSources.jurisprudencia || []),
    ];
    const merged = [];
    const errors = [];

    const results = await Promise.allSettled(sources.map((s) => loadCatalog(s)));
    for (let i = 0; i < results.length; i++) {
      const r = results[i];
      if (r.status === "fulfilled") {
        merged.push(...r.value);
      } else {
        errors.push(`${sources[i]}: ${r.reason?.message || r.reason}`);
        console.warn("Catálogo", sources[i], r.reason);
      }
    }

    if (merged.length) {
      window.__LEX_DATA_SOURCE = "supabase";
      let prepared = window.LexFormat ? window.LexFormat.prepareCatalog(merged) : merged;
      prepared = await mergeJurisCatalogs(prepared);
      await applyLegisSummaries(prepared);
      await attachJurisPreviews(prepared);
      console.info(`Lex: ${prepared.length} documentos (Supabase, ${merged.length} brutos)`);
      return prepared;
    }

    try {
      const viewRows = [];
      let offset = 0;
      const limit = 1000;
      for (let page = 0; page < 5; page++) {
        const batch = await publicFetch(
          `norma_document_catalog?select=source,doc_key,url,source_file,chunk_count,metadata&limit=${limit}&offset=${offset}`
        );
        if (!Array.isArray(batch) || !batch.length) break;
        viewRows.push(...batch.map(mapCatalogRow));
        if (batch.length < limit) break;
        offset += limit;
      }
      if (viewRows.length) {
        window.__LEX_DATA_SOURCE = "supabase_view";
        let prepared = window.LexFormat ? window.LexFormat.prepareCatalog(viewRows) : viewRows;
        prepared = await mergeJurisCatalogs(prepared);
        await applyLegisSummaries(prepared);
        await attachJurisPreviews(prepared);
        console.info(`Lex: ${prepared.length} documentos (view)`);
        return prepared;
      }
    } catch (err) {
      errors.push(String(err));
      console.warn("norma_document_catalog view:", err);
    }

    window.__LEX_DATA_SOURCE = "fallback";
    console.warn("Lex: usando fallback local —", errors.join("; ") || "catálogo vazio");
    const res = await fetch(cfg.corpusFallback, { cache: "no-store" });
    const data = await res.json();
    let docs = data.documents || [];
    docs = window.LexFormat ? window.LexFormat.prepareCatalog(docs) : docs;
    docs = await mergeJurisCatalogs(docs);
    await applyLegisSummaries(docs);
    return attachJurisPreviews(docs);
  }

  function enrichLegisDoc(doc) {
    if (doc.doc_type !== "legislacao") return doc;
    const url = doc.url || doc.doc_key || "";
    const known = window.LexLegisMeta?.lookupKnownMeta?.(url);
    const meta = window.LexLegisMeta?.metaFromUrl?.(url, doc.body || "") || known;
    if (!meta && !known) return doc;
    const src = meta || known;
    if (src.titulo && (!doc.title || /\.htm$/i.test(doc.title) || doc.title.length < 8)) {
      doc.title = src.titulo;
    }
    if (src.resumo && !doc.resumo) doc.resumo = src.resumo;
    if (src.secao || src.secao_lei_seca) {
      if (!doc.organized) doc.organized = {};
      doc.organized.secao_lei_seca =
        doc.organized.secao_lei_seca || src.secao_lei_seca || src.secao;
    }
    return doc;
  }

  async function enrichLegisCatalog(docs) {
    if (window.LexLegisMeta?.loadKnownMeta) {
      await window.LexLegisMeta.loadKnownMeta();
    }
    for (const doc of docs) {
      if (doc.doc_type === "legislacao") enrichLegisDoc(doc);
    }
    return docs;
  }

  async function attachJurisPreviews(docs) {
    const cache = await loadJurisBodiesCache();
    const hasCache = cache && Object.keys(cache).length;
    if (!window.LexFormat?.jurisCardPreview) return docs;
    for (const doc of docs) {
      if (doc.juris_card_preview) continue;
      const kind = doc.catalog_kind || window.LexFormat.classifyDoc(doc);
      if (!["julgado", "tema", "sumula_individual"].includes(kind) && doc.doc_type !== "sumula") continue;
      const body = hasCache ? lookupCachedBody(cache, doc) : "";
      const preview = window.LexFormat.jurisCardPreview(body ? { ...doc, body } : doc);
      if (preview) doc.juris_card_preview = preview;
    }
    return docs;
  }

  async function applyLegisSummaries(docs) {
    if (window.LexLegisMeta?.loadKnownMeta) {
      await window.LexLegisMeta.loadKnownMeta();
    }
    const cache = await loadLegisSummariesCache();
    for (const doc of docs) {
      if (doc.doc_type !== "legislacao") continue;
      const cached = lookupLegisSummary(cache, doc.url, doc.doc_key);
      if (cached?.titulo) doc.title = cached.titulo;
      if (cached?.resumo) doc.resumo = cached.resumo;
      if (cached?.secao) {
        if (!doc.organized) doc.organized = {};
        doc.organized.secao_lei_seca = doc.organized.secao_lei_seca || cached.secao;
      }
      enrichLegisDoc(doc);
    }
    return docs;
  }

  function normalizeNormaUrl(url) {
    if (!url) return "";
    let u = String(url).trim();
    u = u.replace(/^http:\/\//i, "https://");
    u = u.toLowerCase();
    u = u.replace(/#.*$/, "");
    u = u.replace(/\/+$/, "");
    return u;
  }

  function isRpcError(value) {
    return value && typeof value === "object" && "message" in value && "code" in value;
  }

  let jurisBodiesCache = null;
  let legisSummariesCache = null;

  function normalizeSummaryKey(url) {
    if (!url) return "";
    try {
      const u = new URL(url);
      return u.pathname.replace(/\/+$/, "").toLowerCase();
    } catch {
      return String(url).split("?")[0].replace(/\/+$/, "").toLowerCase();
    }
  }

  async function loadLegisSummariesCache() {
    if (legisSummariesCache) return legisSummariesCache;
    try {
      const res = await fetch(cfg.legisSummariesFallback, { cache: "no-store" });
      if (!res.ok) return {};
      const data = await res.json();
      legisSummariesCache = data.summaries || {};
      return legisSummariesCache;
    } catch (err) {
      console.warn("Lex: cache legis summaries", err);
      return {};
    }
  }

  function lookupLegisSummary(cache, url, docKey) {
    const keys = [normalizeSummaryKey(url), normalizeSummaryKey(docKey), url, docKey].filter(Boolean);
    for (const key of keys) {
      if (cache[key]) return cache[key];
    }
    return null;
  }

  async function loadJurisBodiesCache() {
    if (jurisBodiesCache) return jurisBodiesCache;
    try {
      const res = await fetch(cfg.jurisBodiesFallback, { cache: "no-store" });
      if (!res.ok) return {};
      const data = await res.json();
      jurisBodiesCache = data.bodies || {};
      return jurisBodiesCache;
    } catch (err) {
      console.warn("Lex: cache juris local", err);
      return {};
    }
  }

  function lookupCachedBody(cache, doc) {
    const keys = [doc.lex_route_id, doc.doc_key, doc.url, doc.meta?.doc_key].filter(Boolean);
    for (const key of keys) {
      if (cache[key]) return cache[key];
    }
    return "";
  }

  async function loadDocumentChunks(source, doc) {
    const urls = [doc.url, doc.doc_key, doc.meta?.doc_key].filter(Boolean);
    const candidates = [];
    for (const value of urls) {
      candidates.push(value);
      const norm = normalizeNormaUrl(value);
      candidates.push(norm);
      if (norm.includes("?")) candidates.push(norm.split("?")[0]);
    }
    const unique = [...new Set(candidates.filter(Boolean))];

    for (const candidate of unique) {
      try {
        const text = await rpc("get_norma_document_chunks", {
          p_source: source,
          p_url: candidate,
        });
        if (typeof text === "string" && text.trim()) return text;
      } catch (err) {
        console.warn("Lex: RPC chunks", candidate.slice(-72), err.message);
      }

      try {
        const rows = await publicFetch(
          `norma_chunks?select=chunk_index,text&source=eq.${encodeURIComponent(source)}&url=eq.${encodeURIComponent(candidate)}&order=chunk_index.asc`
        );
        if (Array.isArray(rows) && rows.length) {
          return rows.map((r) => r.text || "").join("\n\n");
        }
      } catch (err) {
        console.warn("Lex: REST chunks", candidate.slice(-72), err.message);
      }
    }
    return "";
  }

  async function loadDocumentBody(doc) {
    if (doc.body && typeof doc.body === "string" && doc.body.trim()) {
      if (window.LexFormat) window.LexFormat.ensureFormatted(doc);
      return doc.body;
    }

    const source = doc.source_system || (doc.external_id || "").split("::")[0];
    const docKey = doc.doc_key || (doc.external_id || "").split("::").slice(1).join("::");

    if (source === "trilhante_informativo") {
      const cache = await loadJurisBodiesCache();
      const cached = lookupCachedBody(cache, doc);
      if (cached) {
        doc.body = cached;
        if (window.LexFormat) window.LexFormat.ensureFormatted(doc);
        return doc.body;
      }
    }

    let text = "";
    try {
      text = await loadDocumentChunks(source, doc);
    } catch (err) {
      console.warn("Lex: chunks por URL", docKey, err);
    }

    if (!text && source === "trilhante_informativo") {
      const cache = await loadJurisBodiesCache();
      text = lookupCachedBody(cache, doc);
    }

    if (!text) {
      try {
        const rpcText = await rpc("get_norma_document_text", {
          p_source: source,
          p_doc_key: docKey,
        });
        if (typeof rpcText === "string" && rpcText.trim()) text = rpcText;
        else if (isRpcError(rpcText)) throw new Error(rpcText.message);
      } catch (err) {
        console.warn("Lex: RPC get_norma_document_text", docKey, err);
        if (!text) throw err;
      }
    }

    if (!text || !text.trim()) {
      const preview = (doc.resumo || doc.body || "").trim();
      if (preview) {
        doc.body = preview;
        if (window.LexFormat) window.LexFormat.ensureFormatted(doc);
        return doc.body;
      }
      throw new Error("Documento sem texto disponível");
    }

    doc.body = text;
    if (window.LexLegisMeta) {
      const meta = window.LexLegisMeta.metaFromUrl(doc.url || doc.doc_key || "", doc.body);
      if (meta?.titulo) doc.title = meta.titulo;
      if (meta?.resumo) doc.resumo = meta.resumo;
      if (meta?.secao_lei_seca) {
        if (!doc.organized) doc.organized = {};
        doc.organized.secao_lei_seca = doc.organized.secao_lei_seca || meta.secao_lei_seca;
      }
    }
    if (window.LexFormat) window.LexFormat.ensureFormatted(doc);
    return doc.body;
  }

  async function loadFlashcardDecks() {
    try {
      const decks = await lexFetch("flashcard_decks", "select=*&order=sort_order.asc");
      if (!Array.isArray(decks) || !decks.length) throw new Error("empty");
      const cards = [];
      const limit = cfg.flashcardsPageSize || 1000;
      for (let offset = 0, page = 0; page < 20; page++) {
        const batch = await lexFetch(
          "flashcards",
          `select=*&order=deck_id.asc,sort_order.asc&limit=${limit}&offset=${offset}`
        );
        if (!Array.isArray(batch) || !batch.length) break;
        cards.push(...batch);
        if (batch.length < limit) break;
        offset += limit;
      }
      const byDeck = {};
      for (const c of cards) {
        if (!byDeck[c.deck_id]) byDeck[c.deck_id] = [];
        byDeck[c.deck_id].push(c);
      }
      console.info(`Lex: ${decks.length} decks · ${cards.length} flashcards`);
      return decks.map((d) => ({
        slug: d.slug,
        name: d.name,
        category: d.category,
        cards: (byDeck[d.id] || [])
          .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
          .map((c) => ({
            front: c.front,
            back: c.back,
            highlight: c.highlight,
          })),
      }));
    } catch (_) {
      const res = await fetch(cfg.flashcardsFallback);
      const data = await res.json();
      return data.decks || [];
    }
  }

  function formatQuestaoAlternativas(alts) {
    if (!alts) return [];
    if (Array.isArray(alts)) {
      return alts.map((a, i) => {
        if (typeof a === "object" && a !== null && (a.key || a.letra)) {
          return {
            key: String(a.key || a.letra).toUpperCase(),
            text: String(a.text || a.texto || a.label || ""),
          };
        }
        if (typeof a === "string") {
          const m = a.match(/^(?:\d+\.\s*)?([A-E])\s*[):.\-—]\s*(.*)$/s);
          if (m) return { key: m[1].toUpperCase(), text: m[2].trim() };
          return {
            key: String.fromCharCode(65 + i),
            text: a.replace(/^\d+\.\s*/, "").trim(),
          };
        }
        return { key: String.fromCharCode(65 + i), text: String(a) };
      });
    }
    if (typeof alts === "object") {
      return Object.entries(alts)
        .sort(([a], [b]) => a.localeCompare(b, "pt-BR"))
        .map(([k, v]) => ({ key: k.toUpperCase(), text: String(v) }));
    }
    return [];
  }

  function mapQuestaoRow(row) {
    const isSub = String(row.tipo || "").toLowerCase() === "subjetiva";
    const carreira = row.carreira
      ? String(row.carreira).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
      : null;
    return {
      external_id: `qb::${row.id}`,
      doc_type: isSub ? "questoes_subjetivas" : "questoes_objetivas",
      source_system: "naintegracursos",
      title: [row.banca, row.ano, row.disciplina].filter(Boolean).join(" — "),
      body: row.enunciado,
      meta: {
        alternativas: formatQuestaoAlternativas(row.alternativas),
        gabarito: row.gabarito,
        comentario: row.explicacao,
        explicacao: row.explicacao,
        assunto: row.assunto,
        fonte: row.fonte,
        carreira: row.carreira,
      },
      organized: {
        banca: row.banca,
        ano: row.ano,
        materia: row.disciplina,
        cargo: carreira,
      },
    };
  }

  async function loadQuestionsCount() {
    try {
      const res = await fetch(`${cfg.supabaseUrl}/rest/v1/${cfg.questionsTable}?select=id`, {
        headers: { ...headers("public"), Prefer: "count=exact" },
      });
      if (!res.ok) return null;
      const range = res.headers.get("content-range") || "";
      const m = range.match(/\/(\d+)$/);
      return m ? parseInt(m[1], 10) : null;
    } catch (err) {
      console.warn("Lex: contagem de questões indisponível", err);
      return null;
    }
  }

  async function loadQuestionsFromFallback() {
    try {
      const res = await fetch(cfg.questoesCatalogFallback, { cache: "no-store" });
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      const rows = data.documents || data.questions || [];
      return rows.map((row) =>
        row.external_id && row.doc_type ? row : mapQuestaoRow(row)
      );
    } catch (err) {
      console.warn("Lex: fallback questoes_catalog", err);
      return [];
    }
  }

  async function loadQuestions() {
    const table = cfg.questionsTable || "questoes_banco";
    const cols =
      "id,carreira,banca,ano,disciplina,assunto,enunciado,alternativas,gabarito,explicacao,tipo";
    const limit = cfg.questionsPageSize || 1000;
    const out = [];
    let offset = 0;

    try {
      for (let page = 0; page < 20; page++) {
        const batch = await publicFetch(
          `${table}?select=${cols}&order=created_at.desc&limit=${limit}&offset=${offset}`
        );
        if (!Array.isArray(batch) || !batch.length) break;
        out.push(...batch.map(mapQuestaoRow));
        if (batch.length < limit) break;
        offset += limit;
      }
      if (out.length) {
        console.info(`Lex: ${out.length} questões (Supabase ${table})`);
        return out;
      }
    } catch (err) {
      console.warn("Lex: questoes_banco", err);
    }

    const fallback = await loadQuestionsFromFallback();
    if (fallback.length) console.info(`Lex: ${fallback.length} questões (fallback local)`);
    return fallback;
  }

  window.LexData = {
    loadDocuments,
    loadDocumentBody,
    loadFlashcardDecks,
    loadQuestions,
    loadQuestionsCount,
    mapQuestaoRow,
    parseAlternativas: formatQuestaoAlternativas,
    rpc,
    publicFetch,
  };
})();
