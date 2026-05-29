/** NaIntegra Lex — SPA (naintegracursos.com.br/lex) */
(function () {
  const LS = window.LexStore?.LS || {
    highlights: "lex_highlights",
    notes: "lex_notes",
    progress: "lex_reading_progress",
    studied: "lex_studied_items",
    flashReviews: "lex_flashcard_reviews",
    questionAnswers: "lex_question_answers",
    fontSize: "lex_font_size",
    ttsVoice: "lex_tts_voice",
    recentReads: "lex_recent_reads",
  };

  const TTS_VOICE_PRESETS = [
    { id: "luciana", label: "Luciana", gender: "f", match: (v) => /luciana/i.test(v.name) },
    { id: "joana", label: "Joana", gender: "f", match: (v) => /\bjoana\b/i.test(v.name) },
    { id: "felipe", label: "Felipe", gender: "m", match: (v) => /felipe/i.test(v.name) },
    { id: "joaquim", label: "Joaquim", gender: "m", match: (v) => /joaquim/i.test(v.name) },
    { id: "joao", label: "João", gender: "m", match: (v) => /\bjo[aã]o\b/i.test(v.name) },
    { id: "francisca", label: "Francisca", gender: "f", match: (v) => /francisca/i.test(v.name) },
    { id: "maria", label: "Maria", gender: "f", match: (v) => /\bmaria\b/i.test(v.name) },
    { id: "daniel", label: "Daniel", gender: "m", match: (v) => /daniel/i.test(v.name) },
    { id: "antonio", label: "Antônio", gender: "m", match: (v) => /antonio|antônio/i.test(v.name) },
    { id: "fernanda", label: "Fernanda", gender: "f", match: (v) => /fernanda/i.test(v.name) },
    { id: "vitoria", label: "Vitória", gender: "f", match: (v) => /vit[oó]ria/i.test(v.name) },
    { id: "leticia", label: "Letícia", gender: "f", match: (v) => /let[ií]cia/i.test(v.name) },
    { id: "jorge", label: "Jorge", gender: "m", match: (v) => /jorge/i.test(v.name) },
    { id: "pedro", label: "Pedro", gender: "m", match: (v) => /pedro/i.test(v.name) },
    { id: "paulo", label: "Paulo", gender: "m", match: (v) => /\bpaulo\b/i.test(v.name) },
    { id: "raquel", label: "Raquel", gender: "f", match: (v) => /raquel/i.test(v.name) },
    { id: "duarte", label: "Duarte", gender: "m", match: (v) => /duarte/i.test(v.name) },
    { id: "ricardo", label: "Ricardo", gender: "m", match: (v) => /ricardo/i.test(v.name) },
    { id: "tiago", label: "Tiago", gender: "m", match: (v) => /tiago/i.test(v.name) },
    { id: "camila", label: "Camila", gender: "f", match: (v) => /camila/i.test(v.name) },
    { id: "google_pt_br_f", label: "Google PT-BR", gender: "f", match: (v) => /google.*portugu[eê]s.*brasil|google.*brazilian.*portuguese/i.test(`${v.name} ${v.voiceURI}`) && /female|feminino/i.test(`${v.name} ${v.voiceURI}`) },
    { id: "google_pt_br_m", label: "Google PT-BR", gender: "m", match: (v) => /google.*portugu[eê]s.*brasil|google.*brazilian.*portuguese/i.test(`${v.name} ${v.voiceURI}`) && /male|masculino/i.test(`${v.name} ${v.voiceURI}`) },
    { id: "google_pt_br", label: "Google português", gender: "n", match: (v) => /google.*portugu[eê]s|google.*brazilian/i.test(`${v.name} ${v.voiceURI}`) },
  ];

  const TTS_VIRTUAL_MALE = [
    { id: "vm_felipe", label: "Felipe", pitch: 0.78 },
    { id: "vm_daniel", label: "Daniel", pitch: 0.8 },
    { id: "vm_jorge", label: "Jorge", pitch: 0.76 },
    { id: "vm_pedro", label: "Pedro", pitch: 0.82 },
    { id: "vm_antonio", label: "Antônio", pitch: 0.79 },
    { id: "vm_paulo", label: "Paulo", pitch: 0.77 },
  ];

  const store = () => window.LexStore;

  const FONT_SIZES = [11, 13, 15, 17, 19];
  const LEI_SECOES = [
    "Constituição e Adm.",
    "Penal e Processual",
    "Civil e Trabalho",
    "Legislação Especial",
  ];

  /** Disciplinas básicas do acervo NaIntegra Cursos (questões_banco). */
  const DOUTRINA_DISCIPLINAS = [
    {
      slug: "portugues",
      label: "Português",
      abbr: "PT",
      desc: "Gramática, concordância e interpretação de textos.",
      materias: ["Português", "Língua Portuguesa"],
    },
    {
      slug: "raciocinio-logico",
      label: "Raciocínio Lógico",
      abbr: "RL",
      desc: "Proposições, conjuntos e argumentação.",
      materias: ["Raciocínio Lógico"],
    },
    {
      slug: "informatica",
      label: "Informática",
      abbr: "IF",
      desc: "Sistemas operacionais, redes e segurança da informação.",
      materias: ["Informática"],
    },
  ];

  let state = {
    documents: [],
    decks: [],
    route: parseRoute(),
    reader: null,
    flashSession: null,
    tts: null,
    ttsVoiceOptions: [],
    questionsLoaded: false,
    questionsLoading: false,
    questionsCount: null,
    questionsPage: 1,
    questionsPageSize: 50,
    doutrinaPage: 1,
    doutrinaPageSize: 50,
    doutrinaFilter: { banca: "all", assunto: "all", result: "all" },
    decksLoading: false,
    decksHydrating: false,
    flashManageEdit: null,
    documentsEnriching: false,
    studyPlanCareer: null,
    studyPlanUf: null,
    studyPlanExpandedDay: null,
    studyPlansModuleLoading: false,
    qAnswers: {},
    qStatsPeriod: "7d",
    questaoPageIds: [],
    questaoCommentsLoading: false,
    questaoCommentEdit: null,
    subscriptionActive: false,
    subscriptionChecked: false,
    currentUser: null,
  };

  function isLoggedIn() {
    return Boolean(state.currentUser);
  }

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

  function inferVoiceGender(voice) {
    const n = `${voice.name} ${voice.voiceURI}`.toLowerCase();
    if (/female|feminino|mulher|woman|luciana|maria|fernanda|francisca|raquel|vit[oó]ria|camila|monica|yara|helo[ií]sa|joana|leticia|let[ií]cia|moira|fiona|karen|samantha/i.test(n)) {
      return "f";
    }
    if (/male|masculino|homem|man|felipe|daniel|jorge|pedro|paulo|marcos|antonio|antônio|tiago|duarte|thomaz|ricardo|joaquim|jo[aã]o|fred|eddy|gordon|aaron|nathan/i.test(n)) {
      return "m";
    }
    return "n";
  }

  function isPortugueseVoice(voice) {
    const lang = String(voice.lang || "").toLowerCase();
    const name = `${voice.name} ${voice.voiceURI}`.toLowerCase();
    if (/^pt/i.test(lang)) return true;
    if (/portugu[eê]s|brazil|brasil|pt[-_]?br|pt[-_]?pt/i.test(name)) return true;
    return false;
  }

  function voiceGenderLabel(gender) {
    if (gender === "f") return "feminina";
    if (gender === "m") return "masculina";
    return "neutra";
  }

  function cleanVoiceName(name) {
    return String(name || "")
      .replace(/Microsoft|Google|Apple|SAPI|Online|Natural|Neural|Desktop|Mobile|\(Natural\)|\(Enhanced\)/gi, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function pushVoiceOption(options, used, entry) {
    const key = entry.voiceURI || entry.id;
    if (!key || used.has(key)) return;
    used.add(key);
    options.push(entry);
  }

  function appendVirtualMaleVoices(options) {
    const maleCount = options.filter((o) => o.gender === "m").length;
    if (maleCount >= 4) return options;
    const base =
      options.find((o) => o.voice && o.gender === "f" && /luciana|maria|francisca|fernanda/i.test(o.label)) ||
      options.find((o) => o.voice && o.gender === "f") ||
      options.find((o) => o.voice);
    if (!base?.voice) return options;
    const out = [...options];
    for (const preset of TTS_VIRTUAL_MALE) {
      if (out.some((o) => o.id === preset.id)) continue;
      out.push({
        id: preset.id,
        label: `${preset.label} (masculina, tom ajustado)`,
        voiceURI: `${base.voiceURI}::${preset.id}`,
        voice: base.voice,
        gender: "m",
        pitch: preset.pitch,
        virtual: true,
      });
    }
    return out;
  }

  function buildTtsVoiceOptions() {
    const synth = window.speechSynthesis;
    if (!synth) return [];
    const system = synth.getVoices().filter(isPortugueseVoice);
    const used = new Set();
    const options = [];

    for (const preset of TTS_VOICE_PRESETS) {
      const voice = system.find((v) => !used.has(v.voiceURI) && preset.match(v));
      if (!voice) continue;
      pushVoiceOption(options, used, {
        id: preset.id,
        label: `${preset.label} (${voiceGenderLabel(preset.gender === "n" ? inferVoiceGender(voice) : preset.gender)})`,
        voiceURI: voice.voiceURI,
        voice,
        gender: preset.gender === "n" ? inferVoiceGender(voice) : preset.gender,
      });
    }

    for (const voice of system) {
      if (used.has(voice.voiceURI)) continue;
      const gender = inferVoiceGender(voice);
      pushVoiceOption(options, used, {
        id: voice.voiceURI,
        label: `${cleanVoiceName(voice.name)} (${voiceGenderLabel(gender)})`,
        voiceURI: voice.voiceURI,
        voice,
        gender,
      });
    }

    return appendVirtualMaleVoices(options);
  }

  function refreshTtsVoiceOptions() {
    state.ttsVoiceOptions = buildTtsVoiceOptions();
    const saved = loadJson(LS.ttsVoice, null);
    if (state.ttsVoiceOptions.length && (!saved || !state.ttsVoiceOptions.some((o) => o.id === saved))) {
      saveJson(LS.ttsVoice, state.ttsVoiceOptions[0].id);
    }
  }

  function initTtsVoices() {
    if (!window.speechSynthesis) return;
    refreshTtsVoiceOptions();
    window.speechSynthesis.addEventListener("voiceschanged", () => {
      refreshTtsVoiceOptions();
      if (state.route.id && (state.route.path === "lei-seca" || state.route.path === "jurisprudencia")) render();
    });
    [400, 1200, 2500].forEach((ms) => setTimeout(refreshTtsVoiceOptions, ms));
  }

  function selectedTtsVoiceId() {
    const saved = state.reader?.voiceId || loadJson(LS.ttsVoice, null);
    if (saved && state.ttsVoiceOptions.some((o) => o.id === saved)) return saved;
    const preferred = state.ttsVoiceOptions.find((o) => o.gender === "f" && !o.virtual)?.id;
    return preferred || state.ttsVoiceOptions[0]?.id || "";
  }

  function resolveTtsVoiceOption(id) {
    return state.ttsVoiceOptions.find((o) => o.id === id) || null;
  }

  function resolveTtsVoice(id) {
    return resolveTtsVoiceOption(id)?.voice || null;
  }

  function renderTtsVoiceSelect(selectId, selectedId) {
    const selected = selectedId || selectedTtsVoiceId();
    const options = state.ttsVoiceOptions;
    if (!options.length) {
      return `<select id="${esc(selectId)}" class="tts-voice-select" title="Voz da narração" disabled><option>Carregando vozes…</option></select>`;
    }
    const groups = [
      { label: "Femininas", items: options.filter((o) => o.gender === "f" && !o.virtual) },
      { label: "Masculinas", items: options.filter((o) => o.gender === "m" && !o.virtual) },
      { label: "Masculinas (tom ajustado)", items: options.filter((o) => o.gender === "m" && o.virtual) },
      { label: "Outras", items: options.filter((o) => o.gender === "n") },
    ].filter((g) => g.items.length);
    const body = groups.length
      ? groups
          .map(
            (g) =>
              `<optgroup label="${esc(g.label)}">${g.items
                .map(
                  (o) =>
                    `<option value="${esc(o.id)}"${o.id === selected ? " selected" : ""}>${esc(o.label)}</option>`
                )
                .join("")}</optgroup>`
          )
          .join("")
      : options
          .map(
            (o) =>
              `<option value="${esc(o.id)}"${o.id === selected ? " selected" : ""}>${esc(o.label)}</option>`
          )
          .join("");
    return `<select id="${esc(selectId)}" class="tts-voice-select" title="Voz da narração">${body}</select>`;
  }

  function bindTtsVoiceSelects(onChange) {
    document.querySelectorAll("#tts-voice, #tts-voice-header").forEach((sel) => {
      sel.addEventListener("change", () => {
        const id = sel.value;
        if (!state.reader) state.reader = { activeArt: 0, narrating: false, speed: 1 };
        state.reader.voiceId = id;
        saveJson(LS.ttsVoice, id);
        document.querySelectorAll("#tts-voice, #tts-voice-header").forEach((other) => {
          if (other !== sel) other.value = id;
        });
        onChange?.();
      });
    });
  }

  function docStudyType(doc) {
    if (!doc) return "legislacao";
    if (doc.doc_type === "jurisprudencia" || doc.doc_type === "sumula") return "jurisprudencia";
    return "legislacao";
  }

  function readerStorageId(docOrRouteId) {
    if (docOrRouteId && typeof docOrRouteId === "object") return progressDocKey(docOrRouteId);
    const doc = findDocument(docOrRouteId);
    return doc ? progressDocKey(doc) : docOrRouteId;
  }

  function isJurisStudyDoc(doc) {
    if (!doc) return false;
    const kind = docStudyType(doc);
    return kind === "jurisprudencia" || doc.doc_type === "sumula";
  }

  function narrationArticles(doc) {
    if (!doc) return [];
    if (doc.formatted?.mode === "juris" && doc.formatted.items?.length) {
      return doc.formatted.items.map((it, i) => ({
        id: i,
        label: it.numero || it.tipo || `Item ${i + 1}`,
        text: [it.ementa, it.tese, it.julgado].filter(Boolean).join("\n\n").trim() || it.ementa || "",
      }));
    }
    const arts = parseArticles(doc);
    if (arts.length) return arts;
    if (isJurisStudyDoc(doc) && doc.body?.trim()) {
      return [{ id: 0, label: doc.title || "Precedente", text: doc.body.trim() }];
    }
    return [];
  }

  function canNarrateDoc(doc, articles) {
    if (!articles.length) return false;
    if (doc.formatted?.mode === "legislacao" || doc.formatted?.mode === "juris") return true;
    return isJurisStudyDoc(doc) && Boolean(doc.body?.trim());
  }

  function highlightBlockKey(artId, part) {
    return part ? `${artId}.${part}` : String(artId);
  }

  function applyJurisItemHighlights(itemHtml, itemIdx, highlights) {
    const whole = highlights[itemIdx];
    if (whole && typeof whole === "string") return null;
    let html = itemHtml;
    for (const part of ["ementa", "tese", "julgado", "texto"]) {
      const saved = highlights[highlightBlockKey(itemIdx, part)];
      if (!saved) continue;
      const re = new RegExp(
        `(<p\\s+class="juris-section-text article-text"\\s+data-hl-part="${part}"[^>]*>)([\\s\\S]*?)(</p>)`
      );
      html = html.replace(re, `$1${saved}$3`);
    }
    return html;
  }

  function augmentJurisItemHtml(itemHtml, itemIdx, notes, storageId, studyType) {
    let html = itemHtml;
    let injected = false;
    for (const part of ["ementa", "tese", "julgado", "texto"]) {
      if (!html.includes(`data-hl-part="${part}"`)) continue;
      const noteKey = highlightBlockKey(itemIdx, part);
      const note = notes[noteKey] ?? (part === "ementa" ? notes[itemIdx] : "");
      const noteHtml = `<div class="juris-section-note">${renderBlockNote(storageId, noteKey, note, studyType)}</div>`;
      const re = new RegExp(
        `(<p\\s+class="juris-section-text article-text"\\s+data-hl-part="${part}"[^>]*>[\\s\\S]*?</p>\\s*)`,
        "i"
      );
      if (re.test(html)) {
        html = html.replace(re, `$1${noteHtml}`);
        injected = true;
      }
    }
    if (!injected) {
      html = html.replace(
        /<\/article>\s*$/,
        `${renderBlockNote(storageId, String(itemIdx), notes[itemIdx] || "", studyType)}</article>`
      );
    }
    return html;
  }

  function readerShowsNarrationPanel(doc) {
    if (!state.reader?.narrating || !doc) return false;
    return canNarrateDoc(doc, narrationArticles(doc));
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
    if (!path || path === "home") return true;
    const pub = window.LEX_CONFIG?.publicRoutes || ["assinatura", "contato", "auth"];
    return pub.includes(path) || path.startsWith("auth");
  }

  function isLandingRoute(path) {
    return !path || path === "home" || path === "precos";
  }

  function updatePublicLayout(path) {
    const publicLanding = !isLoggedIn() && isLandingRoute(path);
    document.body.classList.toggle("lex-public-mode", publicLanding);
  }

  function isLocalPreview() {
    const h = location.hostname;
    return h === "localhost" || h === "127.0.0.1" || h === "[::1]";
  }

  async function ensureSubscriptionGate() {
    if (isLocalPreview() || new URLSearchParams(location.search).get("promo") === "1") {
      state.subscriptionChecked = true;
      state.subscriptionActive = true;
      return true;
    }
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

  function progressDocKey(docOrId) {
    if (typeof docOrId === "string") {
      const doc = findDocument(docOrId);
      return doc ? readerRouteId(doc) : docOrId;
    }
    return readerRouteId(docOrId);
  }

  function isReaderRoute() {
    return Boolean(
      state.route.id && (state.route.path === "lei-seca" || state.route.path === "jurisprudencia")
    );
  }

  function renderAfterBackgroundUpdate() {
    refreshSearchIndex();
    renderRecentReads();
    if (isReaderRoute()) return;
    render();
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
    const key = progressDocKey(docId);
    if (store()) return store().readingProgress(key);
    return loadJson(LS.progress, {})[key] || { read: [], pct: 0 };
  }

  function setReadingProgress(docId, readIds, total) {
    const key = progressDocKey(docId);
    if (store()) store().setReadingProgress(key, readIds, total);
    else {
      const all = loadJson(LS.progress, {});
      all[key] = { read: readIds, pct: total ? Math.round((readIds.length / total) * 100) : 0 };
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
    const all = loadJson(LS.highlights, {});
    const type = docType || "legislacao";
    if (all[type]?.[docId]) return all[type][docId];
    return all[docId] || {};
  }

  function setHighlight(docId, artId, html, docType) {
    if (store()) store().setHighlight(docId, artId, html, docType);
    else {
      const type = docType || "legislacao";
      const all = loadJson(LS.highlights, {});
      if (!all[type]) all[type] = {};
      if (!all[type][docId]) all[type][docId] = {};
      all[type][docId][artId] = html;
      saveJson(LS.highlights, all);
    }
  }

  function getNotes(docId, docType) {
    if (store()) return store().getNotes(docId, docType);
    const all = loadJson(LS.notes, {});
    const type = docType || "legislacao";
    if (all[type]?.[docId]) return all[type][docId];
    return all[docId] || {};
  }

  function setNote(docId, blockKey, text, docType) {
    if (store()) store().setNote(docId, blockKey, text, docType);
    else {
      const type = docType || "legislacao";
      const all = loadJson(LS.notes, {});
      if (!all[type]) all[type] = {};
      if (!all[type][docId]) all[type][docId] = {};
      all[type][docId][blockKey] = text;
      saveJson(LS.notes, all);
    }
  }

  function renderBlockNote(docId, blockKey, note, docType, labels = {}) {
    const addLabel = labels.add || "＋ Anotar";
    const hasLabel = labels.has || "📝 Anotação";
    const placeholder = labels.placeholder || "Sua anotação…";
    const open = labels.open ?? Boolean(note);
    return `
      <div class="block-note" data-note-wrap="${esc(blockKey)}">
        <button type="button" class="block-note-toggle ${note ? "has-note" : ""}" data-note-toggle="${esc(blockKey)}" title="${esc(labels.title || "Anotação")}">
          ${note ? hasLabel : addLabel}
        </button>
        <div class="block-note-panel" ${open ? "" : "hidden"}>
          <textarea class="block-note-input" data-note-input="${esc(blockKey)}" data-note-doc="${esc(docId)}" data-note-type="${esc(docType)}" placeholder="${esc(placeholder)}">${esc(note || "")}</textarea>
        </div>
      </div>`;
  }

  function flashDueCount(deck) {
    const cards = deck.cards || [];
    const reviews = store()?.flashReviews() || loadJson(LS.flashReviews, {});
    const today = new Date().toISOString().slice(0, 10);
    return cards.filter((_, i) => {
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
      const p = readingProgress(progressDocKey(doc));
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
      rehydrateQAnswers();
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

  function renderDashboardHome() {
    const nLeg = byType("legislacao").length;
    const nJur = byType("jurisprudencia").length;
    const nDeck = state.decks.length;
    const nQ = questionsTotal();

    return `
      <section class="hero">
        <h1>Acervo jurídico</h1>
        <p>Lei seca, jurisprudência, flashcards e questões comentadas — com grifos, anotações, <strong>narração em áudio</strong> e progresso na nuvem. Material atualizado semanalmente!</p>
        <p class="sync-hint" id="sync-hint" hidden>Entre na sua conta para sincronizar grifos e anotações entre dispositivos.</p>
      </section>
      <div class="tiles">
        <button class="tile" data-go="flashcards">
          <span class="tile-abbr" aria-hidden="true">FC</span>
          <h2>Flashcards</h2>
          <p>${nDeck} disciplinas · revisão SM-2</p>
        </button>
        <button class="tile" data-go="lei-seca">
          <span class="tile-abbr" aria-hidden="true">LS</span>
          <h2>Lei Seca</h2>
          <p>${nLeg} leis · grifos e narração</p>
        </button>
        <button class="tile" data-go="jurisprudencia">
          <span class="tile-abbr" aria-hidden="true">JU</span>
          <h2>Jurisprudência</h2>
          <p>${nJur} súmulas e teses</p>
        </button>
        <button class="tile" data-go="questoes">
          <span class="tile-abbr" aria-hidden="true">QT</span>
          <h2>Questões</h2>
          <p>${nQ} questões · filtros por banca</p>
        </button>
        <button class="tile" data-go="doutrina">
          <span class="tile-abbr" aria-hidden="true">DO</span>
          <h2>Doutrina</h2>
          <p>Português, lógica e informática</p>
        </button>
        <button class="tile" data-go="plano-estudos">
          <span class="tile-abbr" aria-hidden="true">PE</span>
          <h2>Plano de estudos</h2>
          <p>Trilha por carreira · lei e juris</p>
        </button>
      </div>`;
  }

  function renderLandingPage(showAuthPanel) {
    const nLeg = byType("legislacao").length;
    const nJur = byType("jurisprudencia").length;
    const nQ = questionsTotal();
    const nFlash = state.decks.reduce(
      (sum, d) => sum + (window.LexData?.deckCardCount?.(d) ?? d.cards?.length ?? 0),
      0
    );

    const authAside = showAuthPanel
      ? `<aside class="landing-auth-aside"><div id="landing-auth-root"></div></aside>`
      : `<aside class="landing-auth-aside">
          <div class="landing-auth-panel landing-auth-panel--cta">
            <h2 class="landing-auth-title">Assine para acessar</h2>
            <p class="landing-auth-lead">Conta ativa — escolha um plano.</p>
            <a class="btn primary block" href="#/assinatura?plan=lex-anual">Anual · R$ 199,90</a>
            <a class="btn block" href="#/assinatura?plan=lex-mensal">Mensal · R$ 19,90</a>
          </div>
        </aside>`;

    return `
      <div class="lex-landing">
        <div class="landing-hero-grid">
          <section class="landing-intro">
            <h1>Legislação e jurisprudência para concursos</h1>
            <p class="landing-intro-lead">Lei seca, súmulas, flashcards e questões comentadas — com grifos, anotações e <strong>narração em áudio</strong>. Material atualizado semanalmente.</p>
            <article class="landing-audio-feature" aria-labelledby="landing-audio-title">
              <span class="landing-audio-icon" aria-hidden="true">🎧</span>
              <div class="landing-audio-copy">
                <h2 id="landing-audio-title">Ouça as leis na íntegra</h2>
                <p>Narração artigo a artigo, com controle de velocidade. Revise no trânsito, na academia ou antes de dormir — sem precisar olhar a tela.</p>
              </div>
            </article>
            <p class="landing-meta">${nLeg.toLocaleString("pt-BR")} leis · ${nJur.toLocaleString("pt-BR")} jurisprudências · ${nQ.toLocaleString("pt-BR")} questões · ${nFlash.toLocaleString("pt-BR")} flashcards</p>
            <div class="landing-plan-list" id="precos">
              <div class="landing-plan-item">
                <span class="landing-plan-copy"><strong>Mensal</strong> R$ 19,90/mês</span>
                <a class="btn sm" href="#/assinatura?plan=lex-mensal">Assinar</a>
              </div>
              <div class="landing-plan-item landing-plan-item--featured">
                <span class="landing-plan-copy"><strong>Anual</strong> R$ 199,90/ano</span>
                <a class="btn sm primary" href="#/assinatura?plan=lex-anual">Assinar</a>
              </div>
            </div>
          </section>
          ${authAside}
        </div>
      </div>`;
  }

  function renderHome() {
    if (isLoggedIn() && state.subscriptionActive) return renderDashboardHome();
    return renderLandingPage(!isLoggedIn());
  }

  function renderFlashcardsList() {
    if (state.decksLoading && !state.decks.length) {
      return `<div class="page-head"><h1>Flashcards</h1><p>Carregando decks…</p></div><div class="empty">Aguarde um instante.</div>`;
    }
    const customDecks = state.decks.filter((d) => d.custom);
    const serverDecks = state.decks.filter((d) => !d.custom);
    const ss = SS();
    const deckCard = (d) => {
      const due = flashDueCount(d);
      const searchText = ss ? ss.deckText(d) : d.name;
      const manage =
        d.custom
          ? `<button type="button" class="btn btn-sm flash-deck-manage" data-manage-deck="${esc(d.slug)}" title="Gerenciar deck">Gerenciar</button>`
          : "";
      return `
            <article class="deck-card ${d.custom ? "deck-card-custom" : ""}" data-deck="${esc(d.slug)}" data-search-text="${esc(searchText)}">
              <span class="tag">${esc(d.category)}${d.custom ? " · Meu" : ""}</span>
              <h3>${esc(d.name)}</h3>
              <p>${window.LexData?.deckCardCount?.(d) ?? (d.cards || []).length} cards · <strong>${due} vencem hoje</strong></p>
              ${manage}
            </article>`;
    };

    const syncHint = window.LexStore?.isLoggedIn?.()
      ? `<p class="flash-sync-hint">Seus decks personalizados são sincronizados na nuvem.</p>`
      : `<p class="flash-sync-hint">Faça login para sincronizar seus decks entre dispositivos.</p>`;

    if (!state.decks.length) {
      return `
        <div class="page-head flash-page-head">
          <div>
            <h1>Flashcards</h1>
            <p>Crie seus próprios decks ou importe de CSV, JSON, Anki e outros formatos.</p>
            ${syncHint}
          </div>
          <div class="flash-page-actions">
            <a class="btn primary" href="#/flashcards/criar">＋ Novo deck</a>
          </div>
        </div>
        <div class="empty">Nenhum deck disponível. <a href="#/flashcards/criar">Crie o primeiro</a>.</div>`;
    }

    return `
      <div class="page-head flash-page-head">
        <div>
          <h1>Flashcards</h1>
          <p>Escolha a disciplina para revisar ou crie/importe seus próprios decks.</p>
          ${syncHint}
        </div>
        <div class="flash-page-actions">
          <a class="btn primary" href="#/flashcards/criar">＋ Novo deck</a>
        </div>
      </div>
      ${sectionSearchBar("flashcards", "Buscar deck ou tema (ex.: constitucional, penal)…")}
      <div class="section-list-scope" data-section-scope="flashcards">
        ${
          customDecks.length
            ? `<section class="flash-deck-section" data-search-group>
          <h2 class="flash-section-title">Meus decks</h2>
          <div class="card-list">${customDecks.map(deckCard).join("")}</div>
        </section>`
            : ""
        }
        ${
          serverDecks.length
            ? `<section class="flash-deck-section" data-search-group>
          <h2 class="flash-section-title">${customDecks.length ? "Acervo NaIntegra" : "Decks"}</h2>
          <div class="card-list">${serverDecks.map(deckCard).join("")}</div>
        </section>`
            : ""
        }
        <div class="empty section-search-empty" data-section-empty hidden>Nenhum deck ou card para este tema.</div>
      </div>`;
  }

  function renderFlashCreate() {
    const hints = (window.LexFlashcardsUser?.FORMAT_HINTS || []).map((h) => `<li>${esc(h)}</li>`).join("");
    return `
      <div class="page-head">
        <h1>Novo deck</h1>
        <p>Crie manualmente ou importe cards de arquivo ou texto colado.</p>
      </div>
      <div class="flash-editor">
        <form id="flash-create-form" class="flash-form">
          <label class="flash-field">
            <span>Nome do deck</span>
            <input type="text" name="name" required maxlength="120" placeholder="Ex.: CF — princípios fundamentais" />
          </label>
          <label class="flash-field">
            <span>Categoria</span>
            <input type="text" name="category" maxlength="80" placeholder="Meus decks" value="Meus decks" />
          </label>

          <div class="flash-import-panel">
            <h3>Importar cards</h3>
            <p class="flash-import-lead">CSV, JSON, JSONL, TSV (Anki), texto com <code>::</code> ou <code>|</code>, ou blocos separados por linha em branco.</p>
            <label class="flash-field">
              <span>Arquivo</span>
              <input type="file" id="flash-import-file" accept=".csv,.json,.jsonl,.tsv,.txt,.ndjson,text/plain,text/csv,application/json" />
            </label>
            <label class="flash-field">
              <span>Ou cole o conteúdo</span>
              <textarea id="flash-import-text" rows="8" placeholder="Cole aqui o conteúdo exportado…"></textarea>
            </label>
            <p class="flash-import-preview" id="flash-import-preview" hidden></p>
            <details class="flash-format-hints">
              <summary>Formatos aceitos</summary>
              <ul>${hints}</ul>
            </details>
          </div>

          <div class="flash-manual-panel">
            <h3>Ou adicione o primeiro card manualmente</h3>
            <label class="flash-field">
              <span>Pergunta (frente)</span>
              <textarea name="front" rows="3" placeholder="Pergunta ou termo…"></textarea>
            </label>
            <label class="flash-field">
              <span>Resposta (verso)</span>
              <textarea name="back" rows="4" placeholder="Resposta ou explicação…"></textarea>
            </label>
            <label class="flash-field">
              <span>Destaque na resposta <small>(opcional)</small></span>
              <input type="text" name="highlight" maxlength="200" placeholder="Trecho a grifar no verso" />
            </label>
          </div>

          <p class="flash-form-error" id="flash-create-error" hidden></p>
          <div class="flash-form-actions">
            <a class="btn" href="#/flashcards">Cancelar</a>
            <button type="submit" class="btn primary">Salvar deck</button>
          </div>
        </form>
      </div>`;
  }

  function renderFlashCardRow(c, i, slug) {
    const editing = state.flashManageEdit?.slug === slug && state.flashManageEdit?.idx === i;
    if (editing) {
      return `
        <article class="flash-card-row flash-card-row--edit">
          <form class="flash-card-edit-form" data-card-idx="${i}">
            <label class="flash-field">
              <span>Pergunta</span>
              <textarea name="front" rows="2" required maxlength="8000">${esc(c.front)}</textarea>
            </label>
            <label class="flash-field">
              <span>Resposta</span>
              <textarea name="back" rows="3" required maxlength="16000">${esc(c.back)}</textarea>
            </label>
            <label class="flash-field">
              <span>Destaque <small>(opcional)</small></span>
              <input type="text" name="highlight" maxlength="200" value="${esc(c.highlight || "")}" />
            </label>
            <div class="flash-card-row-actions">
              <button type="button" class="btn flash-card-cancel">Cancelar</button>
              <button type="submit" class="btn primary">Salvar alterações</button>
            </div>
          </form>
        </article>`;
    }
    return `
        <article class="flash-card-row">
          <div class="flash-card-row-body">
            <strong>${esc(c.front)}</strong>
            <p>${esc(c.back)}</p>
            ${c.highlight ? `<small class="flash-card-highlight">Destaque: ${esc(c.highlight)}</small>` : ""}
          </div>
          <div class="flash-card-row-actions">
            <button type="button" class="btn btn-sm flash-card-edit" data-card-idx="${i}">Editar</button>
            <button type="button" class="btn btn-sm err flash-card-delete" data-card-idx="${i}">Remover</button>
          </div>
        </article>`;
  }

  function renderFlashManage(slug) {
    const deck = state.decks.find((d) => d.slug === slug && d.custom);
    if (!deck) {
      return `<div class="empty">Deck não encontrado ou não editável. <a href="#/flashcards">← Voltar</a></div>`;
    }
    const cards = deck.cards || [];
    return `
      <div class="page-head flash-page-head">
        <div>
          <h1>${esc(deck.name)}</h1>
          <p>${cards.length} cards · ${esc(deck.category)}</p>
        </div>
        <div class="flash-page-actions">
          <a class="btn primary" href="#/flashcards/${encodeURIComponent(slug)}">▶ Estudar</a>
          <button type="button" class="btn" id="flash-export-deck" data-slug="${esc(slug)}">↓ Exportar JSON</button>
          <button type="button" class="btn err" id="flash-delete-deck" data-slug="${esc(slug)}">Excluir deck</button>
        </div>
      </div>
      <div class="flash-editor">
        <form id="flash-manage-meta" class="flash-form flash-form-inline">
          <label class="flash-field">
            <span>Nome</span>
            <input type="text" name="name" value="${esc(deck.name)}" required maxlength="120" />
          </label>
          <label class="flash-field">
            <span>Categoria</span>
            <input type="text" name="category" value="${esc(deck.category)}" maxlength="80" />
          </label>
          <button type="submit" class="btn">Salvar info</button>
        </form>

        <div class="flash-import-panel">
          <h3>Importar mais cards</h3>
          <label class="flash-field">
            <span>Arquivo</span>
            <input type="file" id="flash-manage-import-file" accept=".csv,.json,.jsonl,.tsv,.txt,.ndjson,text/plain,text/csv,application/json" />
          </label>
          <label class="flash-field">
            <span>Ou cole o conteúdo</span>
            <textarea id="flash-manage-import-text" rows="5" placeholder="Cards a adicionar ao deck…"></textarea>
          </label>
          <button type="button" class="btn" id="flash-manage-import-btn">Importar e adicionar</button>
          <p class="flash-import-preview" id="flash-manage-import-preview" hidden></p>
        </div>

        <form id="flash-add-card" class="flash-form">
          <h3>Adicionar card</h3>
          <label class="flash-field">
            <span>Pergunta</span>
            <textarea name="front" rows="2" required placeholder="Frente do card…"></textarea>
          </label>
          <label class="flash-field">
            <span>Resposta</span>
            <textarea name="back" rows="3" required placeholder="Verso do card…"></textarea>
          </label>
          <label class="flash-field">
            <span>Destaque <small>(opcional)</small></span>
            <input type="text" name="highlight" maxlength="200" />
          </label>
          <button type="submit" class="btn primary">Adicionar card</button>
        </form>

        <section class="flash-card-list">
          <h3>Cards (${cards.length})</h3>
          ${
            cards.length
              ? `<div class="flash-card-rows">
              ${cards.map((c, i) => renderFlashCardRow(c, i, slug)).join("")}
            </div>`
              : `<p class="empty">Nenhum card ainda. Importe ou adicione manualmente.</p>`
          }
        </section>
        <p style="margin-top:1.5rem"><a href="#/flashcards">← Voltar aos decks</a></p>
      </div>`;
  }

  function renderFlashSession(slug) {
    const deck = state.decks.find((d) => d.slug === slug);
    if (!deck) {
      if (state.decksLoading) {
        return `<div class="page-head"><h1>Flashcards</h1><p>Carregando deck…</p></div><div class="empty">Aguarde um instante.</div>`;
      }
      return `<div class="empty">Deck não encontrado.</div>`;
    }
    if (!deck.cards?.length && (state.decksLoading || state.decksHydrating)) {
      return `<div class="page-head"><h1>${esc(deck.name)}</h1><p>Carregando cards…</p></div><div class="empty">Aguarde um instante.</div>`;
    }
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
    const fontIdx = loadJson(LS.fontSize, 2);
    const fontSize = FONT_SIZES[fontIdx] || 15;
    const atFirst = s.idx === 0;
    const atLast = s.idx >= deck.cards.length - 1;

    return `
      <div class="page-head">
        <h1>${esc(deck.name)}</h1>
        <p>Card ${s.idx + 1} de ${deck.cards.length}</p>
      </div>
      <div class="flash-controls">
        <div class="reader-tools flash-font-tools">
          <button class="btn icon" id="flash-font-down" title="Diminuir letra">A−</button>
          <span class="font-size-label" id="flash-font-size-label" title="Tamanho da letra">${fontSize}px</span>
          <button class="btn icon" id="flash-font-up" title="Aumentar letra">A+</button>
        </div>
        <div class="flash-nav">
          <button type="button" class="btn" id="flash-prev" ${atFirst ? "disabled" : ""} title="Card anterior">◁ Anterior</button>
          <button type="button" class="btn ${s.flipped ? "primary" : ""}" id="flash-flip" title="${s.flipped ? "Voltar à pergunta" : "Revelar resposta"}">${s.flipped ? "Ver pergunta" : "Ver resposta"}</button>
          <button type="button" class="btn" id="flash-next" ${atLast ? "disabled" : ""} title="Próximo card">Próximo ▷</button>
        </div>
        ${
          deck.custom
            ? `<div class="flash-study-extra">
          <a class="btn btn-sm" href="#/flashcards/gerenciar/${encodeURIComponent(slug)}" id="flash-edit-current">✎ Editar este card</a>
        </div>`
            : ""
        }
      </div>
      <div class="flash-scene" style="--flash-font:${fontSize}px">
        <div class="flash-card ${s.flipped ? "flipped" : ""}" id="flash-card">
          <div class="flash-face front">
            <div class="flash-face-body lex-protected"><p>${esc(card.front)}</p></div>
            <small class="flash-face-hint">Toque para revelar a resposta</small>
          </div>
          <div class="flash-face back">
            <div class="flash-face-body lex-protected"><p>${backHtml}</p></div>
            <small class="flash-face-hint">Toque para ver a pergunta novamente</small>
          </div>
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
    const sortLaws = (items) => {
      const rank = window.LexFormat?.legisSortRank;
      return [...items].sort((a, b) => {
        if (rank) {
          const lr = rank(a) - rank(b);
          if (lr) return lr;
        }
        return String(a.title || "").localeCompare(String(b.title || ""), "pt");
      });
    };
    const sections = LEI_SECOES.map((secName) => ({
      name: secName,
      items: sortLaws(laws.filter((d) => (org(d).secao_lei_seca || "Legislação Especial") === secName)),
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
      <div class="page-head"><h1>Lei Seca</h1><p>Texto consolidado das normas — grife, anote, ouça em voz alta e ajuste o tamanho da letra.</p></div>
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
              const p = readingProgress(progressDocKey(d));
              const artCount = Math.max(arts.length, d.chunk_count || 0);
              const countLabel = artCount > 1 ? `${artCount} dispositivos` : "Abrir leitura";
              const displayTitle = window.LexFormat?.legisListTitle
                ? window.LexFormat.legisListTitle(d)
                : d.title;
              const searchText = SS() ? SS().lawText(d, org) : displayTitle;
              return `
              <article class="law-card" data-law="${esc(readerRouteId(d))}" data-search-text="${esc(searchText)}">
                <h3>${esc(displayTitle)}</h3>
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

  function renderReader(docId, backRoute, opts = {}) {
    const embedded = Boolean(opts.embedded);
    const doc = findDocument(docId);
    if (!doc) return `<div class="empty">Documento não encontrado.</div>`;
    if (!doc.body) return `<div class="loading">Carregando texto…</div>`;

    if (window.LexFormat) window.LexFormat.ensureFormatted(doc);

    const articles = narrationArticles(doc);
    const studyType = docStudyType(doc);
    const storageId = readerStorageId(doc);
    const prog = readingProgress(storageId);
    const fontIdx = loadJson(LS.fontSize, 2);
    const fontSize = FONT_SIZES[fontIdx] || 15;
    const r = state.reader || { activeArt: 0, narrating: false };
    const canNarrate = canNarrateDoc(doc, articles);
    const highlights = getHighlights(storageId, studyType);
    const notes = getNotes(storageId, studyType);
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
            return `<article class="lei-artigo annot-block" id="art-${i}" data-art-id="${i}"><div class="lei-label">${esc(b.label)}</div><div class="lei-text article-text">${saved}</div>${renderBlockNote(storageId, i, note, studyType)}</article>`;
          }
          const blockHtml = F.renderLegisBlock(b, i).replace('class="lei-text"', 'class="lei-text article-text"');
          return blockHtml.replace(/<\/article>\s*$/, `${renderBlockNote(storageId, i, note, studyType)}</article>`);
        }).join("")}`;
    } else if (doc.formatted?.mode === "juris") {
      const items = doc.formatted.items || [];
      bodyHtml = items.length
        ? `<div class="juris-list">${items
            .map((it, i) => {
              const note = notes[i];
              const saved = highlights[i];
              if (saved && typeof saved === "string") {
                return `<article class="juris-item annot-block" id="art-${i}" data-art-id="${i}"><div class="article-text">${saved}</div>${renderBlockNote(storageId, i, note, studyType)}</article>`;
              }
              let itemHtml = F.renderJurisItem(it, i)
                .replace('<article class="juris-item"', `<article class="juris-item annot-block" id="art-${i}" data-art-id="${i}"`);
              itemHtml = applyJurisItemHighlights(itemHtml, i, highlights) || itemHtml;
              return augmentJurisItemHtml(itemHtml, i, notes, storageId, studyType);
            })
            .join("")}</div>`
        : (() => {
            const note = notes[0] ?? notes["0.texto"];
            const saved = highlights[0] ?? highlights["0.texto"];
            const inner = saved || esc(doc.body);
            return `<div class="juris-list"><article class="juris-item annot-block" id="art-0" data-art-id="0"><div class="article-text" data-hl-part="texto">${inner}</div>${renderBlockNote(storageId, "0.texto", note, studyType)}</article></div>`;
          })();
    } else {
      bodyHtml = articles
        .map(
          (a, i) => `
        <article class="article-block annot-block" id="art-${i}" data-art-id="${i}">
          <div class="article-num">${esc(a.label)}</div>
          <div class="article-text">${highlights[i] || esc(a.text)}</div>
          ${renderBlockNote(storageId, i, notes[i], studyType)}
        </article>`
        )
        .join("");
    }

    const voiceId = selectedTtsVoiceId();
    const panel = `
      <aside class="panel">
        <div class="ring">${prog.pct}%</div>
        <div class="audio-panel">
          <h4>Narração</h4>
          <button class="btn primary" id="tts-toggle">${r.narrating ? "⏸ Pausar" : "🎧 Ouvir"}</button>
          <label class="tts-voice-field">Voz ${renderTtsVoiceSelect("tts-voice", voiceId)}</label>
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
              ${
                embedded
                  ? `<button type="button" class="back-link" data-juris-close>← Voltar à lista</button>`
                  : `<a href="#/${backRoute || "lei-seca"}" class="back-link">← Voltar</a>`
              }
              <h1 class="reader-title">${esc(doc.title)}</h1>
            </div>
            <div class="reader-tools">
              <button class="btn icon" id="font-down" title="Diminuir letra">A−</button>
              <span class="font-size-label" id="font-size-label" title="Tamanho da letra">${fontSize}px</span>
              <button class="btn icon" id="font-up" title="Aumentar letra">A+</button>
              ${canNarrate ? renderTtsVoiceSelect("tts-voice-header", voiceId) : ""}
              ${canNarrate ? `<button class="btn ${r.narrating ? "primary" : ""}" id="tts-toggle-header" title="Ouvir em voz alta">${r.narrating ? "⏸ Pausar" : "🎧 Ouvir"}</button>` : ""}
              <button class="btn" id="mark-read">🔖 Marcar lido</button>
              ${renderReportError({
                area: studyType,
                id: doc.external_id,
                title: doc.title || docId,
              })}
            </div>
          </div>
          <div class="reader-features-hint ${studyType === "jurisprudencia" ? "reader-features-hint-juris" : ""}" role="note">
            ${
              studyType === "jurisprudencia"
                ? `<span>🖍️ Selecione ementa, tese ou julgado para <strong>grifar</strong></span>
            <span>📝 <strong>＋ Anotar</strong> em cada seção</span>`
                : `<span>🖍️ Selecione texto para <strong>grifar</strong></span>
            <span>📝 Use <strong>＋ Anotar</strong> em cada bloco</span>`
            }
            <span>🎧 <strong>Ouvir</strong> com vozes diferentes</span>
            <span>🔤 <strong>A− / A+</strong> ajusta o tamanho da letra</span>
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
        ${canNarrate && r.narrating ? panel : ""}`,
      doc,
      articles,
    };
  }

  function renderJurisListChrome(fontSize) {
    return `
      <div class="juris-list-toolbar">
        <div class="reader-tools juris-list-font-tools">
          <button class="btn icon" id="juris-list-font-down" title="Diminuir letra na lista">A−</button>
          <span class="font-size-label" id="juris-list-font-size-label" title="Tamanho da letra">${fontSize}px</span>
          <button class="btn icon" id="juris-list-font-up" title="Aumentar letra na lista">A+</button>
        </div>
        <div class="reader-features-hint reader-features-hint-juris" role="note">
          <span>🖍️ Selecione ementa, tese ou julgado para <strong>grifar</strong></span>
          <span>📝 <strong>＋ Anotar</strong> em cada seção</span>
          <span>🎧 <strong>Ouvir</strong> com vozes diferentes</span>
          <span>🔤 <strong>A− / A+</strong> ajusta o tamanho da letra</span>
        </div>
      </div>`;
  }

  function renderJurisprudencia(openDocId) {
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

    const fontIdx = loadJson(LS.fontSize, 2);
    const fontSize = FONT_SIZES[fontIdx] || 15;
    const readerShell = openDocId
      ? `<section class="juris-reader-shell" id="juris-reader-shell" aria-label="Leitor de jurisprudência">
          <div class="juris-reader-embed" id="juris-reader-embed"><div class="loading">Carregando precedente…</div></div>
        </section>`
      : "";

    return `
      <div class="juris-list-page" style="--juris-list-font:${fontSize}px">
      ${renderJurisListChrome(fontSize)}
      ${readerShell}
      <div class="page-head"><h1>Jurisprudência &amp; Súmulas</h1><p>Precedentes dos tribunais superiores — abra um item para grifar, anotar, ouvir e ajustar a letra.</p></div>
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
                  const openId = readerRouteId(d);
                  const isOpen = openDocId && openDocId === openId;
                  return `
            <article class="juris-card ${studied ? "studied" : ""} ${isOpen ? "juris-card-open" : ""}" data-juris-open="${esc(openId)}" data-search-text="${esc(searchText)}">
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
              <div class="toolbar juris-card-actions" style="margin-top:0.75rem;margin-bottom:0">
                <button type="button" class="btn primary" data-juris-open-btn="${esc(openId)}">${isOpen ? "▲ Recolher" : "📖 Abrir"}</button>
                <button type="button" class="btn" data-studied="${esc(d.external_id)}">${studied ? "Desmarcar" : "✅ Estudada"}</button>
                <button type="button" class="btn" data-fav="${esc(d.external_id)}">☆ Favoritar</button>
              </div>
            </article>`;
                })
                .join("")
            : `<div class="empty">Nenhum precedente para os filtros selecionados.</div>`
        }
      </div>
      <div class="empty section-search-empty" data-section-empty hidden>Nenhum precedente para este tema.</div>
      </div>
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

  const Q_RESULT_FILTERS = [
    { id: "all", label: "Todas" },
    { id: "acertou", label: "Acertei" },
    { id: "errou", label: "Errei" },
    { id: "pendente", label: "Não respondidas" },
  ];

  const Q_STATS_PERIODS = [
    { id: "24h", label: "24h", ms: 86400000 },
    { id: "7d", label: "7 dias", ms: 7 * 86400000 },
    { id: "30d", label: "Mês", ms: 30 * 86400000 },
    { id: "365d", label: "Ano", ms: 365 * 86400000 },
    { id: "all", label: "Todo período", ms: null },
  ];

  function initQAnswers() {
    const saved = loadJson(LS.questionAnswers, {});
    if (saved && typeof saved === "object" && !Array.isArray(saved)) {
      state.qAnswers = saved;
    }
  }

  function rehydrateQAnswers() {
    let changed = false;
    for (const [qid, qa] of Object.entries(state.qAnswers)) {
      if (!qa?.revealed || qa.correct != null) continue;
      const d = findQuestion(qid);
      if (!d || !isQuestaoObjetiva(d) || !qa.pick) continue;
      const meta = d.meta || {};
      const correctKey = gabaritoKey(meta.gabarito || meta.resposta_correta, parseAlternativas(meta));
      qa.correct = qa.pick === correctKey;
      if (!qa.revealedAt) qa.revealedAt = Date.now();
      changed = true;
    }
    if (changed) persistQAnswers();
  }

  function persistQAnswers() {
    saveJson(LS.questionAnswers, state.qAnswers);
  }

  function findQuestion(qid) {
    return state.documents.find((d) => d.external_id === qid);
  }

  function isQuestaoObjetiva(d) {
    return d.doc_type === "questoes_objetivas" && parseAlternativas(d.meta || {}).length > 0;
  }

  function finalizeQAnswer(qid, d) {
    const qa = qAnswerState(qid);
    if (!qa.revealed) return;
    qa.revealedAt = qa.revealedAt || Date.now();
    if (d && isQuestaoObjetiva(d) && qa.pick) {
      const meta = d.meta || {};
      const correctKey = gabaritoKey(meta.gabarito || meta.resposta_correta, parseAlternativas(meta));
      qa.correct = qa.pick === correctKey;
    } else {
      qa.correct = null;
    }
    persistQAnswers();
  }

  function questaoMatchesResultFilter(d, resultFilter) {
    const filter = resultFilter || "all";
    if (filter === "all") return true;
    const qa = state.qAnswers[d.external_id];
    const isObj = isQuestaoObjetiva(d);
    if (filter === "pendente") {
      if (!qa?.revealed) return true;
      return isObj && !qa.pick;
    }
    if (!isObj || !qa?.revealed || qa.correct == null) return false;
    if (filter === "acertou") return qa.correct === true;
    if (filter === "errou") return qa.correct === false;
    return true;
  }

  function qStatsForPeriod(periodId, qidSet) {
    const period = Q_STATS_PERIODS.find((p) => p.id === periodId) || Q_STATS_PERIODS[1];
    const now = Date.now();
    let total = 0;
    let ok = 0;
    for (const [qid, qa] of Object.entries(state.qAnswers)) {
      if (qidSet && !qidSet.has(qid)) continue;
      if (qa?.correct == null || !qa.revealedAt) continue;
      if (period.ms != null && now - qa.revealedAt > period.ms) continue;
      total++;
      if (qa.correct) ok++;
    }
    const pct = total ? Math.round((ok / total) * 100) : null;
    return { ...period, total, ok, err: total - ok, pct };
  }

  function findDoutrinaDisciplina(slug) {
    return DOUTRINA_DISCIPLINAS.find((d) => d.slug === slug) || null;
  }

  function doutrinaMateriaMatch(disc, materia) {
    const m = String(materia || "").trim();
    return disc.materias.some((label) => label === m);
  }

  function doutrinaQuestionsFor(disc) {
    const all = [...byType("questoes_objetivas"), ...byType("questoes_subjetivas")];
    return all.filter((d) => doutrinaMateriaMatch(disc, org(d).materia));
  }

  function doutrinaFilterState() {
    if (!state.doutrinaFilter) state.doutrinaFilter = { banca: "all", assunto: "all", result: "all" };
    return state.doutrinaFilter;
  }

  function doutrinaAssuntoLabel(d) {
    const a = (d.meta || {}).assunto;
    return (a && String(a).trim()) || "Geral";
  }

  function renderDoutrina() {
    if (state.questionsLoading) {
      return `
        <div class="page-head"><h1>Doutrina</h1><p>Carregando acervo do NaIntegra Cursos…</p></div>
        <div class="loading">Aguarde…</div>`;
    }

    const cards = DOUTRINA_DISCIPLINAS.map((disc) => {
      const items = doutrinaQuestionsFor(disc);
      const assuntos = new Map();
      items.forEach((d) => {
        const label = doutrinaAssuntoLabel(d);
        assuntos.set(label, (assuntos.get(label) || 0) + 1);
      });
      const topAssuntos = [...assuntos.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 3)
        .map(([name, n]) => `${name} (${n})`)
        .join(" · ");
      return `
        <a class="doutrina-disc-card" href="#/doutrina/${encodeURIComponent(disc.slug)}">
          <span class="doutrina-disc-abbr" aria-hidden="true">${esc(disc.abbr)}</span>
          <h2>${esc(disc.label)}</h2>
          <p class="doutrina-disc-desc">${esc(disc.desc)}</p>
          <p class="doutrina-disc-meta">${items.length} questões${topAssuntos ? ` · ${esc(topAssuntos)}` : ""}</p>
        </a>`;
    }).join("");

    const total = DOUTRINA_DISCIPLINAS.reduce((n, disc) => n + doutrinaQuestionsFor(disc).length, 0);

    return `
      <div class="page-head doutrina-page">
        <h1>Doutrina</h1>
        <p>Português, Raciocínio Lógico e Informática — questões do repositório <strong>NaIntegra Cursos</strong> (${total.toLocaleString("pt-BR")} no acervo).</p>
      </div>
      <div class="doutrina-disc-grid">${cards}</div>
      <p class="doutrina-source-note">Material importado de provas anteriores (CESPE, FCC, FGV e outras bancas). Para o banco completo por carreira, use <a href="#/questoes">Questões</a>.</p>`;
  }

  function renderDoutrinaDisciplina(disc) {
    const all = doutrinaQuestionsFor(disc);
    const filter = doutrinaFilterState();
    const statsPeriod = state.qStatsPeriod || "7d";
    const qidSet = new Set(all.map((d) => d.external_id));
    const stats = qStatsForPeriod(statsPeriod, qidSet);

    let filtered = all.filter((d) => {
      const o = org(d);
      if (filter.banca !== "all" && o.banca !== filter.banca) return false;
      if (filter.assunto !== "all" && doutrinaAssuntoLabel(d) !== filter.assunto) return false;
      if (!questaoMatchesResultFilter(d, filter.result)) return false;
      return true;
    });

    const focusQ = state.route.sub;
    if (focusQ) {
      const focus = all.find(
        (d) => d.external_id === focusQ || d.lex_route_id === focusQ || d.doc_key === focusQ
      );
      if (focus) {
        filtered = [focus, ...filtered.filter((d) => d.external_id !== focus.external_id)];
        state.doutrinaPage = 1;
      }
    }

    const bancas = ["all", ...new Set(all.map((d) => org(d).banca).filter(Boolean))].sort((a, b) => {
      if (a === "all") return -1;
      if (b === "all") return 1;
      return a.localeCompare(b, "pt-BR");
    });
    const assuntos = ["all", ...new Set(all.map(doutrinaAssuntoLabel))].sort((a, b) => {
      if (a === "all") return -1;
      if (b === "all") return 1;
      return a.localeCompare(b, "pt-BR");
    });

    const pageSize = state.doutrinaPageSize || 50;
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
    const page = Math.min(Math.max(1, state.doutrinaPage || 1), totalPages);
    state.doutrinaPage = page;
    const pageItems = filtered.slice((page - 1) * pageSize, page * pageSize);
    state.questaoPageIds = pageItems.map((d) => d.external_id);

    if (!all.length) {
      return `
        <div class="page-head"><h1>${esc(disc.label)}</h1><p><a href="#/doutrina">← Doutrina</a></p></div>
        <div class="empty">Nenhuma questão desta disciplina no acervo ainda.</div>`;
    }

    return `
      <div class="page-head doutrina-page">
        <p class="doutrina-breadcrumb"><a href="#/doutrina">Doutrina</a> / <strong>${esc(disc.label)}</strong></p>
        <h1>${esc(disc.label)}</h1>
        <p>${all.length} questões · NaIntegra Cursos</p>
      </div>
      <section class="q-stats-panel" aria-label="Desempenho em ${esc(disc.label)}">
        <h2 class="q-stats-title">Taxa de acerto</h2>
        <div class="toolbar q-stats-periods">
          ${Q_STATS_PERIODS.map(
            (p) =>
              `<button type="button" class="chip ${statsPeriod === p.id ? "active" : ""}" data-q-stats-period="${esc(p.id)}">${esc(p.label)}</button>`
          ).join("")}
        </div>
        <p class="q-stats-summary">
          ${
            stats.total
              ? `<strong>${stats.pct}%</strong> de acertos (${stats.ok} certas · ${stats.err} erradas · ${stats.total} respondidas)`
              : `Nenhuma questão respondida${statsPeriod === "all" ? "" : " neste período"}.`
          }
        </p>
      </section>
      ${sectionSearchBar("doutrina", `Buscar em ${disc.label}…`)}
      <div class="toolbar q-result-filters">
        ${Q_RESULT_FILTERS.map(
          (f) =>
            `<button type="button" class="chip ${(filter.result || "all") === f.id ? "active" : ""}" data-doutrina-result="${esc(f.id)}">${esc(f.label)}</button>`
        ).join("")}
      </div>
      <div class="toolbar doutrina-assunto-toolbar">
        ${assuntos.map((a) => {
          const label = a === "all" ? "Todos assuntos" : a;
          return `<button type="button" class="chip ${filter.assunto === a ? "active" : ""}" data-doutrina-assunto="${esc(a)}">${esc(label)}</button>`;
        }).join("")}
      </div>
      <div class="toolbar">
        ${bancas.map((b) => `<button type="button" class="chip ${filter.banca === b ? "active" : ""}" data-doutrina-banca="${esc(b)}">${b === "all" ? "Todas bancas" : esc(b)}</button>`).join("")}
      </div>
      <p class="tag" style="margin:0 0 1rem">${filtered.length} no filtro · página ${page} de ${totalPages}</p>
      <div class="section-list-scope" data-section-scope="doutrina">
        <div class="card-list">
          ${pageItems.map((d) => renderQuestaoCard(d)).join("")}
        </div>
        <div class="toolbar" style="margin-top:1rem">
          <button type="button" class="chip" data-doutrina-page="prev" ${page <= 1 ? "disabled" : ""}>← Anterior</button>
          <button type="button" class="chip" data-doutrina-page="next" ${page >= totalPages ? "disabled" : ""}>Próxima →</button>
        </div>
        <div class="empty section-search-empty" data-section-empty hidden>Nenhuma questão para este tema.</div>
      </div>`;
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
    const acertou = isObj && qa.revealed && qa.correct === true;
    const errou = isObj && qa.revealed && qa.correct === false;
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
    const commentsHtml = window.LexQuestaoComentarios
      ? window.LexQuestaoComentarios.renderSection(qid, {
          user: state.currentUser,
          editingId:
            state.questaoCommentEdit?.qid === qid ? state.questaoCommentEdit.commentId : null,
        })
      : "";

    return `
      <article class="question-card ${acertou ? "question-card-ok" : errou ? "question-card-err" : ""}" data-q="${esc(qid)}" data-search-text="${esc(searchText)}">
        <div class="meta-row">
          ${o.banca ? `<span class="tag">${esc(o.banca)} ${o.ano || ""}</span>` : ""}
          ${o.cargo ? `<span class="tag">${esc(o.cargo)}</span>` : ""}
          ${o.materia ? `<span class="tag">${esc(o.materia)}</span>` : ""}
          ${acertou ? `<span class="tag q-tag-ok">Acertou</span>` : errou ? `<span class="tag q-tag-err">Errou</span>` : ""}
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
        ${commentsHtml}
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
    const filter = state.qFilter || { banca: "all", disciplina: "all", result: "all" };
    const statsPeriod = state.qStatsPeriod || "7d";
    const stats = qStatsForPeriod(statsPeriod);

    let filtered = all.filter((d) => {
      const o = org(d);
      if (filter.banca !== "all" && o.banca !== filter.banca) return false;
      if (filter.disciplina !== "all" && (o.materia || "").toLowerCase() !== filter.disciplina) return false;
      if (!questaoMatchesResultFilter(d, filter.result)) return false;
      return true;
    });

    const focusQ = state.route.sub;
    if (focusQ) {
      const focus = all.find(
        (d) => d.external_id === focusQ || d.lex_route_id === focusQ || d.doc_key === focusQ
      );
      if (focus) {
        filtered = [focus, ...filtered.filter((d) => d.external_id !== focus.external_id)];
        state.questionsPage = 1;
      }
    }

    const bancas = ["all", ...new Set(all.map((d) => org(d).banca).filter(Boolean))];
    const pageSize = state.questionsPageSize || 50;
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
    const page = Math.min(Math.max(1, state.questionsPage || 1), totalPages);
    state.questionsPage = page;
    const pageItems = filtered.slice((page - 1) * pageSize, page * pageSize);
    state.questaoPageIds = pageItems.map((d) => d.external_id);

    if (!all.length) {
      return `
        <div class="page-head"><h1>Questões</h1><p>Objetivas (CESPE/FCC) e discursivas de segunda fase.</p></div>
        <div class="empty">As questões serão disponibilizadas em breve.</div>`;
    }

    return `
      <div class="page-head"><h1>Questões</h1><p>${objs.length} objetivas · ${subs.length} subjetivas</p></div>
      <section class="q-stats-panel" aria-label="Desempenho em questões objetivas">
        <h2 class="q-stats-title">Taxa de acerto</h2>
        <div class="toolbar q-stats-periods">
          ${Q_STATS_PERIODS.map(
            (p) =>
              `<button type="button" class="chip ${statsPeriod === p.id ? "active" : ""}" data-q-stats-period="${esc(p.id)}">${esc(p.label)}</button>`
          ).join("")}
        </div>
        <p class="q-stats-summary">
          ${
            stats.total
              ? `<strong>${stats.pct}%</strong> de acertos (${stats.ok} certas · ${stats.err} erradas · ${stats.total} respondidas)`
              : `Nenhuma questão objetiva respondida${statsPeriod === "all" ? "" : " neste período"}.`
          }
        </p>
        <p class="q-stats-note">Estatísticas consideram apenas questões objetivas conferidas.</p>
      </section>
      ${sectionSearchBar("questoes", "Buscar por tema (ex.: penal, constitucional, CESPE)…")}
      <div class="toolbar q-result-filters">
        ${Q_RESULT_FILTERS.map(
          (f) =>
            `<button type="button" class="chip ${(filter.result || "all") === f.id ? "active" : ""}" data-q-result="${esc(f.id)}">${esc(f.label)}</button>`
        ).join("")}
      </div>
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
    doutrina: "Doutrina",
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

  function lexJsBase() {
    const scripts = document.getElementsByTagName("script");
    for (let i = scripts.length - 1; i >= 0; i--) {
      const src = scripts[i].src;
      if (src && /\/js\/app\.js/i.test(src)) {
        return src.replace(/\/js\/app\.js.*$/i, "");
      }
    }
    const path = location.pathname.replace(/\/[^/]*$/, "");
    return `${location.origin}${path}`;
  }

  let studyPlansLoadPromise = null;

  function ensureStudyPlansModule() {
    if (window.LexStudyPlans) return Promise.resolve(true);
    if (studyPlansLoadPromise) return studyPlansLoadPromise;
    studyPlansLoadPromise = new Promise((resolve) => {
      const done = (ok) => {
        studyPlansLoadPromise = null;
        resolve(ok);
      };
      const existing = document.querySelector("script[data-lex-study-plans]");
      if (existing) {
        if (window.LexStudyPlans) return done(true);
        existing.addEventListener("load", () => done(!!window.LexStudyPlans));
        existing.addEventListener("error", () => done(false));
        return;
      }
      const s = document.createElement("script");
      s.src = `${lexJsBase()}/js/study-plans.js?v=3`;
      s.dataset.lexStudyPlans = "1";
      s.onload = () => done(!!window.LexStudyPlans);
      s.onerror = () => done(false);
      document.head.appendChild(s);
    });
    return studyPlansLoadPromise;
  }

  function studyPlansApi() {
    return window.LexStudyPlans;
  }

  function renderStudyPlanUnavailable() {
    return `
      <div class="page-head">
        <h1>Plano de estudos</h1>
        <p>Não foi possível carregar o módulo de planos.</p>
      </div>
      <div class="empty">
        <p>Verifique se o arquivo <code>js/study-plans.js</code> está publicado no servidor (recarregue com Ctrl+Shift+R).</p>
        <button type="button" class="btn primary" id="study-reload-module">Tentar novamente</button>
      </div>`;
  }

  function renderStudyPlanWizard() {
    const SP = studyPlansApi();
    if (!SP) {
      if (state.studyPlansModuleLoading) {
        return `
          <div class="page-head"><h1>Plano de estudos</h1><p>Carregando módulo…</p></div>
          <div class="loading">Aguarde um instante.</div>`;
      }
      return renderStudyPlanUnavailable();
    }
    if (!state.documents.length) {
      return `
        <div class="page-head"><h1>Plano de estudos</h1><p>Carregando acervo jurídico…</p></div>
        <div class="loading">Aguarde um instante.</div>`;
    }
    const saved = SP.loadSavedPlan();
    const careers = SP.CAREERS;
    const selected = state.studyPlanCareer || saved?.careerId || careers[0]?.id;
    const ufSelected = state.studyPlanUf || saved?.uf || "geral";
    const ufProfiles = SP.UF_PROFILES || { geral: { label: "Brasil (edital genérico)", bancas: [] } };

    const careerCards = careers
      .map(
        (c) => `
      <button type="button" class="study-career-card ${c.id === selected ? "selected" : ""}" data-career="${esc(c.id)}">
        <h3>${esc(c.label)}</h3>
        <p>${esc(c.description)}</p>
      </button>`
      )
      .join("");

    const career = SP.getCareer(selected);
    const legisPreview = career ? SP.resolveLegis(state.documents, career) : [];
    const jurisPreview = career ? SP.resolveJuris(state.documents, career) : [];
    const decksPreview = career ? SP.resolveFlashcardDecks(state.decks, career) : [];
    const questoesPreview =
      career && SP.filterQuestions ? SP.filterQuestions(state.documents, selected, ufSelected) : [];
    const ufProfile = SP.getUfProfile?.(ufSelected) || ufProfiles[ufSelected] || ufProfiles.geral;
    const totalArts = legisPreview.reduce((s, l) => s + l.articles, 0);

    const ufOptions = Object.entries(ufProfiles)
      .map(
        ([id, p]) =>
          `<option value="${esc(id)}" ${id === ufSelected ? "selected" : ""}>${esc(p.label)}</option>`
      )
      .join("");

    const missingWarn =
      career && legisPreview.length < career.legis.length
        ? `<p class="study-plan-warn">Algumas leis do edital típico ainda não constam no acervo (${career.legis.length - legisPreview.length} pendente(s)).</p>`
        : "";

    const enrichHint = state.documentsEnriching
      ? `<p class="sync-hint">Carregando súmulas e temas no acervo… a prévia de jurisprudência será atualizada em instantes.</p>`
      : "";

    const savedBanner = saved
      ? `<p class="sync-hint">Você já tem um plano ativo (${esc(saved.careerLabel)}, ${saved.totalDays} dias). <a href="#/plano-estudos/trilha">Abrir trilha</a> ou gere um novo abaixo.</p>`
      : "";

    const cloudHint = window.LexStore?.isLoggedIn?.()
      ? `<p class="sync-hint">Com sua conta, o plano sincroniza entre dispositivos.</p>`
      : `<p class="sync-hint">Entre na conta para salvar o plano na nuvem.</p>`;

    return `
      <div class="study-plan-page">
        <div class="page-head">
          <h1>Plano de estudos</h1>
          <p>Trilha automática com <strong>disciplinas intercaladas</strong> a cada dia — legislação, jurisprudência, questões e flashcards em rodízio.</p>
        </div>
        ${savedBanner}
        ${cloudHint}
        ${enrichHint}
        <h2 class="section-title">Objetivo de carreira</h2>
        <div class="study-career-grid" id="study-career-grid">${careerCards}</div>
        <div class="study-plan-form" id="study-plan-form">
          <label for="study-days">Duração do plano (dias)</label>
          <input type="number" id="study-days" min="14" max="365" value="${career?.defaultDays || 90}" />
          <label for="study-start">Data de início</label>
          <input type="date" id="study-start" value="${new Date().toISOString().slice(0, 10)}" />
          <label for="study-uf">Estado do concurso (edital)</label>
          <select id="study-uf">${ufOptions}</select>
          <p class="sync-hint" style="margin-top:-0.5rem">Bancas priorizadas nas questões: ${ufProfile.bancas?.length ? esc(ufProfile.bancas.join(", ")) : "todas do acervo"}</p>
          <label for="study-questoes-day">Questões por dia</label>
          <input type="number" id="study-questoes-day" min="0" max="20" value="6" />
          <div class="study-plan-summary" id="study-plan-preview">
            <strong>${esc(career?.label || "")}</strong> — ${esc(career?.editalFocus || "")}
            <ul>
              <li><strong>${legisPreview.length}</strong> leis no acervo · ~<strong>${totalArts.toLocaleString("pt-BR")}</strong> unidades (artigos/dispositivos)</li>
              <li><strong>${jurisPreview.length}</strong> itens de jurisprudência (súmulas e temas)</li>
              <li><strong>${questoesPreview.length}</strong> questões filtradas${state.questionsLoaded ? "" : " (carregando banco…)"}</li>
              <li><strong>${decksPreview.length}</strong> decks de flashcards · ${decksPreview.reduce((s, d) => s + d.cardCount, 0).toLocaleString("pt-BR")} cards</li>
            </ul>
            ${missingWarn}
          </div>
          <details class="study-syllabus">
            <summary>Leis previstas para esta carreira</summary>
            <ul>${(career?.legis || []).map((l) => `<li>${esc(l.label)}</li>`).join("")}</ul>
          </details>
          <button type="button" class="btn primary" id="study-generate-btn">Gerar plano e trilha</button>
        </div>
      </div>`;
  }

  function renderStudyTrail() {
    const SP = studyPlansApi();
    if (!SP) return renderStudyPlanUnavailable();
    const plan = SP?.loadSavedPlan();
    if (!plan) {
      return `
        <div class="page-head">
          <h1>Trilha de estudos</h1>
          <p>Nenhum plano gerado ainda.</p>
        </div>
        <a class="btn primary" href="#/plano-estudos">Criar plano</a>`;
    }

    const prog = SP.planProgress(plan);
    const todayIdx = SP.todayIndex(plan);
    const t = plan.targets || {};

    const dayHtml = plan.trail
      .map((day, idx) => {
        const tasks = [
          ...(day.legisTasks || []),
          ...(day.jurisTasks || []),
          ...(day.flashTasks || []),
          ...(day.questoesTasks || []),
        ];
        const doneSet = new Set(day.completedTasks || []);
        const dayDone = tasks.length > 0 && tasks.every((tk) => doneSet.has(tk.taskId));
        const isToday = idx === todayIdx;
        const expanded = state.studyPlanExpandedDay === idx || (isToday && state.studyPlanExpandedDay == null);

        const legisRows = (day.legisTasks || [])
          .map((task) => {
            const done = doneSet.has(task.taskId);
            const href = docHash("lei-seca", task.docId);
            const range =
              task.articleFrom === task.articleTo
                ? `art. ${task.articleFrom}`
                : `arts. ${task.articleFrom}–${task.articleTo}`;
            return `
            <label class="study-task ${done ? "done" : ""}">
              <input type="checkbox" data-study-task data-day="${idx}" data-task="${esc(task.taskId)}" ${done ? "checked" : ""} />
              <span><a href="${href}">${esc(task.title)}</a> — ${range} (${task.articleCount} un.)</span>
            </label>`;
          })
          .join("");

        const jurisRows = (day.jurisTasks || [])
          .map((task) => {
            const done = doneSet.has(task.taskId);
            const href = docHash("jurisprudencia", task.docId);
            return `
            <label class="study-task ${done ? "done" : ""}">
              <input type="checkbox" data-study-task data-day="${idx}" data-task="${esc(task.taskId)}" ${done ? "checked" : ""} />
              <span><a href="${href}">${esc(task.title)}</a>${task.group ? ` <em>(${esc(task.group)})</em>` : ""}</span>
            </label>`;
          })
          .join("");

        const flashRows = (day.flashTasks || [])
          .map((task) => {
            const done = doneSet.has(task.taskId);
            return `
            <label class="study-task ${done ? "done" : ""}">
              <input type="checkbox" data-study-task data-day="${idx}" data-task="${esc(task.taskId)}" ${done ? "checked" : ""} />
              <span><a href="#/flashcards/${encodeURIComponent(task.slug)}">${esc(task.name)}</a> — ${task.count} cards</span>
            </label>`;
          })
          .join("");

        const questoesRows = (day.questoesTasks || [])
          .map((task) => {
            const done = doneSet.has(task.taskId);
            const href = `#/questoes?q=${encodeURIComponent(task.docId)}`;
            return `
            <label class="study-task ${done ? "done" : ""}">
              <input type="checkbox" data-study-task data-day="${idx}" data-task="${esc(task.taskId)}" ${done ? "checked" : ""} />
              <span><a href="${href}">${esc(task.title)}</a>${task.questaoTipo ? ` <em>(${esc(task.questaoTipo)})</em>` : ""}</span>
            </label>`;
          })
          .join("");

        return `
        <article class="study-day ${isToday ? "today" : ""} ${dayDone ? "done" : ""}">
          <button type="button" class="study-day-head" data-study-day-toggle="${idx}" aria-expanded="${expanded}">
            <strong>Dia ${day.day}</strong>
            <span class="study-day-date">${esc(day.date)}</span>
            <span class="study-day-badge">${day.articlesTarget} art. · ${day.jurisTarget} juris · ${day.questoesTarget || 0} quest. · ${day.flashTarget || 0} cards</span>
          </button>
          <div class="study-day-body" ${expanded ? "" : "hidden"}>
            ${legisRows ? `<div class="study-task-group"><h4>Legislação</h4>${legisRows}</div>` : ""}
            ${jurisRows ? `<div class="study-task-group"><h4>Jurisprudência</h4>${jurisRows}</div>` : ""}
            ${questoesRows ? `<div class="study-task-group"><h4>Questões</h4>${questoesRows}</div>` : ""}
            ${flashRows ? `<div class="study-task-group"><h4>Flashcards</h4>${flashRows}</div>` : ""}
          </div>
        </article>`;
      })
      .join("");

    return `
      <div class="study-plan-page">
        <div class="page-head">
          <h1>Trilha — ${esc(plan.careerLabel)}</h1>
          <p>${plan.totalDays} dias · ${esc(plan.ufLabel || "Brasil")} · início ${esc(plan.startDate)} · meta: ~${t.articlesPerDay || "—"} artigos, ${t.jurisPerDay || "—"} juris, ${t.questoesPerDay || 0} questões/dia</p>
        </div>
        <div class="study-trail-head">
          <div class="study-trail-progress">
            <span>Progresso geral: <strong>${prog.pct}%</strong> (${prog.done}/${prog.total} tarefas)</span>
            <div class="study-trail-progress-bar"><span style="width:${prog.pct}%"></span></div>
          </div>
          <div>
            <a class="btn sm" href="#/plano-estudos">Novo plano</a>
            <button type="button" class="btn sm" id="study-clear-plan">Excluir plano</button>
          </div>
        </div>
        <div class="study-trail-meta">
          <span>${(plan.legisCatalog || []).length} leis</span>
          <span>${plan.jurisCount || 0} jurisprudências</span>
          <span>${t.totalQuestoes || 0} questões na trilha</span>
          <span>~${(t.totalLegisArticles || 0).toLocaleString("pt-BR")} artigos no total</span>
        </div>
        <div class="study-day-list">${dayHtml}</div>
      </div>`;
  }

  function bindStudyPlanWizard() {
    const SP = studyPlansApi();
    if (!SP) return;

    document.querySelectorAll("[data-career]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.studyPlanCareer = btn.getAttribute("data-career");
        render();
      });
    });

    document.getElementById("study-uf")?.addEventListener("change", (e) => {
      state.studyPlanUf = e.target.value;
      render();
    });

    document.getElementById("study-generate-btn")?.addEventListener("click", async () => {
      const btn = document.getElementById("study-generate-btn");
      const careerId = state.studyPlanCareer || SP.loadSavedPlan()?.careerId || SP.CAREERS[0]?.id;
      const days = parseInt(document.getElementById("study-days")?.value, 10);
      const startDate = document.getElementById("study-start")?.value;
      const uf = document.getElementById("study-uf")?.value || "geral";
      const questoesPerDay = parseInt(document.getElementById("study-questoes-day")?.value, 10);
      if (btn) {
        btn.disabled = true;
        btn.textContent = "Gerando trilha…";
      }
      try {
        await ensureQuestionsLoaded();
        let docs = state.documents;
        if (window.LexData?.enrichDocuments) {
          docs = await window.LexData.enrichDocuments(docs);
          state.documents = docs;
          state.documentsEnriching = false;
        }
        const plan = SP.generatePlan({
          careerId,
          totalDays: days,
          startDate,
          documents: docs,
          decks: state.decks,
          uf,
          questoesPerDay,
        });
        SP.savePlan(plan);
        location.hash = "#/plano-estudos/trilha";
      } catch (err) {
        console.error(err);
        alert("Não foi possível gerar o plano. Tente novamente.");
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.textContent = "Gerar plano e trilha";
        }
      }
    });
  }

  function bindStudyTrail() {
    const SP = studyPlansApi();
    if (!SP) return;

    document.getElementById("study-clear-plan")?.addEventListener("click", () => {
      if (confirm("Excluir o plano de estudos salvo?")) {
        SP.clearPlan();
        location.hash = "#/plano-estudos";
      }
    });

    document.querySelectorAll("[data-study-day-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.getAttribute("data-study-day-toggle"), 10);
        state.studyPlanExpandedDay = state.studyPlanExpandedDay === idx ? null : idx;
        render();
      });
    });

    document.querySelectorAll("[data-study-task]").forEach((input) => {
      input.addEventListener("change", () => {
        const plan = SP.loadSavedPlan();
        if (!plan) return;
        const dayIndex = parseInt(input.getAttribute("data-day"), 10);
        const taskId = input.getAttribute("data-task");
        SP.toggleTask(plan, dayIndex, taskId);
        const row = input.closest(".study-task");
        if (row) row.classList.toggle("done", input.checked);
        const prog = SP.planProgress(plan);
        const bar = document.querySelector(".study-trail-progress-bar span");
        const label = document.querySelector(".study-trail-progress strong");
        if (bar) bar.style.width = `${prog.pct}%`;
        if (label) label.textContent = `${prog.pct}%`;
      });
    });
  }

  function renderContato() {
    const email = contactEmail();
    const deleteUrl = window.LEX_CONFIG?.accountDeletionUrl || `${location.origin}${location.pathname}#/excluir-conta`;
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
        <p class="contact-alt">
          Para solicitar exclusão da sua conta e dados, acesse
          <a href="${esc(deleteUrl)}">Exclusão de conta</a>.
        </p>
      </div>`;
  }

  function renderExcluirConta() {
    const email = contactEmail();
    const deleteUrl = window.LEX_CONFIG?.accountDeletionUrl || `${location.origin}${location.pathname}#/excluir-conta`;
    return `
      <div class="page-head">
        <h1>Exclusão de conta</h1>
        <p>Solicite a remoção da sua conta NaIntegra Lex e dos dados associados.</p>
      </div>
      <div class="contact-card">
        <h2>Como solicitar</h2>
        <p>Envie um e-mail para <a href="mailto:${esc(email)}?subject=${encodeURIComponent("Exclusão de conta NaIntegra Lex")}">${esc(email)}</a> com o assunto <strong>Exclusão de conta NaIntegra Lex</strong>, informando o e-mail usado no cadastro (Google ou Apple).</p>
        <p>Responderemos em até 7 dias úteis confirmando a exclusão.</p>
        <h2>O que é excluído</h2>
        <ul>
          <li>Cadastro e login (Google/Apple vinculados ao Lex)</li>
          <li>Progresso de leitura, anotações e grifos sincronizados</li>
          <li>Flashcards personalizados e decks criados por você</li>
          <li>Comentários públicos em questões</li>
          <li>Preferências e histórico de uso no app</li>
        </ul>
        <h2>O que pode ser mantido</h2>
        <ul>
          <li>Registros de pagamento e notas fiscais, pelo prazo legal exigido</li>
          <li>Backups de segurança por até 30 dias, apenas para recuperação de incidentes</li>
        </ul>
        <p class="contact-alt">
          Link desta página (para a Play Store): <a href="${esc(deleteUrl)}">${esc(deleteUrl)}</a>
        </p>
        <p><a href="#/contato" class="btn">← Voltar ao contato</a></p>
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

  function bindLanding() {
    document.querySelectorAll("[data-auth-open]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const view = btn.getAttribute("data-auth-open") || "login";
        if (window.LexAuthUI?.scrollToLandingAuth) window.LexAuthUI.scrollToLandingAuth(view);
        else window.LexAuthUI?.open(view);
      });
    });
    document.querySelectorAll("[data-scroll-to]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.preventDefault();
        const id = el.getAttribute("data-scroll-to");
        document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
    const authRoot = document.getElementById("landing-auth-root");
    if (authRoot) window.LexAuthUI?.mountLandingAuth(authRoot, "login");
  }

  function bindFlashcardsList() {
    document.querySelectorAll("[data-deck]").forEach((el) => {
      el.addEventListener("click", (e) => {
        if (e.target.closest(".flash-deck-manage")) return;
        state.flashSession = { idx: 0, flipped: false, stats: { err: 0, mid: 0, ok: 0 } };
        location.hash = `#/flashcards/${el.getAttribute("data-deck")}`;
      });
    });
    document.querySelectorAll(".flash-deck-manage").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const slug = btn.getAttribute("data-manage-deck");
        if (slug) location.hash = `#/flashcards/gerenciar/${encodeURIComponent(slug)}`;
      });
    });
  }

  function reloadDecksFromStorage() {
    const catalog = state.decks.filter((d) => !d.custom);
    state.decks = window.LexFlashcardsUser
      ? window.LexFlashcardsUser.mergeDecks(catalog)
      : catalog;
    refreshSearchIndex();
  }

  function flashImportPreview(text, filename, previewEl) {
    if (!window.LexFlashcardsUser || !previewEl) return [];
    const parsed = window.LexFlashcardsUser.parseImport(text, { filename });
    if (parsed.error) {
      previewEl.hidden = false;
      previewEl.textContent = `Erro ao interpretar (${parsed.format}): ${parsed.error}`;
      previewEl.className = "flash-import-preview flash-import-preview--err";
      return [];
    }
    if (!parsed.count) {
      previewEl.hidden = false;
      previewEl.textContent = "Nenhum card reconhecido neste conteúdo.";
      previewEl.className = "flash-import-preview flash-import-preview--warn";
      return [];
    }
    previewEl.hidden = false;
    previewEl.textContent = `${parsed.count} card${parsed.count === 1 ? "" : "s"} detectado${parsed.count === 1 ? "" : "s"} (formato: ${parsed.format}).`;
    previewEl.className = "flash-import-preview";
    return parsed.cards;
  }

  function bindFlashCreate() {
    const form = document.getElementById("flash-create-form");
    const fileInput = document.getElementById("flash-import-file");
    const textInput = document.getElementById("flash-import-text");
    const preview = document.getElementById("flash-import-preview");
    const errEl = document.getElementById("flash-create-error");
    let importCards = [];

    const refreshPreview = () => {
      const text = textInput?.value?.trim() || "";
      if (!text) {
        importCards = [];
        if (preview) preview.hidden = true;
        return;
      }
      importCards = flashImportPreview(text, fileInput?.files?.[0]?.name || "", preview);
    };

    fileInput?.addEventListener("change", () => {
      const file = fileInput.files?.[0];
      if (!file || !textInput) return;
      const reader = new FileReader();
      reader.onload = () => {
        textInput.value = String(reader.result || "");
        refreshPreview();
      };
      reader.readAsText(file, "UTF-8");
    });

    textInput?.addEventListener("input", refreshPreview);

    form?.addEventListener("submit", (e) => {
      e.preventDefault();
      if (!window.LexFlashcardsUser) return;
      const fd = new FormData(form);
      const name = String(fd.get("name") || "").trim();
      const category = String(fd.get("category") || "Meus decks").trim();
      const manual = window.LexFlashcardsUser.normalizeCard({
        front: fd.get("front"),
        back: fd.get("back"),
        highlight: fd.get("highlight"),
      });
      const cards = [...importCards];
      if (manual) cards.push(manual);
      if (!name) {
        if (errEl) {
          errEl.hidden = false;
          errEl.textContent = "Informe o nome do deck.";
        }
        return;
      }
      if (!cards.length) {
        if (errEl) {
          errEl.hidden = false;
          errEl.textContent = "Importe cards ou preencha pergunta e resposta.";
        }
        return;
      }
      const deck = window.LexFlashcardsUser.createDeck({ name, category, cards });
      reloadDecksFromStorage();
      location.hash = `#/flashcards/gerenciar/${encodeURIComponent(deck.slug)}`;
    });
  }

  function bindFlashManage(slug) {
    const metaForm = document.getElementById("flash-manage-meta");
    const addForm = document.getElementById("flash-add-card");
    const fileInput = document.getElementById("flash-manage-import-file");
    const textInput = document.getElementById("flash-manage-import-text");
    const importBtn = document.getElementById("flash-manage-import-btn");
    const importPreview = document.getElementById("flash-manage-import-preview");

    metaForm?.addEventListener("submit", (e) => {
      e.preventDefault();
      const deck = window.LexFlashcardsUser?.findCustomDeck(slug);
      if (!deck) return;
      const fd = new FormData(metaForm);
      window.LexFlashcardsUser.upsertCustomDeck({
        ...deck,
        name: String(fd.get("name") || deck.name).trim(),
        category: String(fd.get("category") || deck.category).trim(),
      });
      reloadDecksFromStorage();
      render();
    });

    addForm?.addEventListener("submit", (e) => {
      e.preventDefault();
      const fd = new FormData(addForm);
      const card = window.LexFlashcardsUser?.normalizeCard({
        front: fd.get("front"),
        back: fd.get("back"),
        highlight: fd.get("highlight"),
      });
      if (!card) return;
      window.LexFlashcardsUser.appendCards(slug, [card]);
      reloadDecksFromStorage();
      render();
    });

    fileInput?.addEventListener("change", () => {
      const file = fileInput.files?.[0];
      if (!file || !textInput) return;
      const reader = new FileReader();
      reader.onload = () => {
        textInput.value = String(reader.result || "");
      };
      reader.readAsText(file, "UTF-8");
    });

    importBtn?.addEventListener("click", () => {
      const text = textInput?.value?.trim() || "";
      if (!text || !window.LexFlashcardsUser) return;
      const cards = flashImportPreview(text, fileInput?.files?.[0]?.name || "", importPreview);
      if (!cards.length) return;
      window.LexFlashcardsUser.appendCards(slug, cards);
      if (textInput) textInput.value = "";
      reloadDecksFromStorage();
      render();
    });

    document.querySelectorAll(".flash-card-edit").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.getAttribute("data-card-idx"), 10);
        if (Number.isNaN(idx)) return;
        state.flashManageEdit = { slug, idx };
        render();
      });
    });

    document.querySelectorAll(".flash-card-edit-form").forEach((form) => {
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        const idx = parseInt(form.getAttribute("data-card-idx"), 10);
        if (Number.isNaN(idx)) return;
        const fd = new FormData(form);
        const card = window.LexFlashcardsUser?.normalizeCard({
          front: fd.get("front"),
          back: fd.get("back"),
          highlight: fd.get("highlight"),
        });
        if (!card) return;
        window.LexFlashcardsUser.updateCard(slug, idx, card);
        state.flashManageEdit = null;
        reloadDecksFromStorage();
        render();
      });
    });

    document.querySelectorAll(".flash-card-cancel").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.flashManageEdit = null;
        render();
      });
    });

    document.querySelectorAll(".flash-card-delete").forEach((btn) => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.getAttribute("data-card-idx"), 10);
        if (Number.isNaN(idx)) return;
        if (state.flashManageEdit?.slug === slug && state.flashManageEdit?.idx === idx) {
          state.flashManageEdit = null;
        } else if (state.flashManageEdit?.slug === slug && state.flashManageEdit?.idx > idx) {
          state.flashManageEdit = { slug, idx: state.flashManageEdit.idx - 1 };
        }
        window.LexFlashcardsUser?.removeCard(slug, idx);
        reloadDecksFromStorage();
        render();
      });
    });

    document.getElementById("flash-export-deck")?.addEventListener("click", () => {
      const deck = state.decks.find((d) => d.slug === slug);
      if (!deck || !window.LexFlashcardsUser) return;
      const blob = new Blob([window.LexFlashcardsUser.exportDeckJson(deck)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${deck.slug}.json`;
      a.click();
      URL.revokeObjectURL(a.href);
    });

    document.getElementById("flash-delete-deck")?.addEventListener("click", () => {
      if (!window.confirm("Excluir este deck e todos os cards? Esta ação não pode ser desfeita.")) return;
      window.LexFlashcardsUser?.deleteCustomDeck(slug);
      reloadDecksFromStorage();
      location.hash = "#/flashcards";
    });
  }

  function bindFlashSession(slug) {
    const deck = state.decks.find((d) => d.slug === slug);
    if (deck && !deck.cards?.length && window.LexData?.ensureFlashcardDeckHydrated) {
      state.decksHydrating = true;
      render();
      window.LexData.ensureFlashcardDeckHydrated(slug)
        .then(() => {
          state.decksHydrating = false;
          render();
          bindFlashSession(slug);
        })
        .catch((err) => {
          console.warn("Lex: deck hydrate", err);
          state.decksHydrating = false;
          render();
        });
      return;
    }
    const ensureSession = () => {
      if (!state.flashSession) state.flashSession = { idx: 0, flipped: false, stats: { err: 0, mid: 0, ok: 0 } };
      return state.flashSession;
    };
    const fontIdx = () => loadJson(LS.fontSize, 2);

    document.getElementById("flash-edit-current")?.addEventListener("click", () => {
      const s = ensureSession();
      state.flashManageEdit = { slug, idx: s.idx };
    });

    document.getElementById("flash-font-down")?.addEventListener("click", () => {
      saveJson(LS.fontSize, Math.max(0, fontIdx() - 1));
      render();
    });
    document.getElementById("flash-font-up")?.addEventListener("click", () => {
      saveJson(LS.fontSize, Math.min(FONT_SIZES.length - 1, fontIdx() + 1));
      render();
    });

    document.getElementById("flash-prev")?.addEventListener("click", () => {
      const s = ensureSession();
      if (s.idx > 0) {
        s.idx--;
        s.flipped = false;
        render();
      }
    });

    document.getElementById("flash-next")?.addEventListener("click", () => {
      const s = ensureSession();
      if (deck && s.idx < deck.cards.length - 1) {
        s.idx++;
        s.flipped = false;
        render();
      }
    });

    document.getElementById("flash-flip")?.addEventListener("click", () => {
      const s = ensureSession();
      s.flipped = !s.flipped;
      render();
    });

    const card = document.getElementById("flash-card");
    if (card) {
      card.addEventListener("click", () => {
        const s = ensureSession();
        s.flipped = !s.flipped;
        render();
      });
    }

    document.querySelectorAll("[data-rate]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const rate = btn.getAttribute("data-rate");
        const s = ensureSession();
        scheduleFlash(slug, s.idx, rate === "err" ? "err" : rate === "mid" ? "mid" : "ok");
        s.stats[rate === "err" ? "err" : rate === "mid" ? "mid" : "ok"]++;
        s.idx++;
        s.flipped = false;
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
    const doc = findDocument(docId);
    const storageId = doc ? readerStorageId(doc) : readerStorageId(docId);
    const fontIdx = () => loadJson(LS.fontSize, 2);

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
      const prog = readingProgress(storageId);
      const ids = [...new Set([...prog.read, state.reader?.activeArt ?? 0])];
      setReadingProgress(storageId, ids, articles.length);
      renderRecentReads();
      render();
    });

    bindTts(storageId, articles);
  }

  function saveNoteFromTextarea(ta) {
    const docId = ta.getAttribute("data-note-doc");
    const blockKey = ta.getAttribute("data-note-input");
    const docType = ta.getAttribute("data-note-type") || "legislacao";
    setNote(docId, blockKey, ta.value.trim(), docType);
    const btn = ta.closest(".block-note, .flash-note-wrap")?.querySelector("[data-note-toggle]");
    if (btn) btn.classList.toggle("has-note", Boolean(ta.value.trim()));
  }

  function bindInteractionDelegation() {
    const app = document.getElementById("app");
    if (!app || app.dataset.interactionBound) return;
    app.dataset.interactionBound = "1";

    app.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-note-toggle]");
      if (!btn) return;
      e.preventDefault();
      const wrap = btn.closest("[data-note-wrap]");
      const panel = wrap?.querySelector(".block-note-panel");
      if (panel) panel.hidden = !panel.hidden;
    });

    const noteTimers = new WeakMap();
    app.addEventListener("input", (e) => {
      const ta = e.target.closest("[data-note-input]");
      if (!ta) return;
      clearTimeout(noteTimers.get(ta));
      noteTimers.set(
        ta,
        setTimeout(() => saveNoteFromTextarea(ta), 400)
      );
    });

    app.addEventListener(
      "blur",
      (e) => {
        const ta = e.target.closest?.("[data-note-input]");
        if (ta) saveNoteFromTextarea(ta);
      },
      true
    );

    document.addEventListener("mouseup", () => {
      if (!isReaderRoute()) return;
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || !sel.rangeCount) return;
      const anchor = sel.anchorNode;
      const el = anchor?.nodeType === 3 ? anchor.parentElement : anchor;
      const block = el?.closest?.(".article-text");
      if (!block) return;
      const host = block.closest("[data-art-id]");
      if (!host) return;
      const toolbar = document.getElementById("highlight-toolbar");
      if (!toolbar) return;
      const doc = findDocument(state.route.id);
      const artId = host.getAttribute("data-art-id");
      const part = block.getAttribute("data-hl-part") || "";
      const storageId = doc ? readerStorageId(doc) : readerStorageId(state.route.id);
      toolbar.classList.add("visible");
      toolbar.dataset.artId = artId;
      toolbar.dataset.blockKey = highlightBlockKey(artId, part);
      toolbar.dataset.docId = storageId;
      toolbar.dataset.docType = docStudyType(doc);
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
        const blockKey = toolbar.dataset.blockKey || artId;
        const docId = toolbar.dataset.docId;
        const docType = toolbar.dataset.docType || "legislacao";
        const host = document.getElementById(`art-${artId}`);
        const part = blockKey.includes(".") ? blockKey.split(".").slice(1).join(".") : "";
        const block = part
          ? host?.querySelector(`.article-text[data-hl-part="${part}"]`)
          : host?.querySelector(".article-text");
        if (block) setHighlight(docId, blockKey, block.innerHTML, docType);
        toolbar.classList.remove("visible");
        sel.removeAllRanges();
      });
    });
    document.getElementById("hl-note-btn")?.addEventListener("click", () => {
      const artId = toolbar.dataset.artId;
      const blockKey = toolbar.dataset.blockKey || artId;
      const host = document.getElementById(`art-${artId}`);
      const wrap =
        host?.querySelector(`[data-note-wrap="${CSS.escape(blockKey)}"]`) ||
        host?.querySelector("[data-note-wrap]");
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
    if (!state.reader) state.reader = { activeArt: 0, narrating: false, speed: 1, voiceId: selectedTtsVoiceId() };

    const synth = window.speechSynthesis;
    let utter = null;

    function speakArt(i) {
      synth.cancel();
      state.reader.activeArt = i;
      const text = articles[i]?.text;
      if (!text) return;
      utter = new SpeechSynthesisUtterance(text);
      const voiceOpt = resolveTtsVoiceOption(state.reader.voiceId || selectedTtsVoiceId());
      utter.lang = voiceOpt?.voice?.lang || "pt-BR";
      utter.rate = state.reader.speed || 1;
      if (voiceOpt?.pitch) utter.pitch = voiceOpt.pitch;
      if (voiceOpt?.voice) utter.voice = voiceOpt.voice;
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

    function toggleTts() {
      if (state.reader.narrating) {
        synth.cancel();
        state.reader.narrating = false;
      } else {
        state.reader.narrating = true;
        speakArt(state.reader.activeArt || 0);
      }
      render();
    }

    document.querySelectorAll("#tts-toggle, #tts-toggle-header").forEach((btn) => {
      btn.addEventListener("click", toggleTts);
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

    bindTtsVoiceSelects(() => {
      if (state.reader.narrating) speakArt(state.reader.activeArt || 0);
    });
  }

  function bindJurisListToolbar() {
    const fontIdx = () => loadJson(LS.fontSize, 2);
    document.getElementById("juris-list-font-down")?.addEventListener("click", () => {
      saveJson(LS.fontSize, Math.max(0, fontIdx() - 1));
      render();
    });
    document.getElementById("juris-list-font-up")?.addEventListener("click", () => {
      saveJson(LS.fontSize, Math.min(FONT_SIZES.length - 1, fontIdx() + 1));
      render();
    });
  }

  function mountReaderContent(container, docId, backRoute, { embedded = false } = {}) {
    const app = document.getElementById("app");
    const doc = findDocument(docId);
    const reader = renderReader(docId, backRoute, { embedded });
    if (typeof reader === "string") {
      container.innerHTML = reader;
      return null;
    }
    container.innerHTML = reader.html;
    if (readerShowsNarrationPanel(doc)) {
      if (embedded) container.classList.add("juris-reader-embed--panel");
      else app?.classList.add("with-panel");
    } else {
      container.classList.remove("juris-reader-embed--panel");
    }
    bindReader(docId, reader.articles, docStudyType(doc));
    bindReportError();
    bindJurisCloseButtons();
    return reader;
  }

  async function renderJurisprudenciaPage(openDocId) {
    const main = document.getElementById("main");
    const app = document.getElementById("app");
    main?.classList.remove("with-panel");
    app?.classList.remove("with-panel");

    setAppHtml(renderJurisprudencia(openDocId || null));
    bindJuris();
    bindJurisListToolbar();
    bindPageSectionSearch("jurisprudencia");
    bindJurisCloseButtons();

    if (!openDocId) return;

    const embed = document.getElementById("juris-reader-embed");
    const doc = findDocument(openDocId);
    if (!embed) return;

    if (!doc) {
      embed.innerHTML = `<div class="empty">Documento não encontrado.</div>`;
      return;
    }

    trackRecentRead(doc, "jurisprudencia");

    if (!doc.body) {
      embed.innerHTML = `<div class="loading">Carregando precedente…</div>`;
      try {
        await window.LexData.loadDocumentBody(doc);
      } catch (err) {
        console.error(err);
        const detail = err?.message ? `<p class="meta-row"><small>${esc(String(err.message))}</small></p>` : "";
        embed.innerHTML = `<div class="empty">Não foi possível carregar este documento.${detail}</div>`;
        return;
      }
    }

    mountReaderContent(embed, openDocId, "jurisprudencia", { embedded: true });
    requestAnimationFrame(() => {
      document.getElementById("juris-reader-shell")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function bindJurisCloseButtons() {
    document.querySelectorAll("[data-juris-close]").forEach((btn) => {
      if (btn.dataset.jurisCloseBound) return;
      btn.dataset.jurisCloseBound = "1";
      btn.addEventListener("click", () => {
        location.hash = "#/jurisprudencia";
      });
    });
  }

  function bindJuris() {
    document.querySelectorAll("[data-juris-open]").forEach((el) => {
      el.addEventListener("click", (e) => {
        if (e.target.closest("[data-studied], [data-fav], [data-juris-open-btn], button")) return;
        location.hash = docHash("jurisprudencia", el.getAttribute("data-juris-open"));
      });
    });
    document.querySelectorAll("[data-juris-open-btn]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const id = btn.getAttribute("data-juris-open-btn");
        const current = state.route.id;
        if (current && current === id) location.hash = "#/jurisprudencia";
        else location.hash = docHash("jurisprudencia", id);
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

  let questaoCommentsFetchToken = 0;

  async function refreshQuestaoComments(qids) {
    if (!window.LexQuestaoComentarios || !qids?.length) return;
    const token = ++questaoCommentsFetchToken;
    state.questaoCommentsLoading = true;
    try {
      await window.LexQuestaoComentarios.fetchForQuestions(qids);
    } catch (err) {
      console.warn("Lex: comentários questões", err);
    } finally {
      if (token === questaoCommentsFetchToken) {
        state.questaoCommentsLoading = false;
        if (state.route.path === "questoes" || state.route.path === "doutrina") render();
      }
    }
  }

  function bindDoutrina() {
    document.querySelectorAll("[data-doutrina-result]").forEach((btn) => {
      btn.addEventListener("click", () => {
        doutrinaFilterState().result = btn.getAttribute("data-doutrina-result");
        state.doutrinaPage = 1;
        render();
      });
    });
    document.querySelectorAll("[data-doutrina-banca]").forEach((btn) => {
      btn.addEventListener("click", () => {
        doutrinaFilterState().banca = btn.getAttribute("data-doutrina-banca");
        state.doutrinaPage = 1;
        render();
      });
    });
    document.querySelectorAll("[data-doutrina-assunto]").forEach((btn) => {
      btn.addEventListener("click", () => {
        doutrinaFilterState().assunto = btn.getAttribute("data-doutrina-assunto");
        state.doutrinaPage = 1;
        render();
      });
    });
    document.querySelectorAll("[data-doutrina-page]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const dir = btn.getAttribute("data-doutrina-page");
        if (dir === "prev" && state.doutrinaPage > 1) state.doutrinaPage--;
        if (dir === "next") state.doutrinaPage++;
        render();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    });

    if (state.route.path !== "doutrina" || !state.route.id) return;

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
        finalizeQAnswer(qid, findQuestion(qid));
        render();
        document.querySelector(`[id="gab-${CSS.escape(qid)}"]`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      });
    });
    document.querySelectorAll("[data-q-reveal]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const qid = btn.getAttribute("data-q-reveal");
        const qa = qAnswerState(qid);
        qa.revealed = true;
        finalizeQAnswer(qid, findQuestion(qid));
        render();
      });
    });

    document.querySelectorAll(".q-comment-form, .q-comment-edit-form").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const qid = form.getAttribute("data-qid");
        const body = new FormData(form).get("body");
        if (!window.LexAuth?.getSession) return;
        try {
          const session = await window.LexAuth.getSession();
          if (!session?.user) {
            window.LexAuthUI?.open("login");
            return;
          }
          await window.LexQuestaoComentarios.publishComment(qid, body, session);
          state.questaoCommentEdit = null;
          render();
        } catch (err) {
          console.warn("Lex: publicar comentário", err);
          alert("Não foi possível publicar o comentário. Tente novamente.");
        }
      });
    });

    document.querySelectorAll(".q-comment-edit").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.questaoCommentEdit = {
          qid: btn.getAttribute("data-qid"),
          commentId: btn.getAttribute("data-comment-id"),
        };
        render();
      });
    });

    document.querySelectorAll(".q-comment-cancel").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.questaoCommentEdit = null;
        render();
      });
    });

    document.querySelectorAll(".q-comment-delete").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!window.confirm("Excluir seu comentário público?")) return;
        const qid = btn.getAttribute("data-qid");
        const commentId = btn.getAttribute("data-comment-id");
        try {
          const session = await window.LexAuth.getSession();
          if (!session?.access_token) return;
          await window.LexQuestaoComentarios.deleteComment(commentId, qid, session);
          state.questaoCommentEdit = null;
          render();
        } catch (err) {
          console.warn("Lex: excluir comentário", err);
          alert("Não foi possível excluir o comentário.");
        }
      });
    });

    refreshQuestaoComments(state.questaoPageIds);

    const qId = state.route.sub;
    if (qId) {
      const card =
        document.querySelector(`[data-q="${CSS.escape(qId)}"]`) ||
        [...document.querySelectorAll("[data-q]")].find((el) => el.getAttribute("data-q") === qId);
      card?.scrollIntoView({ behavior: "smooth", block: "center" });
      card?.classList.add("search-highlight");
    }
  }

  function bindQuestoes() {
    document.querySelectorAll("[data-q-stats-period]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.qStatsPeriod = btn.getAttribute("data-q-stats-period") || "7d";
        render();
      });
    });
    if (state.route.path === "doutrina") return;

    document.querySelectorAll("[data-q-result]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.qFilter = { ...(state.qFilter || {}), result: btn.getAttribute("data-q-result") };
        state.questionsPage = 1;
        render();
      });
    });
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
        finalizeQAnswer(qid, findQuestion(qid));
        render();
        document.querySelector(`[id="gab-${CSS.escape(qid)}"]`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
      });
    });
    document.querySelectorAll("[data-q-reveal]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const qid = btn.getAttribute("data-q-reveal");
        const qa = qAnswerState(qid);
        qa.revealed = true;
        finalizeQAnswer(qid, findQuestion(qid));
        render();
      });
    });

    document.querySelectorAll(".q-comment-form, .q-comment-edit-form").forEach((form) => {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const qid = form.getAttribute("data-qid");
        const body = new FormData(form).get("body");
        if (!window.LexAuth?.getSession) return;
        try {
          const session = await window.LexAuth.getSession();
          if (!session?.user) {
            window.LexAuthUI?.open("login");
            return;
          }
          await window.LexQuestaoComentarios.publishComment(qid, body, session);
          state.questaoCommentEdit = null;
          render();
        } catch (err) {
          console.warn("Lex: publicar comentário", err);
          alert("Não foi possível publicar o comentário. Tente novamente.");
        }
      });
    });

    document.querySelectorAll(".q-comment-edit").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.questaoCommentEdit = {
          qid: btn.getAttribute("data-qid"),
          commentId: btn.getAttribute("data-comment-id"),
        };
        render();
      });
    });

    document.querySelectorAll(".q-comment-cancel").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.questaoCommentEdit = null;
        render();
      });
    });

    document.querySelectorAll(".q-comment-delete").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!window.confirm("Excluir seu comentário público?")) return;
        const qid = btn.getAttribute("data-qid");
        const commentId = btn.getAttribute("data-comment-id");
        try {
          const session = await window.LexAuth.getSession();
          if (!session?.access_token) return;
          await window.LexQuestaoComentarios.deleteComment(commentId, qid, session);
          state.questaoCommentEdit = null;
          render();
        } catch (err) {
          console.warn("Lex: excluir comentário", err);
          alert("Não foi possível excluir o comentário.");
        }
      });
    });

    refreshQuestaoComments(state.questaoPageIds);

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

    if (!doc.body) {
      setAppHtml(`<div class="loading">Carregando texto…</div>`);
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
    if (readerShowsNarrationPanel(doc)) {
      app?.classList.add("with-panel");
    }
    bindReader(docId, reader.articles, docStudyType(doc));
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
    updatePublicLayout(r.path);

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
      location.hash = "#/";
      return;
    }

    let html = "";

    if (isLandingRoute(r.path)) html = renderHome();
    else if (r.path === "flashcards") {
      if (r.id === "criar") html = renderFlashCreate();
      else if (r.id?.startsWith("gerenciar/")) html = renderFlashManage(r.id.slice("gerenciar/".length));
      else if (r.id) html = renderFlashSession(r.id);
      else html = renderFlashcardsList();
    } else if (r.path === "lei-seca") {
      if (r.id) {
        openReader(r.id, "lei-seca");
        return;
      }
      html = renderLeiSecaList();
    } else if (r.path === "jurisprudencia") {
      renderJurisprudenciaPage(r.id || null);
      return;
    } else if (r.path === "questoes") {
      if (!state.questionsLoaded && !state.questionsLoading) ensureQuestionsLoaded();
      html = renderQuestoes();
    } else if (r.path === "doutrina") {
      if (!state.questionsLoaded && !state.questionsLoading) ensureQuestionsLoaded();
      const disc = r.id ? findDoutrinaDisciplina(r.id) : null;
      html = disc ? renderDoutrinaDisciplina(disc) : renderDoutrina();
    } else if (r.path === "plano-estudos") {
      if (!window.LexStudyPlans && !state.studyPlansModuleLoading) {
        state.studyPlansModuleLoading = true;
        setAppHtml(
          `<div class="page-head"><h1>Plano de estudos</h1><p>Carregando módulo…</p></div><div class="loading">Aguarde…</div>`
        );
        ensureStudyPlansModule().then((ok) => {
          state.studyPlansModuleLoading = false;
          if (!ok) console.warn("Lex: study-plans.js não carregou");
          render();
        });
        return;
      }
      if (!state.questionsLoaded && !state.questionsLoading) ensureQuestionsLoaded();
      html = r.id === "trilha" ? renderStudyTrail() : renderStudyPlanWizard();
    } else if (r.path === "contato") html = renderContato();
    else if (r.path === "excluir-conta") html = renderExcluirConta();
    else html = renderHome();

    setAppHtml(html);

    bindHome();
    bindLanding();
    if (isLandingRoute(r.path) && r.path === "precos") {
      requestAnimationFrame(() => {
        document.getElementById("precos")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
    if (state.subscriptionActive && isLandingRoute(r.path)) {
      const hint = document.getElementById("sync-hint");
      if (hint) hint.hidden = Boolean(window.LexStore?.isLoggedIn?.());
    }
    bindFlashcardsList();
    if (r.path === "flashcards") {
      if (r.id === "criar") bindFlashCreate();
      else if (r.id?.startsWith("gerenciar/")) bindFlashManage(r.id.slice("gerenciar/".length));
      else if (r.id) bindFlashSession(r.id);
    }
    bindLeiSecaList();
    if (r.path !== "jurisprudencia") bindJuris();
    bindQuestoes();
    bindDoutrina();
    bindContactForm();
    bindReportError();
    if (r.path === "plano-estudos") {
      document.getElementById("study-reload-module")?.addEventListener("click", () => {
        state.studyPlansModuleLoading = true;
        studyPlansLoadPromise = null;
        ensureStudyPlansModule().then(() => {
          state.studyPlansModuleLoading = false;
          render();
        });
      });
      if (r.id === "trilha") bindStudyTrail();
      else bindStudyPlanWizard();
    }
    if (r.path === "flashcards" && !r.id) bindPageSectionSearch("flashcards");
    else if (r.path === "lei-seca" && !r.id) bindPageSectionSearch("lei-seca");
    else if (r.path === "questoes") bindPageSectionSearch("questoes");
    else if (r.path === "doutrina" && r.id) bindPageSectionSearch("doutrina");
  }

  function refreshSearchIndex() {
    if (window.LexSearch) {
      window.LexSearch.refresh(state.documents, state.decks);
    }
  }

  function startBackgroundLoads() {
    state.documentsEnriching = true;
    window.LexData.enrichDocuments(state.documents)
      .then((enriched) => {
        state.documents = enriched;
        renderAfterBackgroundUpdate();
      })
      .catch((err) => console.warn("Lex: enriquecimento", err))
      .finally(() => {
        state.documentsEnriching = false;
      });

    state.decksLoading = true;
    state.decksHydrating = false;
    if (window.LexFlashcardsUser) {
      state.decks = window.LexFlashcardsUser.mergeDecks([]);
      refreshSearchIndex();
    }
    render();
    window.LexData.loadFlashcardDecks()
      .then((decks) => {
        state.decks = window.LexFlashcardsUser
          ? window.LexFlashcardsUser.mergeDecks(decks)
          : decks;
        state.decksLoading = false;
        refreshSearchIndex();
        render();
        const hydrate = window.LexData.whenFlashcardsHydrated?.();
        if (hydrate?.then) {
          state.decksHydrating = true;
          render();
          hydrate
            .then((full) => {
              if (!full?.length) return;
              state.decks = window.LexFlashcardsUser
                ? window.LexFlashcardsUser.mergeDecks(full)
                : full;
              refreshSearchIndex();
            })
            .catch((err) => console.warn("Lex: flashcards hydrate", err))
            .finally(() => {
              state.decksHydrating = false;
              render();
            });
        }
      })
      .catch((err) => {
        console.warn("Lex: flashcards", err);
        state.decksLoading = false;
        render();
      });

    window.LexData.loadQuestionsCount?.()
      .then((qCount) => {
        if (qCount != null) {
          state.questionsCount = qCount;
          render();
        }
      })
      .catch(() => {});
  }

  function showOfflineBanner() {
    const src = window.__LEX_DATA_SOURCE || "";
    const offlineSources = new Set([
      "fallback",
      "offline_cache",
      "offline_bundle",
      "offline_summaries",
    ]);
    if (!offlineSources.has(src) && navigator.onLine) return;
    const app = document.getElementById("app");
    if (!app || document.getElementById("lex-offline-banner")) return;
    const offline = !navigator.onLine || offlineSources.has(src);
    const msg = offline
      ? "Modo offline — acervo baixado no aparelho. Login, assinatura e comentários precisam de internet."
      : "Conteúdo em cache local — sincronize online para atualizar o acervo.";
    app.insertAdjacentHTML(
      "afterbegin",
      `<div class="banner-warn lex-offline-banner" id="lex-offline-banner" style="background:#dbeafe;border:1px solid #3b82f6;padding:0.75rem 1rem;margin-bottom:1rem;border-radius:8px;font-size:0.9rem">${msg}</div>`
    );
  }

  async function init() {
    if (location.protocol === "file:") {
      document.getElementById("app").innerHTML =
        `<div class="empty">Abra o Lex via servidor HTTP: <code>python3 preview/serve_preview.py</code> e acesse <code>/web/lex/index.html</code>.</div>`;
      return;
    }

    const promo = new URLSearchParams(location.search).get("promo") === "1";
    if (promo) {
      state.currentUser = {
        id: "promo-demo",
        email: "estudante@demo.com",
        user_metadata: { full_name: "Maria" },
      };
      state.subscriptionActive = true;
      state.subscriptionChecked = true;
    }

    if (window.LexAuthUI) {
      await window.LexAuthUI.init(async (session) => {
        state.currentUser = promo ? state.currentUser : (session?.user ?? null);
        if (window.LexStore) await window.LexStore.setSession(promo ? { user: state.currentUser, access_token: "promo" } : session);
        if (window.LexSubscription) window.LexSubscription.invalidateCache();
        const hint = document.getElementById("sync-hint");
        if (hint) hint.hidden = Boolean(state.currentUser);
        if (!promo) await ensureSubscriptionGate();
        else {
          state.subscriptionActive = true;
          state.subscriptionChecked = true;
        }
        if (state.currentUser && state.subscriptionActive && window.LexProtect && !promo) {
          window.LexProtect.init();
        }
        render();
      });
    }

    window.LexSubscription?.renderSidebarUpdate?.();

    if (!promo) {
      await ensureSubscriptionGate();
    } else {
      state.subscriptionActive = true;
      state.subscriptionChecked = true;
    }
    if (state.subscriptionActive && window.LexProtect && !promo) {
      window.LexProtect.init();
    }

    const r0 = state.route;
    if (!state.subscriptionActive && !isPublicRoute(r0.path)) {
      location.hash = "#/";
    }

    try {
      const documents = await window.LexData.loadDocumentsCatalog();
      state.documents = documents;
      rehydrateQAnswers();
      if (window.LexSearch) {
        window.LexSearch.init();
        window.LexSearch.refresh(documents, []);
      }
    } catch (err) {
      console.error(err);
      document.getElementById("app").innerHTML =
        `<div class="empty">Não foi possível carregar o conteúdo. Verifique sua conexão e tente novamente.</div>`;
      return;
    }
    if (window.__LEX_DATA_SOURCE === "fallback" || !navigator.onLine) {
      showOfflineBanner();
    } else if (
      ["offline_cache", "offline_bundle", "offline_summaries"].includes(window.__LEX_DATA_SOURCE)
    ) {
      showOfflineBanner();
    }
    bindInteractionDelegation();
    bindHighlightToolbar();
    initTtsVoices();
    initQAnswers();
    window.LexFlashcardsUser?.setOnDecksChange?.(() => {
      reloadDecksFromStorage();
      render();
    });
    render();
    startBackgroundLoads();
  }

  window.addEventListener("hashchange", () => {
    state.route = parseRoute();
    if (!state.route.id?.startsWith("gerenciar/")) state.flashManageEdit = null;
    render();
  });

  ensureStudyPlansModule().finally(() => init());
})();
