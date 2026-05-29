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

  /** JSON estático versionado em index.html (?v=) — permite cache do navegador. */
  async function fetchStaticJson(url) {
    const res = await fetch(url);
    if (!res.ok) throw new Error(String(res.status));
    return res.json();
  }

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
    const url = row.url || row.doc_key || "";
    const known = window.LexLegisMeta?.lookupKnownMeta?.(url);
    if (known?.titulo) return known.titulo;
    if (legisMeta?.titulo) return legisMeta.titulo;
    if (meta.titulo) return meta.titulo;
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

  function applySumulasCatalog(docs, data) {
    const entries = data?.sumulas || [];
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
  }

  async function mergeSumulasCatalog(docs, preloaded) {
    try {
      const data = preloaded ?? (await fetchStaticJson(cfg.sumulasCatalogFallback));
      return applySumulasCatalog(docs, data);
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

  function applyTemasCatalog(docs, data) {
    const entries = data?.temas || [];
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
  }

  async function mergeTemasCatalog(docs, preloaded) {
    try {
      const data = preloaded ?? (await fetchStaticJson(cfg.temasCatalogFallback));
      return applyTemasCatalog(docs, data);
    } catch (err) {
      console.warn("Lex: catálogo de temas", err);
      return docs;
    }
  }


  async function loadCatalogFromLegisSummaries() {
    const cache = await loadLegisSummariesCache();
    const docs = [];
    for (const [path, entry] of Object.entries(cache)) {
      const url =
        entry.url ||
        (path.startsWith("http")
          ? path
          : `https://www.planalto.gov.br${path.startsWith("/") ? path : `/${path}`}`);
      docs.push({
        external_id: `planalto::${url}`,
        doc_type: "legislacao",
        source_system: "planalto",
        doc_key: url,
        title: entry.titulo || url,
        resumo: entry.resumo || null,
        body: null,
        url,
        organized: { secao_lei_seca: entry.secao || null },
      });
    }
    return docs;
  }

  function catalogDocKey(doc) {
    const raw = doc.doc_key || doc.url || doc.external_id || "";
    return String(raw).trim().toLowerCase().replace(/\/+$/, "");
  }

  async function mergeAguFromOfflineBundle(catalog) {
    try {
      const data = await fetchStaticJson(cfg.legisCatalogFallback);
      const aguDocs = (data.documents || []).filter((d) => {
        const corpus = d.meta?.corpus || d.organized?.corpus || "";
        return corpus === "legislacao_agu";
      });
      if (!aguDocs.length) return catalog;
      const have = new Set((catalog || []).map(catalogDocKey));
      const extra = aguDocs.filter((d) => !have.has(catalogDocKey(d)));
      if (!extra.length) return catalog;
      console.info(`Lex: +${extra.length} legislação AGU (bundle offline)`);
      return [...catalog, ...extra];
    } catch (err) {
      console.warn("Lex: merge AGU offline", err);
      return catalog;
    }
  }

  async function loadCatalogFromStaticFallback() {
    const cached = await window.LexOffline?.loadCatalog?.();
    if (cached?.length) {
      window.__LEX_DATA_SOURCE = "offline_cache";
      const docs = cached.map((d) => enrichLegisDoc({ ...d }));
      console.info(`Lex: ${docs.length} documentos (cache IndexedDB, metadados reidratados)`);
      return docs;
    }

    try {
      const data = await fetchStaticJson(cfg.legisCatalogFallback);
      const docs = data.documents || [];
      if (docs.length) {
        window.__LEX_DATA_SOURCE = "offline_bundle";
        console.info(`Lex: ${docs.length} documentos (legis_catalog.json)`);
        return docs;
      }
    } catch (err) {
      console.warn("Lex: legis_catalog.json", err);
    }

    const summaryDocs = await loadCatalogFromLegisSummaries();
    if (summaryDocs.length) {
      window.__LEX_DATA_SOURCE = "offline_summaries";
      console.info(`Lex: ${summaryDocs.length} documentos (legis_summaries.json)`);
      return summaryDocs;
    }

    window.__LEX_DATA_SOURCE = "fallback";
    const data = await fetchStaticJson(cfg.corpusFallback);
    const docs = data.documents || [];
    console.warn(`Lex: corpus demo (${docs.length} docs)`);
    return docs;
  }

  async function mergeJurisCatalogs(docs) {
    const [sumRes, temaRes] = await Promise.allSettled([
      fetchStaticJson(cfg.sumulasCatalogFallback),
      fetchStaticJson(cfg.temasCatalogFallback),
    ]);
    let out = docs;
    if (sumRes.status === "fulfilled") out = applySumulasCatalog(out, sumRes.value);
    if (temaRes.status === "fulfilled") out = applyTemasCatalog(out, temaRes.value);
    if (sumRes.status === "rejected") console.warn("Lex: catálogo de súmulas", sumRes.reason);
    if (temaRes.status === "rejected") console.warn("Lex: catálogo de temas", temaRes.reason);
    return out;
  }

  async function loadDocumentsCatalog() {
    if (window.LexLegisMeta?.loadKnownMeta) {
      await window.LexLegisMeta.loadKnownMeta();
    }
    await loadLegisSummariesCache().catch(() => ({}));

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
      const withAgu = await mergeAguFromOfflineBundle(merged);
      let prepared = window.LexFormat ? window.LexFormat.prepareCatalog(withAgu) : withAgu;
      await enrichLegisCatalog(prepared);
      console.info(`Lex: ${prepared.length} documentos (catálogo Supabase, ${merged.length} brutos)`);
      window.LexOffline?.saveCatalog?.(prepared, "supabase");
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
        const withAgu = await mergeAguFromOfflineBundle(viewRows);
        let prepared = window.LexFormat ? window.LexFormat.prepareCatalog(withAgu) : withAgu;
        await enrichLegisCatalog(prepared);
        console.info(`Lex: ${prepared.length} documentos (catálogo view)`);
        window.LexOffline?.saveCatalog?.(prepared, "supabase_view");
        return prepared;
      }
    } catch (err) {
      errors.push(String(err));
      console.warn("norma_document_catalog view:", err);
    }

    console.warn("Lex: offline/fallback —", errors.join("; ") || "catálogo remoto indisponível");
    let docs = await loadCatalogFromStaticFallback();
    docs = window.LexFormat ? window.LexFormat.prepareCatalog(docs) : docs;
    await enrichLegisCatalog(docs);
    return docs;
  }

  async function enrichDocuments(docs) {
    if (!Array.isArray(docs) || !docs.length) return docs || [];
    let prepared = docs;
    prepared = await mergeJurisCatalogs(prepared);
    await Promise.all([applyLegisSummaries(prepared), attachJurisPreviews(prepared)]);
    console.info(`Lex: ${prepared.length} documentos enriquecidos`);
    return prepared;
  }

  async function loadDocuments() {
    const catalog = await loadDocumentsCatalog();
    return enrichDocuments(catalog);
  }

  function enrichLegisDoc(doc) {
    if (doc.doc_type !== "legislacao") return doc;
    const url = doc.url || doc.doc_key || "";
    const known = window.LexLegisMeta?.lookupKnownMeta?.(url);
    const meta = window.LexLegisMeta?.metaFromUrl?.(url, doc.body || "") || known;
    if (!meta && !known && !window.LexLegisMeta?.resolveLegisTitle) return doc;
    const resolved = window.LexLegisMeta?.resolveLegisTitle?.(url, doc.body || "", doc.title);
    if (resolved) {
      const preferKnown =
        known?.titulo &&
        window.LexLegisMeta?.shouldPreferKnownLegisTitle?.(doc.title, known.titulo);
      doc.title = preferKnown ? known.titulo : resolved;
    } else if (known?.titulo) {
      doc.title = known.titulo;
    }
    const src = meta || known;
    if (known?.resumo) doc.resumo = known.resumo;
    else if (src?.resumo && !doc.resumo) doc.resumo = src.resumo;
    if (known?.secao) {
      if (!doc.organized) doc.organized = {};
      doc.organized.secao_lei_seca = known.secao;
    } else if (src && (src.secao || src.secao_lei_seca)) {
      if (!doc.organized) doc.organized = {};
      doc.organized.secao_lei_seca =
        doc.organized.secao_lei_seca || src.secao_lei_seca || src.secao;
    }
    return doc;
  }

  async function enrichLegisCatalog(docs) {
    return applyLegisSummaries(docs);
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
      const known = window.LexLegisMeta?.lookupKnownMeta?.(doc.url || doc.doc_key || "");
      if (known?.titulo) doc.title = known.titulo;
      else if (cached?.titulo) doc.title = cached.titulo;
      if (known?.resumo) doc.resumo = known.resumo;
      else if (cached?.resumo && !doc.resumo) doc.resumo = cached.resumo;
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
  let legisBodiesCache = null;
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
      const data = await fetchStaticJson(cfg.legisSummariesFallback);
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
      const data = await fetchStaticJson(cfg.jurisBodiesFallback);
      jurisBodiesCache = data.bodies || {};
      return jurisBodiesCache;
    } catch (err) {
      console.warn("Lex: cache juris local", err);
      return {};
    }
  }

  async function loadLegisBodiesCache() {
    if (legisBodiesCache) return legisBodiesCache;
    try {
      const data = await fetchStaticJson(cfg.legisBodiesFallback);
      legisBodiesCache = data.bodies || {};
      return legisBodiesCache;
    } catch (err) {
      console.warn("Lex: cache legis local", err);
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

  async function loadLegisDocumentText(doc) {
    const docKey = doc.doc_key || doc.url || "";
    const primary = doc.source_system || "rideel_vademecum";
    const sources =
      primary === "planalto"
        ? ["planalto", "rideel_vademecum"]
        : ["planalto", primary, "rideel_vademecum"];
    const tried = new Set();
    let best = "";
    for (const src of sources) {
      if (!src || tried.has(src)) continue;
      tried.add(src);
      let text = "";
      try {
        text = await loadDocumentChunks(src, { ...doc, source_system: src });
      } catch (_) {}
      if (!text) {
        try {
          const rpcText = await rpc("get_norma_document_text", {
            p_source: src,
            p_doc_key: docKey,
          });
          if (typeof rpcText === "string" && rpcText.trim()) text = rpcText;
        } catch (_) {}
      }
      if (text.length > best.length) best = text;
    }
    return best;
  }

  async function loadDocumentBody(doc) {
    if (doc.body && typeof doc.body === "string" && doc.body.trim()) {
      if (window.LexFormat) window.LexFormat.ensureFormatted(doc);
      return doc.body;
    }

    const cachedBody = await window.LexOffline?.loadDocumentBody?.(doc);
    if (cachedBody) {
      doc.body = cachedBody;
      if (window.LexFormat) window.LexFormat.ensureFormatted(doc);
      return doc.body;
    }

    const source = doc.source_system || (doc.external_id || "").split("::")[0];
    const docKey = doc.doc_key || (doc.external_id || "").split("::").slice(1).join("::");

    if (doc.doc_type === "legislacao" || source === "planalto" || source === "rideel_vademecum") {
      const legisCache = await loadLegisBodiesCache();
      const legisText = lookupCachedBody(legisCache, doc);
      if (legisText) {
        doc.body = legisText;
        if (window.LexFormat) window.LexFormat.ensureFormatted(doc);
        window.LexOffline?.saveDocumentBody?.(doc, doc.body);
        return doc.body;
      }
    }

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
    if (doc.doc_type === "legislacao" || source === "planalto" || source === "rideel_vademecum") {
      try {
        text = await loadLegisDocumentText(doc);
      } catch (err) {
        console.warn("Lex: texto legislação", docKey, err);
      }
    }
    if (!text) {
      try {
        text = await loadDocumentChunks(source, doc);
      } catch (err) {
        console.warn("Lex: chunks por URL", docKey, err);
      }
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
    window.LexOffline?.saveDocumentBody?.(doc, doc.body);
    if (window.LexLegisMeta) {
      if (window.LexLegisMeta.loadKnownMeta) await window.LexLegisMeta.loadKnownMeta();
      const url = doc.url || doc.doc_key || "";
      const resolved = window.LexLegisMeta.resolveLegisTitle?.(url, doc.body, doc.title);
      if (resolved) doc.title = resolved;
      const meta = window.LexLegisMeta.metaFromUrl(url, doc.body);
      const known = window.LexLegisMeta.lookupKnownMeta?.(url);
      if (known?.resumo) doc.resumo = known.resumo;
      else if (meta?.resumo) doc.resumo = meta.resumo;
      if (meta?.secao_lei_seca) {
        if (!doc.organized) doc.organized = {};
        doc.organized.secao_lei_seca = doc.organized.secao_lei_seca || meta.secao_lei_seca;
      }
    }
    if (window.LexFormat) window.LexFormat.ensureFormatted(doc);
    return doc.body;
  }

  let flashcardsCache = null;
  let flashcardsLoadPromise = null;
  let flashcardsHydratePromise = null;

  function deckCardCount(deck) {
    return deck.cardCount ?? (deck.cards?.length || 0);
  }

  function mapFlashcardCards(rawCards) {
    return (rawCards || [])
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0))
      .map((c) => ({
        front: c.front,
        back: c.back,
        highlight: c.highlight,
      }));
  }

  function mapFlashcardDecks(decks, cards) {
    const byDeck = {};
    for (const c of cards) {
      if (!byDeck[c.deck_id]) byDeck[c.deck_id] = [];
      byDeck[c.deck_id].push(c);
    }
    return decks.map((d) => {
      const mapped = mapFlashcardCards(byDeck[d.id] || []);
      return {
        slug: d.slug,
        name: d.name,
        category: d.category,
        cardCount: mapped.length,
        cards: mapped,
      };
    });
  }

  async function lexDeckCardCount(deckId) {
    const res = await fetch(
      `${cfg.supabaseUrl}/rest/v1/flashcards?deck_id=eq.${encodeURIComponent(deckId)}&select=id&limit=1`,
      { headers: { ...headers(cfg.lexSchema), Prefer: "count=exact" } }
    );
    if (!res.ok) throw new Error(String(res.status));
    const range = res.headers.get("content-range") || "";
    const m = range.match(/\/(\d+)$/);
    return m ? parseInt(m[1], 10) : 0;
  }

  async function fetchCardsForDeckId(deckId) {
    const limit = cfg.flashcardsPageSize || 1000;
    const cardCols = "deck_id,front,back,highlight,sort_order";
    const cards = [];
    for (let offset = 0; ; offset += limit) {
      const batch = await lexFetch(
        "flashcards",
        `select=${cardCols}&deck_id=eq.${encodeURIComponent(deckId)}&order=sort_order.asc&limit=${limit}&offset=${offset}`
      );
      if (!Array.isArray(batch) || !batch.length) break;
      cards.push(...batch);
      if (batch.length < limit) break;
    }
    return cards;
  }

  async function loadFlashcardDeckIndexFromSupabase() {
    const decks = await lexFetch("flashcard_decks", "select=id,slug,name,category,sort_order&order=sort_order.asc");
    if (!Array.isArray(decks) || !decks.length) throw new Error("empty");
    const index = await Promise.all(
      decks.map(async (d) => {
        let cardCount = 0;
        try {
          cardCount = await lexDeckCardCount(d.id);
        } catch (_) {
          /* ignora contagem individual */
        }
        return {
          slug: d.slug,
          name: d.name,
          category: d.category,
          cardCount,
          cards: [],
          _deckId: d.id,
        };
      })
    );
    if (!index.some((d) => d.cardCount > 0)) throw new Error("empty cards");
    return index;
  }

  async function hydrateFlashcardsFromSupabase(index) {
    const hydrated = await Promise.all(
      index.map(async (d) => {
        const raw = await fetchCardsForDeckId(d._deckId);
        const cards = mapFlashcardCards(raw);
        return {
          slug: d.slug,
          name: d.name,
          category: d.category,
          cardCount: cards.length,
          cards,
        };
      })
    );
    return hydrated.filter((d) => d.cards.length);
  }

  async function loadFlashcardsFromSupabase() {
    const index = await loadFlashcardDeckIndexFromSupabase();
    const hydrated = await hydrateFlashcardsFromSupabase(index);
    if (!hydrated.length) throw new Error("empty cards");
    const total = hydrated.reduce((n, d) => n + d.cards.length, 0);
    console.info(`Lex: ${hydrated.length} decks · ${total} flashcards (Supabase)`);
    return hydrated;
  }

  async function loadFlashcardIndexFromFallback() {
    let data;
    try {
      data = await fetchStaticJson(cfg.flashcardsCatalogFallback);
    } catch (_) {
      data = await fetchStaticJson(cfg.flashcardsFallback);
    }
    const decks = (data.decks || []).map((d) => ({
      slug: d.slug,
      name: d.name,
      category: d.category,
      cardCount: d.cardCount ?? d.cards?.length ?? 0,
      cards: Array.isArray(d.cards) ? d.cards : [],
    }));
    if (!decks.length) throw new Error("empty");
    if (!decks.some((d) => deckCardCount(d) > 0)) throw new Error("empty cards");
    return decks;
  }

  async function hydrateDeckFromFallback(deck) {
    if (deck.cards?.length) return deck;
    const base = cfg.flashcardsDecksBase || "./data/flashcards/decks/";
    const data = await fetchStaticJson(`${base}${deck.slug}.json`);
    const cards = data.cards || [];
    return { ...deck, cardCount: cards.length, cards };
  }

  async function hydrateFlashcardsFromFallback(index) {
    const hydrated = await Promise.all(index.map((d) => hydrateDeckFromFallback(d)));
    return hydrated.filter((d) => d.cards.length);
  }

  async function loadFlashcardsFromFallback() {
    const index = await loadFlashcardIndexFromFallback();
    if (index.every((d) => d.cards?.length)) {
      console.info(
        `Lex: ${index.length} decks · ${index.reduce((n, d) => n + d.cards.length, 0)} flashcards (cache local)`
      );
      return index;
    }
    const hydrated = await hydrateFlashcardsFromFallback(index);
    if (!hydrated.length) throw new Error("empty cards");
    const total = hydrated.reduce((n, d) => n + d.cards.length, 0);
    console.info(`Lex: ${hydrated.length} decks · ${total} flashcards (cache local por deck)`);
    return hydrated;
  }

  async function ensureFlashcardDeckHydrated(slug) {
    const decks = await loadFlashcardDecks();
    const deck = decks.find((d) => d.slug === slug);
    if (!deck) return null;
    if (deck.cards?.length) return deck;

    try {
      const index = await loadFlashcardDeckIndexFromSupabase();
      const row = index.find((d) => d.slug === slug);
      if (row?._deckId) {
        const cards = mapFlashcardCards(await fetchCardsForDeckId(row._deckId));
        Object.assign(deck, { cards, cardCount: cards.length });
        return deck;
      }
    } catch (_) {
      /* tenta fallback */
    }

    const hydrated = await hydrateDeckFromFallback(deck);
    const idx = decks.findIndex((d) => d.slug === slug);
    if (idx >= 0) decks[idx] = hydrated;
    flashcardsCache = decks;
    return hydrated;
  }

  function whenFlashcardsHydrated() {
    if (flashcardsCache?.length && flashcardsCache.every((d) => d.cards?.length)) {
      return Promise.resolve(flashcardsCache);
    }
    return flashcardsHydratePromise || Promise.resolve(flashcardsCache || []);
  }

  async function loadFlashcardDecks(force = false) {
    if (!force && flashcardsCache) return flashcardsCache;
    if (!force && flashcardsLoadPromise) return flashcardsLoadPromise;

    flashcardsLoadPromise = (async () => {
      const loadFull = async () => {
        try {
          return await loadFlashcardsFromSupabase();
        } catch (supabaseErr) {
          console.warn("Lex: flashcards Supabase indisponível, tentando cache local", supabaseErr);
          return loadFlashcardsFromFallback();
        }
      };

      try {
        const index = await loadFlashcardDeckIndexFromSupabase();
        flashcardsCache = index;
        flashcardsHydratePromise = loadFull()
          .then((full) => {
            flashcardsCache = full;
            return full;
          })
          .catch((err) => {
            console.warn("Lex: hidratação de flashcards falhou", err);
            return flashcardsCache;
          });
        console.info(
          `Lex: ${index.length} decks listados · hidratando ${index.reduce((n, d) => n + deckCardCount(d), 0)} cards…`
        );
        return index;
      } catch (indexErr) {
        console.warn("Lex: índice Supabase indisponível, carregamento completo", indexErr);
        flashcardsCache = await loadFull();
        return flashcardsCache;
      }
    })();

    try {
      return await flashcardsLoadPromise;
    } finally {
      flashcardsLoadPromise = null;
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
      const data = await fetchStaticJson(cfg.questoesCatalogFallback);
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
        window.LexOffline?.saveQuestions?.(out);
        return out;
      }
    } catch (err) {
      console.warn("Lex: questoes_banco", err);
    }

    const cached = await window.LexOffline?.loadQuestions?.();
    if (cached?.length) {
      console.info(`Lex: ${cached.length} questões (cache IndexedDB)`);
      return cached;
    }

    const fallback = await loadQuestionsFromFallback();
    if (fallback.length) console.info(`Lex: ${fallback.length} questões (fallback local)`);
    return fallback;
  }

  window.LexData = {
    loadDocuments,
    loadDocumentsCatalog,
    enrichDocuments,
    loadDocumentBody,
    loadFlashcardDecks,
    ensureFlashcardDeckHydrated,
    whenFlashcardsHydrated,
    deckCardCount,
    loadQuestions,
    loadQuestionsCount,
    mapQuestaoRow,
    parseAlternativas: formatQuestaoAlternativas,
    rpc,
    publicFetch,
  };
})();
