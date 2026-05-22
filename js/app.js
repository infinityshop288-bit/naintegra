/** NaIntegra Lex — SPA (naintegracursos.com.br/lex) */
(function () {
  const LS = window.LexStore?.LS || {
    highlights: "lex_highlights",
    notes: "lex_notes",
    progress: "lex_reading_progress",
    studied: "lex_studied_items",
    flashReviews: "lex_flashcard_reviews",
    fontSize: "lex_font_size",
    recentReads: "lex_recent_reads",
  };

  const store = () => window.LexStore;

  const FONT_SIZES = [11, 13, 15, 17, 19];
  const LEI_SECOES = [
    "Constituição e Adm.",
    "Penal e Processual",
    "Civil e Trabalho",
    "Legislação Especial",
  ];

  let state = {
    documents: [],
    decks: [],
    route: parseRoute(),
    reader: null,
    flashSession: null,
    tts: null,
    questionsLoaded: false,
    questionsLoading: false,
    questionsCount: null,
    questionsPage: 1,
    questionsPageSize: 50,
    qAnswers: {},
    subscriptionActive: false,
    subscriptionChecked: false,
  };

  function loadJson(key, fallback) {
    if (store()?.loadJson) return store().loadJson(key, fallback);
    try {
      return JSON.parse(localStorage.getItem(key) || "null") ?? fallback;
    } catch {
      return fallback;
    }
  }

  function saveJson(key, val) {
    if (store()?.saveJson) store().saveJson(key, val);
    else localStorage.setItem(key, JSON.stringify(val));
  }

  function docStudyType(doc) {
    if (!doc) return "legislacao";
    if (doc.doc_type === "jurisprudencia" || doc.doc_type === "sumula") return "jurisprudencia";
    return "legislacao";
  }

  function parseRoute() {
    const raw = location.hash.replace(/^#/, "") || "/";
    const qIdx = raw.indexOf("?");
    const query = qIdx >= 0 ? raw.slice(qIdx + 1) : "";
    const pathPart = qIdx >= 0 ? raw.slice(0, qIdx) : raw;
    const params = new URLSearchParams(query);
    const theme = params.get("t") || "";
    const sub = params.get("q");
    const plan = params.get("plan") || "";

    if (pathPart === "/" || !pathPart) {
      return { path: "home", id: null, sub, theme, plan };
    }

    const rest = pathPart.startsWith("/") ? pathPart.slice(1) : pathPart;
    const slash = rest.indexOf("/");
    if (slash === -1) return { path: rest, id: null, sub, theme, plan };

    const path = rest.slice(0, slash);
    const encodedId = rest.slice(slash + 1);
    let id = encodedId;
    if (encodedId) {
      try {
        id = decodeURIComponent(encodedId);
      } catch {
        id = encodedId;
      }
    }
    return { path, id: id || null, sub, theme, plan };
  }

  function isPublicRoute(path) {
    const pub = window.LEX_CONFIG?.publicRoutes || ["assinatura", "contato", "auth"];
    return pub.includes(path) || path.startsWith("auth");
  }

  async function ensureSubscriptionGate() {
    if (!window.LexSubscription) {
      state.subscriptionChecked = true;
      state.subscriptionActive = true;
      return true;
    }
    state.subscriptionActive = await window.LexSubscription.isSubscribed(true);
    state.subscriptionChecked = true;
    return state.subscriptionActive;
  }

  function updateThemeHash(theme) {
    const r = state.route;
    if (r.id) return;
    const base = r.path === "home" ? "#/" : `#/${r.path}`;
    const params = new URLSearchParams();
    const t = (theme || "").trim();
    if (t) params.set("t", t);
    if (r.sub) params.set("q", r.sub);
    const qs = params.toString();
    const next = qs ? `${base}?${qs}` : base;
    if (location.hash !== next) location.hash = next;
  }

  const SS = () => window.LexSectionSearch;

  function sectionSearchBar(section, placeholder) {
    if (!SS()) return "";
    return SS().bar(section, state.route.theme || "", placeholder);
  }

  function bindPageSectionSearch(section) {
    if (!SS()) return;
    const scope = document.querySelector(`[data-section-scope="${section}"]`);
    SS().bind(scope, section, (val) => updateThemeHash(val));
  }

  function setAppHtml(html) {
    const app = document.getElementById("app");
    if (app) app.innerHTML = html;
  }

  function docHash(route, externalId) {
    return `#/${route}/${encodeURIComponent(externalId)}`;
  }

  function byType(type) {
    if (type === "jurisprudencia") {
      return state.documents.filter((d) => d.doc_type === "jurisprudencia" || d.doc_type === "sumula");
    }
    return state.documents.filter((d) => d.doc_type === type);
  }

  function findDocument(id) {
    if (!id) return null;
    const exact =
      state.documents.find((d) => d.lex_route_id === id) ||
      state.documents.find((d) => d.external_id === id);
    if (exact) return exact;

    const norm = id.trim().toLowerCase();
    return (
      state.documents.find((d) => (d.lex_route_id || "").toLowerCase() === norm) ||
      state.documents.find((d) => (d.doc_key || "").toLowerCase() === norm) ||
      state.documents.find((d) => (d.url || "").toLowerCase() === norm) ||
      state.documents.find((d) => d.external_id.endsWith(id) || id.endsWith(d.doc_key || "")) ||
      null
    );
  }

  function readerRouteId(doc) {
    return doc.lex_route_id || doc.external_id;
  }

  function org(d) {
    return { ...(d.organized || {}), ...(d.meta || {}) };
  }

  function esc(s) {
    const el = document.createElement("span");
    el.textContent = s ?? "";
    return el.innerHTML;
  }

  function parseArticles(doc) {
    if (doc.formatted?.articles?.length) return doc.formatted.articles;
    if (!doc.body) return [];
    return window.LexFormat
      ? window.LexFormat.formatDocument(doc).articles
      : [{ id: 0, label: "Texto", text: doc.body }];
  }

  function readingProgress(docId) {
    if (store()) return store().readingProgress(docId);
    return loadJson(LS.progress, {})[docId] || { read: [], pct: 0 };
  }

  function setReadingProgress(docId, readIds, total) {
    if (store()) store().setReadingProgress(docId, readIds, total);
    else {
      const all = loadJson(LS.progress, {});
      all[docId] = { read: readIds, pct: total ? Math.round((readIds.length / total) * 100) : 0 };
      saveJson(LS.progress, all);
    }
  }

  function isStudied(id) {
    if (store()) return store().isStudied(id);
    return (loadJson(LS.studied, []) || []).includes(id);
  }

  function toggleStudied(id) {
    if (store()) store().toggleStudied(id);
    else {
      let list = loadJson(LS.studied, []) || [];
      if (list.includes(id)) list = list.filter((x) => x !== id);
      else list.push(id);
      saveJson(LS.studied, list);
    }
  }

  function getHighlights(docId, docType) {
    if (store()) return store().getHighlights(docId, docType);
    return loadJson(LS.highlights, {})[docId] || {};
  }

  function setHighlight(docId, artId, html, docType) {
    if (store()) store().setHighlight(docId, artId, html, docType);
    else {
      const all = loadJson(LS.highlights, {});
      if (!all[docId]) all[docId] = {};
      all[docId][artId] = html;
      saveJson(LS.highlights, all);
    }
  }

  function getNotes(docId, docType) {
    if (store()) return store().getNotes(docId, docType);
    return loadJson(LS.notes, {})[docId] || {};
  }

  function setNote(docId, blockKey, text, docType) {
    if (store()) store().setNote(docId, blockKey, text, docType);
    else {
      const all = loadJson(LS.notes, {});
      if (!all[docId]) all[docId] = {};
      all[docId][blockKey] = text;
      saveJson(LS.notes, all);
    }
  }

  function renderBlockNote(docId, blockKey, note, docType) {
    return `
      <div class="block-note" data-note-wrap="${esc(blockKey)}">
        <button type="button" class="block-note-toggle ${note ? "has-note" : ""}" data-note-toggle="${esc(blockKey)}" title="Anotação">
          ${note ? "📝 Anotação" : "＋ Anotar"}
        </button>
        <div class="block-note-panel" ${note ? "" : "hidden"}>
          <textarea class="block-note-input" data-note-input="${esc(blockKey)}" data-note-doc="${esc(docId)}" data-note-type="${esc(docType)}" placeholder="Sua anotação…">${esc(note || "")}</textarea>
        </div>
      </div>`;
  }

  function flashDueCount(deck) {
    const reviews = store()?.flashReviews() || loadJson(LS.flashReviews, {});
    const today = new Date().toISOString().slice(0, 10);
    return deck.cards.filter((_, i) => {
      const key = `${deck.slug}:${i}`;
      const r = reviews[key];
      return !r || r.due <= today;
    }).length;
  }

  function scheduleFlash(deckSlug, idx, rating) {
    const now = new Date();
    let due = new Date(now);
    if (rating === "err") due.setDate(due.getDate());
    else if (rating === "mid") due.setDate(due.getDate() + 1);
    else due.setDate(due.getDate() + 3);
    const dueStr = due.toISOString().slice(0, 10);
    if (store()) store().scheduleFlash(`${deckSlug}:${idx}`, dueStr, rating);
    else {
      const reviews = loadJson(LS.flashReviews, {});
      reviews[`${deckSlug}:${idx}`] = { due: dueStr, rating };
      saveJson(LS.flashReviews, reviews);
    }
  }

  function trackRecentRead(doc, backRoute) {
    if (store()?.trackRecentRead) store().trackRecentRead(doc, backRoute);
    else if (doc) {
      const type = doc.doc_type;
      if (type !== "legislacao" && type !== "jurisprudencia" && type !== "sumula") return;
      const routeId = readerRouteId(doc);
      const route = backRoute || (type === "legislacao" ? "lei-seca" : "jurisprudencia");
      const list = loadJson(LS.recentReads, []);
      const entry = { id: routeId, external_id: doc.external_id, route, doc_type: type, at: Date.now() };
      saveJson(LS.recentReads, [
        entry,
        ...list.filter((x) => x.id !== routeId && x.external_id !== doc.external_id),
      ].slice(0, 8));
    }
    renderRecentReads();
  }

  function recentReadLabel(doc) {
    if (doc.doc_type === "legislacao") {
      const p = readingProgress(doc.external_id);
      return p.pct ? `Lei · ${p.pct}% lido` : "Lei seca";
    }
    if (doc.doc_type === "sumula") {
      return isStudied(doc.external_id) ? "Súmula · estudada" : "Súmula";
    }
    return isStudied(doc.external_id) ? "Jurisprudência · estudada" : "Jurisprudência";
  }

  function renderRecentReads() {
    const el = document.getElementById("recent-reads");
    if (!el) return;
    const list = store()?.getRecentReads?.() || loadJson(LS.recentReads, []);
    const items = [];
    for (const entry of list) {
      const doc = findDocument(entry.id) || findDocument(entry.external_id);
      if (!doc) continue;
      if (!["legislacao", "jurisprudencia", "sumula"].includes(doc.doc_type)) continue;
      items.push({ doc, route: entry.route });
      if (items.length >= 6) break;
    }
    el.innerHTML = items.length
      ? items
          .map(({ doc, route }) => {
            const r = route || (doc.doc_type === "legislacao" ? "lei-seca" : "jurisprudencia");
            return `<a class="recent-read" href="${docHash(r, readerRouteId(doc))}">${esc(doc.title)}<small>${esc(recentReadLabel(doc))}</small></a>`;
          })
          .join("")
      : `<span class="tag">Abra uma lei ou julgado para ver aqui</span>`;
  }

  function questionsTotal() {
    const loaded = byType("questoes_objetivas").length + byType("questoes_subjetivas").length;
    if (loaded) return loaded;
    if (state.questionsCount != null) return state.questionsCount;
    return 0;
  }

  async function ensureQuestionsLoaded() {
    if (state.questionsLoaded || state.questionsLoading || !window.LexData?.loadQuestions) return;
    state.questionsLoading = true;
    render();
    try {
      const qs = await window.LexData.loadQuestions();
      if (qs.length) {
        const existing = new Set(state.documents.map((d) => d.external_id));
        for (const q of qs) {
          if (!existing.has(q.external_id)) state.documents.push(q);
        }
        state.questionsCount = qs.length;
      }
      state.questionsLoaded = true;
      if (window.LexSearch) window.LexSearch.refresh(state.documents, state.decks);
    } catch (err) {
      console.error(err);
    } finally {
      state.questionsLoading = false;
      render();
    }
  }

  function setActiveNav() {
    const r = state.route.path === "home" ? "/" : `/${state.route.path}`;
    document.querySelectorAll("[data-route]").forEach((a) => {
      a.classList.toggle("active", a.getAttribute("data-route") === r);
    });
  }

  function renderHome() {
    const nLeg = byType("legislacao").length;
    const nJur = byType("jurisprudencia").length;
    const nDeck = state.decks.length;
    const nQ = questionsTotal();

    return `
      <section class="hero">
        <h1>Legislação &amp; Jurisprudência para Concurseiros</h1>
        <p>Lei seca com grifos e áudio, flashcards com revisão espaçada e jurisprudência dos tribunais superiores.</p>
        <p class="sync-hint" id="sync-hint" hidden>Entre na sua conta para sincronizar grifos e anotações entre dispositivos.</p>
      </section>
      <div class="tiles">
        <button class="tile" data-go="flashcards">
          <div class="icon">🃏</div>
          <h2>Flashcards</h2>
          <p>${nDeck} disciplinas · revisão SM-2</p>
        </button>
        <button class="tile" data-go="lei-seca">
          <div class="icon">📜</div>
          <h2>Lei Seca</h2>
          <p>${nLeg} leis · grifos e narração</p>
        </button>
        <button class="tile" data-go="jurisprudencia">
          <div class="icon">⚖️</div>
          <h2>Jurisprudência</h2>
          <p>${nJur} súmulas e teses</p>
        </button>
        <button class="tile" data-go="questoes">
          <div class="icon">📝</div>
          <h2>Questões</h2>
          <p>${nQ} questões · filtros por banca</p>
        </button>
      </div>`;
  }

  function renderFlashcardsList() {
    if (!state.decks.length) {
      return `<div class="page-head"><h1>Flashcards</h1><p>Nenhum deck disponível no momento.</p></div><div class="empty">Novos decks serão disponibilizados em breve.</div>`;
    }
    const ss = SS();
    return `
      <div class="page-head"><h1>Flashcards</h1><p>Escolha a disciplina para iniciar a sessão de revisão.</p></div>
      ${sectionSearchBar("flashcards", "Buscar deck ou tema (ex.: constitucional, penal)…")}
      <div class="section-list-scope" data-section-scope="flashcards">
        <div class="card-list">
          ${state.decks
            .map((d) => {
              const due = flashDueCount(d);
              const searchText = ss ? ss.deckText(d) : d.name;
              return `
            <article class="deck-card" data-deck="${esc(d.slug)}" data-search-text="${esc(searchText)}">
              <span class="tag">${esc(d.category)}</span>
              <h3>${esc(d.name)}</h3>
              <p>${d.cards.length} cards · <strong>${due} vencem hoje</strong></p>
            </article>`;
            })
            .join("")}
        </div>
        <div class="empty section-search-empty" data-section-empty hidden>Nenhum deck ou card para este tema.</div>
      </div>`;
  }

  function renderFlashSession(slug) {
    const deck = state.decks.find((d) => d.slug === slug);
    if (!deck) return `<div class="empty">Deck não encontrado.</div>`;
    const s = state.flashSession || { idx: 0, flipped: false, stats: { err: 0, mid: 0, ok: 0 } };
    const card = deck.cards[s.idx];
    if (!card) {
      const total = s.stats.err + s.stats.mid + s.stats.ok;
      return `
        <div class="page-head"><h1>Sessão concluída</h1><p>${esc(deck.name)}</p></div>
        <div class="reader-body">
          <p><strong>Errei:</strong> ${s.stats.err}</p>
          <p><strong>Difícil:</strong> ${s.stats.mid}</p>
          <p><strong>Fácil:</strong> ${s.stats.ok}</p>
          <p style="margin-top:1rem"><a href="#/flashcards">← Voltar aos decks</a></p>
        </div>`;
    }
    const backHtml = card.highlight
      ? card.back.replace(
          new RegExp(escRegex(card.highlight), "g"),
          `<mark>${esc(card.highlight)}</mark>`
        )
      : card.back;
    const flashDocId = slug;
    const flashBlock = String(s.idx);
    const flashNote = getNotes(flashDocId, "flashcard")[flashBlock] || "";

    return `
      <div class="page-head">
        <h1>${esc(deck.name)}</h1>
        <p>Card ${s.idx + 1} de ${deck.cards.length}</p>
      </div>
      <div class="flash-scene">
        <div class="flash-card ${s.flipped ? "flipped" : ""}" id="flash-card">
          <div class="flash-face front"><p>${esc(card.front)}</p><small style="color:var(--muted);margin-top:auto">Toque para revelar</small></div>
          <div class="flash-face back"><p>${backHtml}</p></div>
        </div>
      </div>
      <div class="flash-note-wrap">
        <label class="flash-note-label">Anotação pessoal</label>
        <textarea class="block-note-input flash-note-input" data-note-input="${esc(flashBlock)}" data-note-doc="${esc(flashDocId)}" data-note-type="flashcard" placeholder="Anote dicas, mnemônicos ou referências…">${esc(flashNote)}</textarea>
      </div>
      ${renderReportError({
        area: "flashcards",
        id: `${slug}::card::${s.idx}`,
        title: deck.name,
        extra: `Card ${s.idx + 1}/${deck.cards.length}: ${(card.front || "").slice(0, 160)}`,
      })}
      ${
        s.flipped
          ? `<div class="flash-actions">
          <button class="btn err" data-rate="err">Errei<br><small>hoje</small></button>
          <button class="btn mid" data-rate="mid">Difícil<br><small>amanhã</small></button>
          <button class="btn ok" data-rate="ok">Fácil<br><small>3 dias</small></button>
        </div>`
          : ""
      }`;
  }

  function escRegex(s) {
    return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  }

  function renderLeiSecaList() {
    const laws = byType("legislacao");
    const sections = LEI_SECOES.map((secName) => ({
      name: secName,
      items: laws.filter((d) => (org(d).secao_lei_seca || "Legislação Especial") === secName),
    }));
    const uncat = laws.filter((d) => {
      const sec = org(d).secao_lei_seca;
      return !sec || !LEI_SECOES.includes(sec);
    });
    if (uncat.length) sections.push({ name: "Outros", items: uncat });

    if (!laws.length) {
      return `<div class="page-head"><h1>Lei Seca</h1></div><div class="empty">Nenhuma legislação disponível no momento.</div>`;
    }

    return `
      <div class="page-head"><h1>Lei Seca</h1><p>Texto consolidado das normas — leitura artigo por artigo.</p></div>
      ${sectionSearchBar("lei-seca", "Buscar lei por tema (ex.: processo penal, drogas, SUS)…")}
      <div class="section-list-scope" data-section-scope="lei-seca">
      ${sections
        .filter((s) => s.items.length)
        .map(
          (sec) => `
        <section class="lei-section" data-search-group>
        <h2 style="font-family:var(--font-serif);font-size:1.1rem;margin:1.25rem 0 0.65rem">${esc(sec.name)}</h2>
        <div class="card-list">
          ${sec.items
            .map((d) => {
              const arts = parseArticles(d);
              const p = readingProgress(d.external_id);
              const countLabel = arts.length > 1 ? `${arts.length} dispositivos` : "Abrir leitura";
              const searchText = SS() ? SS().lawText(d, org) : d.title;
              return `
              <article class="law-card" data-law="${esc(readerRouteId(d))}" data-search-text="${esc(searchText)}">
                <h3>${esc(d.title)}</h3>
                ${d.resumo ? `<p class="law-summary">${esc(d.resumo)}</p>` : ""}
                <p class="law-meta">${countLabel} · ${p.pct}% lido</p>
                <div class="meta-row">${(org(d).tags_incidencia || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}</div>
                <div class="progress-bar"><span style="width:${p.pct}%"></span></div>
              </article>`;
            })
            .join("")}
        </div>
        </section>`
        )
        .join("")}
        <div class="empty section-search-empty" data-section-empty hidden>Nenhuma lei para este tema.</div>
      </div>`;
  }

  function renderReader(docId, backRoute) {
    const doc = findDocument(docId);
    if (!doc) return `<div class="empty">Documento não encontrado.</div>`;
    if (!doc.body) return `<div class="loading">Carregando texto…</div>`;

    if (window.LexFormat) window.LexFormat.ensureFormatted(doc);

    const articles = parseArticles(doc);
    const studyType = docStudyType(doc);
    const prog = readingProgress(docId);
    const fontIdx = loadJson(LS.fontSize, 2);
    const fontSize = FONT_SIZES[fontIdx] || 15;
    const r = state.reader || { activeArt: 0, narrating: false };
    const highlights = getHighlights(docId, studyType);
    const notes = getNotes(docId, studyType);
    const F = window.LexFormat;

    let bodyHtml = "";
    if (doc.formatted?.mode === "legislacao") {
      const leg = doc.formatted;
      bodyHtml = `
        ${leg.epigrafe ? `<header class="lei-epigrafe">${esc(leg.epigrafe)}</header>` : ""}
        ${leg.ementa ? `<p class="lei-ementa">${esc(leg.ementa)}</p>` : ""}
        ${leg.blocks.map((b, i) => {
          const saved = highlights[i];
          const note = notes[i];
          if (saved) {
            return `<article class="lei-artigo annot-block" id="art-${i}" data-art-id="${i}"><div class="lei-label">${esc(b.label)}</div><div class="lei-text article-text">${saved}</div>${renderBlockNote(docId, i, note, studyType)}</article>`;
          }
          const blockHtml = F.renderLegisBlock(b, i).replace('class="lei-text"', 'class="lei-text article-text"');
          return blockHtml.replace(/<\/article>\s*$/, `${renderBlockNote(docId, i, note, studyType)}</article>`);
        }).join("")}`;
    } else if (doc.formatted?.mode === "juris") {
      const items = doc.formatted.items || [];
      bodyHtml = items.length
        ? `<div class="juris-list">${items
            .map((it, i) => {
              const saved = highlights[i];
              const note = notes[i];
              if (saved) {
                return `<article class="juris-item annot-block" id="art-${i}" data-art-id="${i}"><div class="article-text">${saved}</div>${renderBlockNote(docId, i, note, studyType)}</article>`;
              }
              let itemHtml = F.renderJurisItem(it, i)
                .replace('<article class="juris-item"', `<article class="juris-item annot-block" id="art-${i}" data-art-id="${i}"`)
                .replace(/class="juris-section-text"/g, 'class="juris-section-text article-text"');
              return itemHtml.replace(/<\/article>\s*$/, `${renderBlockNote(docId, i, note, studyType)}</article>`);
            })
            .join("")}</div>`
        : (() => {
            const note = notes[0];
            const saved = highlights[0];
            const inner = saved || esc(doc.body);
            return `<div class="juris-list"><article class="juris-item annot-block" id="art-0" data-art-id="0"><div class="article-text">${inner}</div>${renderBlockNote(docId, 0, note, studyType)}</article></div>`;
          })();
    } else {
      bodyHtml = articles
        .map(
          (a, i) => `
        <article class="article-block annot-block" id="art-${i}" data-art-id="${i}">
          <div class="article-num">${esc(a.label)}</div>
          <div class="article-text">${highlights[i] || esc(a.text)}</div>
          ${renderBlockNote(docId, i, notes[i], studyType)}
        </article>`
        )
        .join("");
    }

    const panel = `
      <aside class="panel">
        <div class="ring">${prog.pct}%</div>
        <div class="audio-panel">
          <h4>Narração</h4>
          <button class="btn primary" id="tts-toggle">${r.narrating ? "⏸ Pausar" : "🎧 Ouvir"}</button>
          <div class="audio-progress" id="tts-progress"><span style="width:0"></span></div>
          <div class="reader-tools" style="justify-content:center;margin-top:0.5rem">
            <button class="btn icon" id="tts-prev">◁</button>
            <button class="btn icon" id="tts-rew">⟪</button>
            <button class="btn icon" id="tts-fwd">⟫</button>
            <button class="btn icon" id="tts-next">▷</button>
          </div>
          <div class="toolbar" style="justify-content:center;margin-top:0.5rem">
            ${[0.75, 1, 1.25, 1.5].map((sp) => `<button class="chip ${r.speed === sp ? "active" : ""}" data-speed="${sp}">${sp}×</button>`).join("")}
          </div>
        </div>
      </aside>`;

    return {
      html: `
        <div class="content">
          <div class="reader-head">
            <div>
              <a href="#/${backRoute || "lei-seca"}" class="back-link">← Voltar</a>
              <h1 class="reader-title">${esc(doc.title)}</h1>
            </div>
            <div class="reader-tools">
              <button class="btn icon" id="font-down">A−</button>
              <button class="btn icon" id="font-up">A+</button>
              <button class="btn" id="mark-read">🔖 Marcar lido</button>
              ${renderReportError({
                area: studyType,
                id: doc.external_id,
                title: doc.title || docId,
              })}
            </div>
          </div>
          ${
            articles.length > 1
              ? `<div class="article-pills">
            ${articles.map((a, i) => `<button class="pill ${prog.read.includes(i) ? "read" : ""} ${r.activeArt === i ? "active" : ""}" data-art="${i}">${esc(a.label.length > 18 ? a.label.slice(0, 16) + "…" : a.label)}</button>`).join("")}
          </div>`
              : ""
          }
          <div class="progress-bar" style="margin-bottom:1rem"><span style="width:${prog.pct}%"></span></div>
          <div class="reader-body ${doc.formatted?.mode === "juris" ? "reader-juris" : "reader-lei"}" id="reader-body" style="font-size:${fontSize}px">
            ${bodyHtml}
          </div>
        </div>
        ${doc.formatted?.mode === "legislacao" ? panel : ""}`,
      doc,
      articles,
    };
  }

  function renderJurisprudencia() {
    const items = byType("jurisprudencia");
    const tribunals = ["all", ...new Set(items.map((d) => org(d).tribunal || "STF"))].filter(
      (t) => t !== "Outros"
    );
    const filter = state.jurisFilter || { tribunal: "all", materia: "all", tipo: "all" };

    const filtered = items.filter((d) => {
      const o = org(d);
      if (filter.tribunal !== "all" && (o.tribunal || "STF") !== filter.tribunal) return false;
      if (filter.tipo === "sumula_individual") {
        if (d.doc_type !== "sumula" && d.catalog_kind !== "sumula_individual") return false;
      } else if (filter.tipo === "tema_rg") {
        if (d.catalog_kind !== "tema") return false;
        if (d.meta?.tema_categoria === "recurso_repetitivo") return false;
        if (d.meta?.tema_categoria === "repercussao_geral") return true;
        const u = (d.url || d.doc_key || "").toLowerCase();
        if (u.includes("temas-stf") || (u.includes("/tema-") && !u.includes("repetitivo"))) return true;
        return false;
      } else if (filter.tipo === "tema_rep") {
        if (d.catalog_kind !== "tema") return false;
        if (d.meta?.tema_categoria === "repercussao_geral") return false;
        if (d.meta?.tema_categoria === "recurso_repetitivo") return true;
        const u = (d.url || d.doc_key || "").toLowerCase();
        return u.includes("temas-stj") || u.includes("temas-tst") || u.includes("repetitivo");
      } else if (filter.tipo === "tema") {
        if (d.catalog_kind !== "tema") return false;
      } else if (filter.tipo !== "all" && d.catalog_kind !== filter.tipo) return false;
      return true;
    });

    const tipos = [
      ["all", "Todos"],
      ["tema", "Temas"],
      ["tema_rg", "Repercussão Geral"],
      ["tema_rep", "Recurso Repetitivo"],
      ["julgado", "Julgados"],
      ["sumula_individual", "Súmulas"],
      ["sumulas_colecao", "Compilados"],
      ["sumulas_vinculantes", "Vinculantes"],
    ];

    return `
      <div class="page-head"><h1>Jurisprudência &amp; Súmulas</h1><p>Precedentes dos tribunais superiores — ementa, tese e julgado.</p></div>
      ${sectionSearchBar("jurisprudencia", "Buscar por tema (ex.: habeas corpus, repercussão geral, ICMS)…")}
      <div class="toolbar">
        ${tribunals.map((t) => `<button class="tab ${filter.tribunal === t ? "active" : ""}" data-tribunal="${esc(t)}">${t === "all" ? "Todos os tribunais" : esc(t)}</button>`).join("")}
      </div>
      <div class="toolbar">
        ${tipos.map(([k, label]) => `<button class="chip ${filter.tipo === k ? "active" : ""}" data-tipo="${k}">${label}</button>`).join("")}
      </div>
      <div class="section-list-scope" data-section-scope="jurisprudencia">
      <div class="card-list">
        ${
          filtered.length
            ? filtered
                .map((d) => {
                  const o = org(d);
                  const studied = isStudied(d.external_id);
                  const preview =
                    (window.LexFormat && window.LexFormat.jurisCardPreview(d)) ||
                    d.juris_card_preview ||
                    o.tribunal ||
                    "";
                  const searchText = SS() ? SS().jurisText(d, org) : d.title;
                  return `
            <article class="juris-card ${studied ? "studied" : ""}" data-juris-open="${esc(readerRouteId(d))}" data-search-text="${esc(searchText)}">
              <span class="juris-tribunal-badge">${esc(o.tribunal || "STF")}</span>
              <h3>${esc(d.title)}</h3>
              <p class="juris-card-sub">${esc(preview)}</p>
              <div class="meta-row">
                ${d.meta?.vinculante ? `<span class="tag">Vinculante</span>` : ""}
                ${d.doc_type === "sumula" || d.catalog_kind === "sumula_individual" ? `<span class="tag">Súmula</span>` : ""}
                ${d.catalog_kind === "tema" ? `<span class="tag">Tema</span>` : ""}
                ${d.meta?.tema_categoria === "repercussao_geral" ? `<span class="tag">Repercussão Geral</span>` : ""}
                ${d.meta?.tema_categoria === "recurso_repetitivo" ? `<span class="tag">Recurso Repetitivo</span>` : ""}
                ${d.catalog_kind === "sumulas_vinculantes" ? `<span class="tag">Vinculante</span>` : ""}
                ${studied ? `<span class="tag">✓ Estudada</span>` : ""}
              </div>
              <div class="toolbar" style="margin-top:0.75rem;margin-bottom:0">
                <button class="btn" data-studied="${esc(d.external_id)}">${studied ? "Desmarcar" : "✅ Estudada"}</button>
                <button class="btn" data-fav="${esc(d.external_id)}">☆ Favoritar</button>
              </div>
            </article>`;
                })
                .join("")
            : `<div class="empty">Nenhum precedente para os filtros selecionados.</div>`
        }
      </div>
      <div class="empty section-search-empty" data-section-empty hidden>Nenhum precedente para este tema.</div>
      </div>`;
  }

  function parseAlternativas(meta) {
    if (window.LexData?.parseAlternativas) return window.LexData.parseAlternativas(meta?.alternativas || meta?.opcoes);
    return [];
  }

  function gabaritoKey(gabarito, alts) {
    const g = String(gabarito || "").trim();
    if (!g) return "";
    const upper = g.toUpperCase();
    if (/^[A-E]$/.test(upper)) return upper;
    const byKey = alts.find((a) => a.key.toUpperCase() === upper);
    if (byKey) return byKey.key;
    const gl = g.toLowerCase();
    const byText = alts.find((a) => a.text.toLowerCase() === gl || a.text.toLowerCase().startsWith(gl));
    if (byText) return byText.key;
    if (gl.includes("certo")) {
      const certo = alts.find((a) => /certo/i.test(a.text));
      if (certo) return certo.key;
    }
    if (gl.includes("errado")) {
      const errado = alts.find((a) => /errado/i.test(a.text));
      if (errado) return errado.key;
    }
    return upper.charAt(0);
  }

  function qAnswerState(qid) {
    if (!state.qAnswers[qid]) state.qAnswers[qid] = { pick: null, revealed: false };
    return state.qAnswers[qid];
  }

  function renderQuestaoCard(d) {
    const o = org(d);
    const meta = d.meta || {};
    const alts = parseAlternativas(meta);
    const isObj = d.doc_type === "questoes_objetivas" && alts.length;
    const qid = d.external_id;
    const qa = qAnswerState(qid);
    const correctKey = isObj ? gabaritoKey(meta.gabarito || meta.resposta_correta, alts) : "";
    const acertou = isObj && qa.revealed && qa.pick === correctKey;
    const searchText = SS() ? SS().questaoText(d, org) : d.body || d.title;

    let altsHtml = "";
    if (isObj) {
      altsHtml = `
        <div class="q-alts" role="group" aria-label="Alternativas">
          ${alts
            .map((a) => {
              const selected = qa.pick === a.key;
              const isCorrect = a.key === correctKey;
              let cls = "q-alt";
              if (selected && !qa.revealed) cls += " selected";
              if (qa.revealed) {
                if (isCorrect) cls += " correct";
                else if (selected) cls += " wrong";
              }
              return `
            <button type="button" class="${cls}" data-q-id="${esc(qid)}" data-alt-key="${esc(a.key)}" ${
                qa.revealed ? "disabled" : ""
              }>
              <span class="q-alt-key">${esc(a.key)})</span>
              <span class="q-alt-text">${esc(a.text)}</span>
            </button>`;
            })
            .join("")}
        </div>
        ${
          !qa.revealed
            ? `<button type="button" class="btn primary q-check-btn" data-q-check="${esc(qid)}" ${
                qa.pick ? "" : "disabled"
              }>Conferir resposta</button>`
            : `<div class="q-result ${acertou ? "ok" : "err"}">${acertou ? "✓ Você acertou!" : "✗ Você errou."}${
                !acertou && correctKey
                  ? ` Gabarito: <strong>${esc(correctKey)}</strong>.`
                  : ""
              }</div>`
        }`;
    }

    const showGabarito = !isObj ? qa.revealed : qa.revealed;
    const gabaritoBody = isObj
      ? meta.comentario || meta.explicacao || ""
      : meta.gabarito || meta.resposta_correta || meta.comentario || meta.explicacao || "";

    return `
      <article class="question-card" data-q="${esc(qid)}" data-search-text="${esc(searchText)}">
        <div class="meta-row">
          ${o.banca ? `<span class="tag">${esc(o.banca)} ${o.ano || ""}</span>` : ""}
          ${o.cargo ? `<span class="tag">${esc(o.cargo)}</span>` : ""}
          ${o.materia ? `<span class="tag">${esc(o.materia)}</span>` : ""}
        </div>
        <p class="q-enunciado">${esc(d.body || d.title)}</p>
        ${altsHtml}
        ${
          !isObj
            ? `<button type="button" class="btn primary q-reveal-sub" data-q-reveal="${esc(qid)}" ${
                qa.revealed ? "hidden" : ""
              }>Ver resposta padrão</button>`
            : ""
        }
        <div class="gabarito-panel" id="gab-${esc(qid)}" ${showGabarito ? "" : "hidden"}>
          ${!isObj ? `<strong>Resposta padrão:</strong> ${esc(gabaritoBody || "—")}<br>` : ""}
          ${isObj && gabaritoBody ? `<strong>Comentário:</strong> ${esc(gabaritoBody)}` : ""}
          ${!isObj && (meta.comentario || meta.explicacao) && meta.comentario !== gabaritoBody
            ? `<br><em>${esc(meta.comentario || meta.explicacao)}</em>`
            : ""}
        </div>
        ${renderReportError({
          area: "questoes",
          id: qid,
          title: (d.body || d.title || "").slice(0, 120),
          extra: [o.banca, o.ano, o.materia].filter(Boolean).join(" · "),
        })}
      </article>`;
  }

  function renderQuestoes() {
    if (state.questionsLoading) {
      return `
        <div class="page-head"><h1>Questões</h1><p>Carregando banco de questões do NaIntegra Cursos…</p></div>
        <div class="loading">Aguarde…</div>`;
    }

    const objs = byType("questoes_objetivas");
    const subs = byType("questoes_subjetivas");
    const all = [...objs, ...subs];
    const filter = state.qFilter || { banca: "all", disciplina: "all" };

    const filtered = all.filter((d) => {
      const o = org(d);
      if (filter.banca !== "all" && o.banca !== filter.banca) return false;
      if (filter.disciplina !== "all" && (o.materia || "").toLowerCase() !== filter.disciplina) return false;
      return true;
    });

    const bancas = ["all", ...new Set(all.map((d) => org(d).banca).filter(Boolean))];
    const pageSize = state.questionsPageSize || 50;
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
    const page = Math.min(Math.max(1, state.questionsPage || 1), totalPages);
    state.questionsPage = page;
    const pageItems = filtered.slice((page - 1) * pageSize, page * pageSize);

    if (!all.length) {
      return `
        <div class="page-head"><h1>Questões</h1><p>Objetivas (CESPE/FCC) e discursivas de segunda fase.</p></div>
        <div class="empty">As questões serão disponibilizadas em breve.</div>`;
    }

    return `
      <div class="page-head"><h1>Questões</h1><p>${objs.length} objetivas · ${subs.length} subjetivas</p></div>
      ${sectionSearchBar("questoes", "Buscar por tema (ex.: penal, constitucional, CESPE)…")}
      <div class="toolbar">
        ${bancas.map((b) => `<button class="chip ${filter.banca === b ? "active" : ""}" data-banca="${esc(b)}">${b === "all" ? "Todas bancas" : esc(b)}</button>`).join("")}
      </div>
      <p class="tag" style="margin:0 0 1rem">${filtered.length} no filtro · página ${page} de ${totalPages}</p>
      <div class="section-list-scope" data-section-scope="questoes">
      <div class="card-list">
        ${pageItems.map((d) => renderQuestaoCard(d)).join("")}
      </div>
      <div class="toolbar" style="margin-top:1rem">
        <button class="chip" data-q-page="prev" ${page <= 1 ? "disabled" : ""}>← Anterior</button>
        <button class="chip" data-q-page="next" ${page >= totalPages ? "disabled" : ""}>Próxima →</button>
      </div>
      <div class="empty section-search-empty" data-section-empty hidden>Nenhuma questão para este tema.</div>
      </div>`;
  }

  function contactEmail() {
    return window.LEX_CONFIG?.contactEmail || "contato@naintegracursos.com.br";
  }

  const REPORT_TYPE_LABELS = {
    equivocado: "Conteúdo equivocado",
    desatualizado: "Conteúdo desatualizado",
  };

  const REPORT_AREA_LABELS = {
    legislacao: "Lei Seca",
    jurisprudencia: "Jurisprudência",
    questoes: "Questões",
    flashcards: "Flashcards",
  };

  function renderReportError({ area, id, title, extra = "" }) {
    return `
      <div class="report-error-wrap" data-report-area="${esc(area)}" data-report-id="${esc(id)}" data-report-title="${esc(title)}" data-report-extra="${esc(extra)}">
        <button type="button" class="btn sm report-error-toggle">⚠ Reportar erro</button>
        <div class="report-error-menu" hidden>
          <p class="report-error-label">Qual o problema?</p>
          <button type="button" class="report-error-opt" data-report-type="equivocado">Conteúdo equivocado</button>
          <button type="button" class="report-error-opt" data-report-type="desatualizado">Conteúdo desatualizado</button>
        </div>
      </div>`;
  }

  function sendErrorReport({ area, id, title, type, extra }) {
    const typeLabel = REPORT_TYPE_LABELS[type] || type;
    const areaLabel = REPORT_AREA_LABELS[area] || area;
    const subject = encodeURIComponent(`NaIntegra Lex — Reporte: ${typeLabel}`);
    let body = `Tipo de reporte: ${typeLabel}\n`;
    body += `Área: ${areaLabel}\n`;
    body += `Item: ${title}\n`;
    body += `ID: ${id}\n`;
    if (extra) body += `Detalhe: ${extra}\n`;
    body += `URL: ${location.href}\n`;
    body += `\nDescreva o erro encontrado (edite antes de enviar, se quiser):\n\n`;
    body += `\n---\nReporte automático — NaIntegra Lex`;
    window.location.href = `mailto:${contactEmail()}?subject=${subject}&body=${encodeURIComponent(body)}`;
  }

  function bindReportError() {
    if (!window.__lexReportOutsideClose) {
      window.__lexReportOutsideClose = true;
      document.addEventListener("click", () => {
        document.querySelectorAll(".report-error-menu").forEach((m) => {
          m.hidden = true;
        });
      });
    }
    document.querySelectorAll(".report-error-toggle").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const wrap = btn.closest(".report-error-wrap");
        const menu = wrap?.querySelector(".report-error-menu");
        document.querySelectorAll(".report-error-menu").forEach((m) => {
          if (m !== menu) m.hidden = true;
        });
        if (menu) menu.hidden = !menu.hidden;
      });
    });
    document.querySelectorAll(".report-error-opt").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const wrap = btn.closest(".report-error-wrap");
        if (!wrap) return;
        sendErrorReport({
          area: wrap.getAttribute("data-report-area"),
          id: wrap.getAttribute("data-report-id"),
          title: wrap.getAttribute("data-report-title"),
          type: btn.getAttribute("data-report-type"),
          extra: wrap.getAttribute("data-report-extra") || "",
        });
        const menu = wrap.querySelector(".report-error-menu");
        if (menu) menu.hidden = true;
      });
    });
  }

  function renderContato() {
    const email = contactEmail();
    return `
      <div class="page-head">
        <h1>Fale Conosco</h1>
        <p>Envie sugestão, crítica ou elogio sobre o NaIntegra Lex.</p>
      </div>
      <div class="contact-card">
        <form id="contact-form" class="contact-form">
          <label>
            Tipo de mensagem
            <select name="tipo" required>
              <option value="Sugestão">Sugestão</option>
              <option value="Crítica">Crítica</option>
              <option value="Elogio">Elogio</option>
            </select>
          </label>
          <label>
            Seu nome <span class="optional">(opcional)</span>
            <input type="text" name="nome" autocomplete="name" placeholder="Como podemos te chamar?" />
          </label>
          <label>
            Seu e-mail <span class="optional">(opcional, para resposta)</span>
            <input type="email" name="email" autocomplete="email" placeholder="seu@email.com" />
          </label>
          <label>
            Mensagem
            <textarea name="mensagem" rows="7" required placeholder="Conte-nos sua sugestão, crítica ou elogio…"></textarea>
          </label>
          <button type="submit" class="btn primary contact-submit">Enviar e-mail</button>
        </form>
        <p class="contact-alt">
          Também pode escrever diretamente para
          <a href="mailto:${esc(email)}">${esc(email)}</a>
        </p>
      </div>`;
  }

  function bindContactForm() {
    const form = document.getElementById("contact-form");
    if (!form) return;
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const tipo = String(fd.get("tipo") || "Contato");
      const nome = String(fd.get("nome") || "").trim();
      const replyEmail = String(fd.get("email") || "").trim();
      const mensagem = String(fd.get("mensagem") || "").trim();
      if (!mensagem) return;

      const subject = encodeURIComponent(`NaIntegra Lex — ${tipo}`);
      let body = `Tipo: ${tipo}\n`;
      if (nome) body += `Nome: ${nome}\n`;
      if (replyEmail) body += `E-mail para resposta: ${replyEmail}\n`;
      body += `\n${mensagem}`;
      body += `\n\n---\nEnviado via NaIntegra Lex\n${location.href}`;

      const mail = contactEmail();
      const mailto = `mailto:${mail}?subject=${subject}&body=${encodeURIComponent(body)}`;
      window.location.href = mailto;
    });
  }

  function bindHome() {
    document.querySelectorAll("[data-go]").forEach((el) => {
      el.addEventListener("click", () => {
        location.hash = `#/${el.getAttribute("data-go")}`;
      });
    });
  }

  function bindFlashcardsList() {
    document.querySelectorAll("[data-deck]").forEach((el) => {
      el.addEventListener("click", () => {
        state.flashSession = { idx: 0, flipped: false, stats: { err: 0, mid: 0, ok: 0 } };
        location.hash = `#/flashcards/${el.getAttribute("data-deck")}`;
      });
    });
  }

  function bindFlashSession(slug) {
    const card = document.getElementById("flash-card");
    if (card) {
      card.addEventListener("click", () => {
        if (!state.flashSession.flipped) {
          state.flashSession.flipped = true;
          render();
        }
      });
    }
    document.querySelectorAll("[data-rate]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const rate = btn.getAttribute("data-rate");
        scheduleFlash(slug, state.flashSession.idx, rate === "err" ? "err" : rate === "mid" ? "mid" : "ok");
        state.flashSession.stats[rate === "err" ? "err" : rate === "mid" ? "mid" : "ok"]++;
        state.flashSession.idx++;
        state.flashSession.flipped = false;
        render();
      });
    });
  }

  function bindLeiSecaList() {
    document.querySelectorAll("[data-law]").forEach((el) => {
      el.addEventListener("click", () => {
        location.hash = docHash("lei-seca", el.getAttribute("data-law"));
      });
    });
  }

  function bindReader(docId, articles, docType) {
    const fontIdx = () => loadJson(LS.fontSize, 2);
    const studyType = docType || "legislacao";

    document.getElementById("font-down")?.addEventListener("click", () => {
      const i = Math.max(0, fontIdx() - 1);
      saveJson(LS.fontSize, i);
      render();
    });
    document.getElementById("font-up")?.addEventListener("click", () => {
      const i = Math.min(FONT_SIZES.length - 1, fontIdx() + 1);
      saveJson(LS.fontSize, i);
      render();
    });

    document.querySelectorAll(".pill[data-art]").forEach((p) => {
      p.addEventListener("click", () => {
        const i = +p.getAttribute("data-art");
        document.getElementById(`art-${i}`)?.scrollIntoView({ behavior: "smooth" });
        if (!state.reader) state.reader = {};
        state.reader.activeArt = i;
      });
    });

    document.getElementById("mark-read")?.addEventListener("click", () => {
      const prog = readingProgress(docId);
      const ids = [...new Set([...prog.read, state.reader?.activeArt ?? 0])];
      setReadingProgress(docId, ids, articles.length);
      renderRecentReads();
      render();
    });

    document.querySelectorAll(".article-text").forEach((block) => {
      block.addEventListener("mouseup", () => {
        const sel = window.getSelection();
        if (!sel || sel.isCollapsed) return;
        const host = block.closest("[data-art-id]");
        if (!host) return;
        const toolbar = document.getElementById("highlight-toolbar");
        toolbar.classList.add("visible");
        toolbar.dataset.artId = host.getAttribute("data-art-id");
        toolbar.dataset.docId = docId;
        toolbar.dataset.docType = studyType;
      });
    });

    bindBlockNotes();
    bindTts(docId, articles);
  }

  function bindBlockNotes() {
    document.querySelectorAll("[data-note-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const wrap = btn.closest("[data-note-wrap]");
        const panel = wrap?.querySelector(".block-note-panel");
        if (panel) panel.hidden = !panel.hidden;
      });
    });

    const saveNote = (ta) => {
      const docId = ta.getAttribute("data-note-doc");
      const blockKey = ta.getAttribute("data-note-input");
      const docType = ta.getAttribute("data-note-type") || "legislacao";
      setNote(docId, blockKey, ta.value.trim(), docType);
      const btn = ta.closest(".block-note, .flash-note-wrap")?.querySelector("[data-note-toggle]");
      if (btn) btn.classList.toggle("has-note", Boolean(ta.value.trim()));
    };

    document.querySelectorAll("[data-note-input]").forEach((ta) => {
      let timer;
      ta.addEventListener("input", () => {
        clearTimeout(timer);
        timer = setTimeout(() => saveNote(ta), 500);
      });
      ta.addEventListener("blur", () => saveNote(ta));
    });
  }

  function bindHighlightToolbar() {
    const toolbar = document.getElementById("highlight-toolbar");
    if (!toolbar || toolbar.dataset.bound) return;
    toolbar.dataset.bound = "1";
    toolbar.querySelectorAll(".hl-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const sel = window.getSelection();
        if (!sel || sel.isCollapsed) return;
        const color = btn.getAttribute("data-color");
        const range = sel.getRangeAt(0);
        const mark = document.createElement("mark");
        mark.className = `hl-${color}`;
        try {
          range.surroundContents(mark);
        } catch {
          mark.appendChild(range.extractContents());
          range.insertNode(mark);
        }
        const artId = toolbar.dataset.artId;
        const docId = toolbar.dataset.docId;
        const docType = toolbar.dataset.docType || "legislacao";
        const block = document.querySelector(`#art-${artId} .article-text`);
        if (block) setHighlight(docId, artId, block.innerHTML, docType);
        toolbar.classList.remove("visible");
        sel.removeAllRanges();
      });
    });
    document.getElementById("hl-note-btn")?.addEventListener("click", () => {
      const artId = toolbar.dataset.artId;
      const wrap = document.querySelector(`#art-${artId} [data-note-wrap]`);
      const panel = wrap?.querySelector(".block-note-panel");
      const input = wrap?.querySelector("[data-note-input]");
      toolbar.classList.remove("visible");
      if (panel) {
        panel.hidden = false;
        input?.focus();
      }
    });
  }

  function bindTts(docId, articles) {
    if (!state.reader) state.reader = { activeArt: 0, narrating: false, speed: 1 };

    const synth = window.speechSynthesis;
    let utter = null;

    function speakArt(i) {
      synth.cancel();
      state.reader.activeArt = i;
      const text = articles[i]?.text;
      if (!text) return;
      utter = new SpeechSynthesisUtterance(text);
      utter.lang = "pt-BR";
      utter.rate = state.reader.speed || 1;
      utter.onend = () => {
        if (state.reader.narrating && i + 1 < articles.length) speakArt(i + 1);
        else {
          state.reader.narrating = false;
          render();
        }
      };
      synth.speak(utter);
      render();
    }

    document.getElementById("tts-toggle")?.addEventListener("click", () => {
      if (state.reader.narrating) {
        synth.cancel();
        state.reader.narrating = false;
      } else {
        state.reader.narrating = true;
        speakArt(state.reader.activeArt || 0);
      }
      render();
    });

    document.getElementById("tts-prev")?.addEventListener("click", () => {
      const i = Math.max(0, (state.reader.activeArt || 0) - 1);
      if (state.reader.narrating) speakArt(i);
      else state.reader.activeArt = i;
      render();
    });

    document.getElementById("tts-next")?.addEventListener("click", () => {
      const i = Math.min(articles.length - 1, (state.reader.activeArt || 0) + 1);
      if (state.reader.narrating) speakArt(i);
      else state.reader.activeArt = i;
      render();
    });

    document.querySelectorAll("[data-speed]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.reader.speed = parseFloat(btn.getAttribute("data-speed"));
        render();
      });
    });
  }

  function bindJuris() {
    document.querySelectorAll("[data-juris-open]").forEach((el) => {
      el.addEventListener("click", (e) => {
        if (e.target.closest("[data-studied]")) return;
        location.hash = docHash("jurisprudencia", el.getAttribute("data-juris-open"));
      });
    });
    document.querySelectorAll("[data-tribunal]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.jurisFilter = { ...(state.jurisFilter || {}), tribunal: btn.getAttribute("data-tribunal") };
        render();
      });
    });
    document.querySelectorAll("[data-tipo]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.jurisFilter = { ...(state.jurisFilter || {}), tipo: btn.getAttribute("data-tipo") };
        render();
      });
    });
    document.querySelectorAll("[data-studied]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleStudied(btn.getAttribute("data-studied"));
        renderRecentReads();
        render();
      });
    });
  }

  function bindQuestoes() {
    document.querySelectorAll("[data-banca]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.qFilter = { ...(state.qFilter || {}), banca: btn.getAttribute("data-banca") };
        state.questionsPage = 1;
        render();
      });
    });
    document.querySelectorAll("[data-q-page]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const dir = btn.getAttribute("data-q-page");
        if (dir === "prev" && state.questionsPage > 1) state.questionsPage--;
        if (dir === "next") state.questionsPage++;
        render();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    });
    document.querySelectorAll(".q-alt:not([disabled])").forEach((btn) => {
      btn.addEventListener("click", () => {
        const qid = btn.getAttribute("data-q-id");
        const key = btn.getAttribute("data-alt-key");
        const qa = qAnswerState(qid);
        if (qa.revealed) return;
        qa.pick = key;
        render();
      });
    });
    document.querySelectorAll("[data-q-check]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const qid = btn.getAttribute("data-q-check");
        const qa = qAnswerState(qid);
        if (!qa.pick || qa.revealed) return;
        qa.revealed = true;
        render();
        document.querySelector(`[id="gab-${CSS.escape(qid)}"]`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      });
    });
    document.querySelectorAll("[data-q-reveal]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const qid = btn.getAttribute("data-q-reveal");
        qAnswerState(qid).revealed = true;
        render();
      });
    });
    const qId = state.route.sub;
    if (qId) {
      const card =
        document.querySelector(`[data-q="${CSS.escape(qId)}"]`) ||
        [...document.querySelectorAll("[data-q]")].find((el) => el.getAttribute("data-q") === qId);
      card?.scrollIntoView({ behavior: "smooth", block: "center" });
      card?.classList.add("search-highlight");
    }
  }

  async function openReader(docId, backRoute) {
    const main = document.getElementById("main");
    const app = document.getElementById("app");
    main.classList.remove("with-panel");
    app?.classList.remove("with-panel");

    const doc = findDocument(docId);
    if (!doc) {
      setAppHtml(`<div class="empty">Documento não encontrado.</div>`);
      return;
    }
    trackRecentRead(doc, backRoute);

    setAppHtml(renderReader(docId, backRoute));

    if (!doc.body) {
      try {
        await window.LexData.loadDocumentBody(doc);
      } catch (err) {
        console.error(err);
        const detail = err?.message ? `<p class="meta-row"><small>${esc(String(err.message))}</small></p>` : "";
        setAppHtml(`<div class="empty">Não foi possível carregar este documento.${detail}<p style="margin-top:0.75rem"><a href="#/${esc(backRoute || "jurisprudencia")}" class="btn">← Voltar</a></p></div>`);
        return;
      }
    }

    const reader = renderReader(docId, backRoute);
    if (typeof reader === "string") {
      setAppHtml(reader);
      return;
    }
    setAppHtml(reader.html);
    if (doc.formatted?.mode === "legislacao") app?.classList.add("with-panel");
    bindReader(docId, reader.articles, docStudyType(doc));
    bindHighlightToolbar();
    bindBlockNotes();
    bindReportError();
  }

  function render() {
    const main = document.getElementById("main");
    const app = document.getElementById("app");
    main.classList.remove("with-panel");
    app?.classList.remove("with-panel");
    setActiveNav();
    renderRecentReads();

    const r = state.route;

    if (r.path === "assinatura") {
      const planId = r.plan || "lex-mensal";
      window.LexSubscription?.renderAssinaturaPage(planId).then((h) => {
        setAppHtml(h);
        window.LexSubscription?.bindAssinaturaPage(planId);
      });
      setAppHtml(`<div class="loading">Carregando checkout…</div>`);
      return;
    }

    if (!state.subscriptionActive && state.subscriptionChecked && !isPublicRoute(r.path)) {
      location.hash = "#/assinatura";
      return;
    }

    let html = "";

    if (r.path === "home" || !r.path) html = renderHome();
    else if (r.path === "flashcards") {
      if (r.id) html = renderFlashSession(r.id);
      else html = renderFlashcardsList();
    } else if (r.path === "lei-seca") {
      if (r.id) {
        openReader(r.id, "lei-seca");
        return;
      }
      html = renderLeiSecaList();
    } else if (r.path === "jurisprudencia") {
      if (r.id) {
        openReader(r.id, "jurisprudencia");
        return;
      }
      html = renderJurisprudencia();
    } else if (r.path === "questoes") {
      if (!state.questionsLoaded && !state.questionsLoading) ensureQuestionsLoaded();
      html = renderQuestoes();
    } else if (r.path === "contato") html = renderContato();
    else html = renderHome();

    setAppHtml(html);

    bindHome();
    if (r.path === "home" || !r.path) {
      const hint = document.getElementById("sync-hint");
      if (hint) hint.hidden = Boolean(window.LexStore?.isLoggedIn?.());
    }
    bindFlashcardsList();
    if (r.path === "flashcards" && r.id) {
      bindFlashSession(r.id);
      bindBlockNotes();
    }
    bindLeiSecaList();
    bindJuris();
    bindQuestoes();
    bindContactForm();
    bindReportError();
    bindHighlightToolbar();
    bindBlockNotes();
    if (r.path === "flashcards" && !r.id) bindPageSectionSearch("flashcards");
    else if (r.path === "lei-seca" && !r.id) bindPageSectionSearch("lei-seca");
    else if (r.path === "jurisprudencia" && !r.id) bindPageSectionSearch("jurisprudencia");
    else if (r.path === "questoes") bindPageSectionSearch("questoes");
  }

  async function init() {
    if (location.protocol === "file:") {
      document.getElementById("app").innerHTML =
        `<div class="empty">Abra o Lex via servidor HTTP: <code>python3 preview/serve_preview.py</code> e acesse <code>/web/lex/index.html</code>.</div>`;
      return;
    }

    if (window.LexAuthUI) {
      await window.LexAuthUI.init(async (session) => {
        if (window.LexStore) await window.LexStore.setSession(session);
        if (window.LexSubscription) window.LexSubscription.invalidateCache();
        const hint = document.getElementById("sync-hint");
        if (hint) hint.hidden = Boolean(session?.user);
        await ensureSubscriptionGate();
        if (session?.user && state.subscriptionActive && window.LexProtect) {
          window.LexProtect.init();
        }
        render();
      });
    }

    window.LexSubscription?.renderSidebarUpdate?.();

    await ensureSubscriptionGate();
    if (state.subscriptionActive && window.LexProtect) {
      window.LexProtect.init();
    }

    const r0 = state.route;
    if (!state.subscriptionActive && !isPublicRoute(r0.path)) {
      location.hash = "#/assinatura";
    }

    try {
      const [documents, decks, qCount] = await Promise.all([
        window.LexData.loadDocuments(),
        window.LexData.loadFlashcardDecks(),
        window.LexData.loadQuestionsCount?.() ?? Promise.resolve(null),
      ]);
      state.documents = documents;
      state.decks = decks;
      if (qCount != null) state.questionsCount = qCount;
      if (window.LexSearch) {
        window.LexSearch.init();
        window.LexSearch.refresh(documents, decks);
      }
    } catch (err) {
      console.error(err);
      document.getElementById("app").innerHTML =
        `<div class="empty">Não foi possível carregar o conteúdo. Verifique sua conexão e tente novamente.</div>`;
      return;
    }
    if (window.__LEX_DATA_SOURCE === "fallback") {
      const app = document.getElementById("app");
      if (app) {
        app.insertAdjacentHTML(
          "afterbegin",
          `<div class="banner-warn" style="background:#fef3c7;border:1px solid #f59e0b;padding:0.75rem 1rem;margin-bottom:1rem;border-radius:8px;font-size:0.9rem">
            Modo demonstração (offline). Abra via <code>python3 preview/serve_preview.py</code> e acesse <code>/web/lex/index.html</code> para ver todo o acervo do Supabase.
          </div>`
        );
      }
    }
    render();
  }

  window.addEventListener("hashchange", () => {
    state.route = parseRoute();
    render();
  });

  init();
})();
