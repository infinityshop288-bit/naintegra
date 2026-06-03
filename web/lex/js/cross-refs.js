/**
 * Referências cruzadas: artigos, leis e jurisprudência clicáveis com preview em balão.
 */
(function () {
  const MAX_EXCERPT = 1400;
  const SKIP_PARENT =
    "button,a,script,style,textarea,input,select,.lex-xref,.block-note,.hl-note-btn,[contenteditable=true]";
  const TEXT_HOST = ".article-text,.lei-text,.lei-p-text,.q-enunciado,.q-comentario";

  const CODE_ALIASES = [
    { re: /\bConstituição\s+Federal\b|\bCF\b(?![\w/])/i, urlRe: /constituicao\.htm|constituicao\/constituicao/i },
    { re: /\bCódigo\s+Penal\b|\bCP\b(?![\w/])/i, urlRe: /del2848|cod_pen/i },
    { re: /\bCódigo\s+de\s+Processo\s+Penal\b|\bCPP\b/i, urlRe: /del3689/i },
    { re: /\bCLT\b|\bConsolidação\s+das\s+Leis\s+do\s+Trabalho\b/i, urlRe: /del5452/i },
    { re: /\bCódigo\s+Civil\b|\bCC\b(?![\w/])/i, urlRe: /l10406|2002\/l10406/i },
    { re: /\bCDC\b|\bCódigo\s+de\s+Defesa\s+do\s+Consumidor\b/i, urlRe: /l8078/i },
    { re: /\bCPC\b|\bCódigo\s+de\s+Processo\s+Civil\b/i, urlRe: /l13105/i },
    { re: /\bCTB\b|\bCódigo\s+de\s+Trânsito\b/i, urlRe: /l9503/i },
    { re: /\bECA\b|\bEstatuto\s+da\s+Criança\b/i, urlRe: /l8069/i },
    { re: /\bLei\s+de\s+Drogas\b/i, urlRe: /l11343/i },
    { re: /\bLei\s+Maria\s+da\s+Penha\b/i, urlRe: /l11340/i },
  ];

  let catalog = [];
  let legisByKey = new Map();
  let jurisByKey = new Map();
  let docById = new Map();
  let artMapCache = new Map();
  let popoverEl = null;
  let activeBtn = null;
  let loadToken = 0;

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function normalizeYear(y) {
    const s = String(y || "").replace(/\D/g, "");
    if (s.length === 4) return s;
    if (s.length === 2) return parseInt(s, 10) >= 50 ? `19${s}` : `20${s}`;
    return s;
  }

  function leiKey(num, year) {
    const n = String(num || "").replace(/\D/g, "").replace(/^0+/, "") || "0";
    const y = normalizeYear(year);
    return y ? `${n}:${y}` : n;
  }

  function tribunalNorm(t) {
    const u = String(t || "").toUpperCase();
    if (/STF/.test(u)) return "STF";
    if (/STJ/.test(u)) return "STJ";
    if (/TST/.test(u)) return "TST";
    if (/TSE/.test(u)) return "TSE";
    return u.slice(0, 3) || "STF";
  }

  function registerLegis(key, doc) {
    if (!key || !doc) return;
    const prev = legisByKey.get(key);
    if (!prev || legisRank(doc) < legisRank(prev)) legisByKey.set(key, doc);
  }

  function legisRank(doc) {
    if (doc.source_system === "planalto") return 0;
    if (doc.source_system === "rideel_vademecum") return 1;
    return 2;
  }

  function registerJuris(key, doc) {
    if (!key || !doc) return;
    if (!jurisByKey.has(key)) jurisByKey.set(key, doc);
  }

  function indexLegisDoc(doc) {
    const url = doc.url || doc.doc_key || "";
    const norma = window.LexLegisMeta?.parseNormaFromUrl?.(url, doc.body);
    if (norma?.numero && norma.ano) {
      registerLegis(leiKey(norma.numero.replace(/\./g, ""), norma.ano), doc);
    }
    const title = doc.title || "";
    let m = title.match(/\bLei\s+Complementar\s+(\d[\d.]*)\/(\d{4})/i);
    if (m) registerLegis(leiKey(m[1], m[2]), doc);
    m = title.match(/\b(?:Lei|Decreto-Lei|Decreto)\s+(\d[\d.]*)\/(\d{4})/i);
    if (m) registerLegis(leiKey(m[1], m[2]), doc);

    const rid = doc.lex_route_id || "";
    const rm = rid.match(/^lei-(\d+)$/i);
    if (rm) registerLegis(rm[1], doc);

    for (const alias of CODE_ALIASES) {
      if (alias.urlRe.test(url)) registerLegis(`url:${alias.urlRe.source}`, doc);
    }
    if (/constituicao\.htm|constituicao\/constituicao/i.test(url)) {
      registerLegis("cf", doc);
    }
  }

  function indexJurisDoc(doc) {
    const tribunal = tribunalNorm(doc.organized?.tribunal);
    const title = doc.title || "";
    const rid = (doc.lex_route_id || "").toLowerCase();

    let m = rid.match(/^sumula-(stf|stj|tst|tse)-sv-(\d+)$/);
    if (m) registerJuris(`${m[1].toUpperCase()}:sv:${m[2]}`, doc);

    m = rid.match(/^sumula-(stf|stj|tst|tse)-(\d+)$/);
    if (m) registerJuris(`${m[1].toUpperCase()}:s:${m[2]}`, doc);

    m = rid.match(/^tema-(stf|stj|tst)-(?:rep-)?(\d+)$/);
    if (m) registerJuris(`${m[1].toUpperCase()}:tema:${m[2]}`, doc);

    const sv = title.match(/S[úu]mula\s+Vinculante\s+(?:n[º°.]?\s*)?(\d{1,4})/i);
    if (sv) registerJuris(`${tribunal}:sv:${sv[1]}`, doc);

    const sm = title.match(/S[úu]mula\s+(?:n[º°.]?\s*)?(\d{1,4})/i);
    if (sm && !sv) registerJuris(`${tribunal}:s:${sm[1]}`, doc);

    const tm = title.match(/Tema\s+(?:de\s+)?(?:Repetitivo\s+)?(?:n[º°.]?\s*)?(\d{1,5})/i);
    if (tm) registerJuris(`${tribunal}:tema:${tm[1]}`, doc);
  }

  function setCatalog(documents) {
    catalog = documents || [];
    legisByKey = new Map();
    jurisByKey = new Map();
    docById = new Map();
    artMapCache = new Map();
    for (const doc of catalog) {
      docById.set(doc.external_id, doc);
      if (doc.lex_route_id) docById.set(doc.lex_route_id, doc);
      if (doc.doc_type === "legislacao") indexLegisDoc(doc);
      else if (
        doc.doc_type === "sumula" ||
        doc.doc_type === "jurisprudencia" ||
        doc.catalog_kind === "tema" ||
        doc.catalog_kind === "sumula_individual"
      ) {
        indexJurisDoc(doc);
      }
    }
  }

  function findLegisByKey(key) {
    if (legisByKey.has(key)) return legisByKey.get(key);
    if (key === "cf") return legisByKey.get("cf") || null;
    return null;
  }

  function findLegisByAlias(text) {
    for (const alias of CODE_ALIASES) {
      if (alias.re.test(text)) {
        for (const doc of catalog) {
          if (doc.doc_type !== "legislacao") continue;
          const url = doc.url || doc.doc_key || "";
          if (alias.urlRe.test(url)) return doc;
        }
      }
    }
    return null;
  }

  function findJuris(tribunal, kind, num) {
    const t = tribunalNorm(tribunal);
    const key = `${t}:${kind}:${num}`;
    if (jurisByKey.has(key)) return jurisByKey.get(key);
    for (const [k, doc] of jurisByKey) {
      if (k.endsWith(`:${kind}:${num}`)) return doc;
    }
    return null;
  }

  function artNumFromLabel(label) {
    const m = String(label || "").match(/Art\.?\s*(\d{1,4})/i);
    return m ? parseInt(m[1], 10) : null;
  }

  function getArtMap(doc) {
    if (!doc?.external_id) return new Map();
    if (artMapCache.has(doc.external_id)) return artMapCache.get(doc.external_id);
    const map = new Map();
    window.LexFormat?.ensureFormatted?.(doc);
    const blocks = doc.formatted?.blocks;
    if (blocks) {
      blocks.forEach((b, i) => {
        if (b.type === "artigo") {
          const n = artNumFromLabel(b.label);
          if (n != null) map.set(n, i);
        }
      });
    }
    artMapCache.set(doc.external_id, map);
    return map;
  }

  function shorten(text, max = MAX_EXCERPT) {
    const t = String(text || "").replace(/\s+/g, " ").trim();
    if (t.length <= max) return t;
    return `${t.slice(0, max - 1)}…`;
  }

  function articleExcerpt(doc, artNum) {
    window.LexFormat?.ensureFormatted?.(doc);
    const map = getArtMap(doc);
    const idx = map.get(artNum);
    const blocks = doc.formatted?.blocks;
    if (blocks && idx != null && blocks[idx]) {
      const b = blocks[idx];
      return { title: b.label || `Art. ${artNum}`, text: b.text || "" };
    }
  }

  function jurisItemExcerpt(doc, kind, num) {
    window.LexFormat?.ensureFormatted?.(doc);
    const items = doc.formatted?.items;
    if (!items?.length) {
      const body = doc.body || "";
      return { title: doc.title, text: body.slice(0, MAX_EXCERPT) };
    }
    const n = String(num);
    const hit = items.find((it) => {
      const label = `${it.numero || ""} ${it.tipo || ""}`;
      if (kind === "sv") return /vinculante|SV/i.test(label) && new RegExp(`\\b${n}\\b`).test(label);
      if (kind === "tema") return /tema/i.test(label) && new RegExp(`\\b${n}\\b`).test(label);
      return /s[úu]mula/i.test(label) && new RegExp(`\\b${n}\\b`).test(label);
    });
    if (hit) {
      const text = [hit.ementa, hit.tese, hit.julgado].filter(Boolean).join("\n\n");
      return { title: hit.numero || doc.title, text };
    }
    const first = items[0];
    return {
      title: doc.title,
      text: [first?.ementa, first?.tese].filter(Boolean).join("\n\n") || doc.title,
    };
  }

  function docRoute(doc) {
    if (doc.doc_type === "legislacao") return "lei-seca";
    return "jurisprudencia";
  }

  function docOpenHash(doc, artNum) {
    const id = doc.lex_route_id || doc.external_id;
    let hash = `#/${docRoute(doc)}/${encodeURIComponent(id)}`;
    if (artNum != null) {
      const map = getArtMap(doc);
      const idx = map.get(artNum);
      if (idx != null) hash += `#art-${idx}`;
    }
    return hash;
  }

  function resolvePayload(ref, sourceDoc) {
    const kind = ref.kind;
    if (kind === "art") {
      let doc = ref.docId ? docById.get(ref.docId) : null;
      if (!doc && ref.leiKey) doc = findLegisByKey(ref.leiKey);
      if (!doc && sourceDoc?.doc_type === "legislacao") doc = sourceDoc;
      if (!doc) return null;
      return { type: "legis", doc, artNum: ref.art };
    }
    if (kind === "lei") {
      const doc = findLegisByKey(ref.leiKey);
      if (!doc) return null;
      const artNum = ref.art != null ? parseInt(ref.art, 10) : null;
      return { type: "legis", doc, artNum: Number.isFinite(artNum) ? artNum : null };
    }
    if (kind === "sumula" || kind === "sv" || kind === "tema") {
      const jkind = kind === "sv" ? "sv" : kind === "tema" ? "tema" : "s";
      const doc = findJuris(ref.tribunal, jkind, ref.num);
      if (!doc) return null;
      return { type: "juris", doc, jurisKind: kind, num: ref.num };
    }
    return null;
  }

  function collectMatches(text, sourceDoc) {
    const matches = [];
    const ctx = { lastLei: null, sourceDoc };

    function add(kind, start, end, raw, ref) {
      matches.push({ kind, start, end, raw, ref });
    }

    const patterns = [
      {
        re: /\bS[úu]mula\s+Vinculante\s+(?:n[º°.]?\s*)?(\d{1,4})\b/gi,
        fn(m) {
          const trib = text.slice(Math.max(0, m.index - 20), m.index + m[0].length + 15).match(/\b(STF|STJ)\b/i);
          return { kind: "sv", tribunal: trib ? trib[1] : "STF", num: m[1] };
        },
      },
      {
        re: /\bS[úu]mula\s+(?:n[º°.]?\s*)?(\d{1,4})(?:\s*(?:\/|do|da|de|-)\s*(STF|STJ|TST|TSE))?\b/gi,
        fn(m) {
          const trib = m[2] || text.slice(m.index - 12, m.index).match(/\b(STF|STJ|TST|TSE)\b/i)?.[1] || "STF";
          return { kind: "sumula", tribunal: trib, num: m[1] };
        },
      },
      {
        re: /\bTema\s+(?:de\s+)?(?:Repetitivo\s+)?(?:n[º°.]?\s*)?(\d{1,5})(?:\s*(?:\/|do|da|de|-)\s*(STF|STJ|TST))?\b/gi,
        fn(m) {
          const trib = m[2] || "STF";
          return { kind: "tema", tribunal: trib, num: m[1] };
        },
      },
      {
        re: /\bLei\s+Complementar\s+(?:n[º°.]?\s*)?([\d.]+)\s*\/\s*(\d{2,4})(?:\s*,?\s*art(?:igo)?\.?\s*(\d{1,4}))?/gi,
        fn(m) {
          const key = leiKey(m[1], m[2]);
          ctx.lastLei = key;
          return { kind: "lei", leiKey: key, art: m[3] ? parseInt(m[3], 10) : null };
        },
      },
      {
        re: /\b(?:Lei|Decreto-?Lei)\s+(?:n[º°.]?\s*)?([\d.]+)\s*\/\s*(\d{2,4})(?:\s*,?\s*art(?:igo)?\.?\s*(\d{1,4}))?/gi,
        fn(m) {
          const key = leiKey(m[1], m[2]);
          ctx.lastLei = key;
          return { kind: "lei", leiKey: key, art: m[3] ? parseInt(m[3], 10) : null };
        },
      },
      {
        re: /\bart(?:igo)?\.?\s*(\d{1,4})(?:º|°)?\s+da\s+Constituição(?:\s+Federal)?/gi,
        fn(m) {
          return { kind: "art", leiKey: "cf", art: parseInt(m[1], 10) };
        },
      },
      {
        re: /\b(?:CF|Constituição(?:\s+Federal)?)\s*,?\s*art(?:igo)?\.?\s*(\d{1,4})(?:º|°)?/gi,
        fn(m) {
          return { kind: "art", leiKey: "cf", art: parseInt(m[1], 10) };
        },
      },
      {
        re: /\b(Código Penal|Código de Processo Penal|Constituição Federal|CLT|CDC|CPC|CTB|CP|CPP|CF)\s*,?\s*art(?:igo)?\.?\s*(\d{1,4})(?:º|°)?/gi,
        fn(m) {
          const aliasDoc = findLegisByAlias(m[1]);
          if (/cf/i.test(m[1])) return { kind: "art", leiKey: "cf", art: parseInt(m[2], 10) };
          if (aliasDoc) {
            return {
              kind: "art",
              docId: aliasDoc.lex_route_id || aliasDoc.external_id,
              art: parseInt(m[2], 10),
            };
          }
          return null;
        },
      },
      {
        re: /\bart(?:igo)?\.?\s*(\d{1,4})(?:º|°)?/gi,
        fn(m) {
          if (/\b(n[º°]|lei|decreto)\s*$/i.test(text.slice(Math.max(0, m.index - 8), m.index))) return null;
          const art = parseInt(m[1], 10);
          if (ctx.lastLei) return { kind: "art", leiKey: ctx.lastLei, art };
          if (sourceDoc?.doc_type === "legislacao") {
            return {
              kind: "art",
              docId: sourceDoc.lex_route_id || sourceDoc.external_id,
              art,
            };
          }
          const cf = findLegisByKey("cf");
          if (cf && /constitui/i.test(sourceDoc?.title || "")) return { kind: "art", leiKey: "cf", art };
          return null;
        },
      },
    ];

    for (const { re, fn } of patterns) {
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(text)) !== null) {
        const ref = fn(m);
        if (!ref) continue;
        const payload = resolvePayload(ref, sourceDoc);
        if (!payload) continue;
        add(ref.kind, m.index, m.index + m[0].length, m[0], ref);
      }
    }

    matches.sort((a, b) => a.start - b.start || b.end - a.end - (a.end - a.start));
    const kept = [];
    let end = -1;
    for (const m of matches) {
      if (m.start >= end) {
        kept.push(m);
        end = m.end;
      }
    }
    return kept;
  }

  function encodeRef(ref) {
    return encodeURIComponent(JSON.stringify(ref));
  }

  function linkifyText(text, sourceDoc) {
    const matches = collectMatches(text, sourceDoc);
    if (!matches.length) return text;
    let out = "";
    let pos = 0;
    for (const m of matches) {
      out += esc(text.slice(pos, m.start));
      out += `<button type="button" class="lex-xref" data-xref="${encodeRef(m.ref)}">${esc(m.raw)}</button>`;
      pos = m.end;
    }
    out += esc(text.slice(pos));
    return out;
  }

  function shouldSkipNode(node) {
    let el = node.parentElement;
    while (el) {
      if (el.matches?.(SKIP_PARENT)) return true;
      if (el.classList?.contains("reader-body") || el.classList?.contains("q-enunciado")) break;
      el = el.parentElement;
    }
    return false;
  }

  function wrapTextNode(node, sourceDoc) {
    if (!node.nodeValue?.trim()) return;
    if (shouldSkipNode(node)) return;
    const linked = linkifyText(node.nodeValue, sourceDoc);
    if (linked === esc(node.nodeValue)) return;
    const span = document.createElement("span");
    span.innerHTML = linked;
    node.parentNode?.replaceChild(span, node);
  }

  function enhance(root, sourceDoc) {
    if (!root) return;
    const hosts = root.matches?.(TEXT_HOST) ? [root] : root.querySelectorAll?.(TEXT_HOST);
    if (!hosts?.length) return;
    for (const host of hosts) {
      if (host.dataset.xrefDone) continue;
      host.dataset.xrefDone = "1";
      const walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      for (const n of nodes) wrapTextNode(n, sourceDoc || null);
    }
  }

  function ensurePopover() {
    if (popoverEl) return popoverEl;
    popoverEl = document.createElement("div");
    popoverEl.id = "lex-xref-popover";
    popoverEl.className = "lex-xref-popover";
    popoverEl.hidden = true;
    popoverEl.setAttribute("role", "dialog");
    popoverEl.setAttribute("aria-label", "Referência legal");
    popoverEl.innerHTML = `
      <div class="lex-xref-popover-inner">
        <header class="lex-xref-popover-head">
          <h3 class="lex-xref-popover-title"></h3>
          <button type="button" class="lex-xref-popover-close" aria-label="Fechar">×</button>
        </header>
        <div class="lex-xref-popover-body"></div>
        <footer class="lex-xref-popover-foot">
          <a class="btn sm primary lex-xref-popover-open" href="#">Abrir documento</a>
        </footer>
      </div>`;
    document.body.appendChild(popoverEl);
    popoverEl.querySelector(".lex-xref-popover-close")?.addEventListener("click", closePopover);
    document.addEventListener(
      "click",
      (e) => {
        if (!popoverEl || popoverEl.hidden) return;
        if (popoverEl.contains(e.target) || e.target.closest?.(".lex-xref")) return;
        closePopover();
      },
      true
    );
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closePopover();
    });
    return popoverEl;
  }

  function positionPopover(btn) {
    const pop = ensurePopover();
    const rect = btn.getBoundingClientRect();
    const margin = 8;
    pop.hidden = false;
    pop.style.visibility = "hidden";
    pop.style.left = "0";
    pop.style.top = "0";
    const pw = pop.offsetWidth;
    const ph = pop.offsetHeight;
    let left = rect.left + rect.width / 2 - pw / 2;
    let top = rect.bottom + margin;
    left = Math.max(margin, Math.min(left, window.innerWidth - pw - margin));
    if (top + ph > window.innerHeight - margin) {
      top = rect.top - ph - margin;
    }
    if (top < margin) top = margin;
    pop.style.left = `${Math.round(left)}px`;
    pop.style.top = `${Math.round(top)}px`;
    pop.style.visibility = "";
  }

  function closePopover() {
    if (popoverEl) popoverEl.hidden = true;
    activeBtn?.classList.remove("lex-xref-active");
    activeBtn = null;
    loadToken += 1;
  }

  async function loadPreview(resolved) {
    const doc = resolved.doc;
    if (!doc.body?.trim() && window.LexData?.loadDocumentBody) {
      await window.LexData.loadDocumentBody(doc);
    }
    window.LexFormat?.ensureFormatted?.(doc);

    if (resolved.type === "legis") {
      if (resolved.artNum != null) {
        const ex = articleExcerpt(doc, resolved.artNum);
        if (ex) return { title: `${doc.title} — ${ex.title}`, text: ex.text, hash: docOpenHash(doc, resolved.artNum) };
      }
      const ementa = doc.formatted?.ementa || doc.resumo || "";
      return { title: doc.title, text: ementa || "Abra o documento para ler o texto completo.", hash: docOpenHash(doc) };
    }

    const jk = resolved.jurisKind === "sv" ? "sv" : resolved.jurisKind === "tema" ? "tema" : "s";
    const ex = jurisItemExcerpt(doc, jk, resolved.num);
    return { title: ex.title || doc.title, text: ex.text, hash: docOpenHash(doc) };
  }

  async function openPopover(btn, sourceDoc) {
    let ref;
    try {
      ref = JSON.parse(decodeURIComponent(btn.getAttribute("data-xref") || ""));
    } catch {
      return;
    }
    const resolved = resolvePayload(ref, sourceDoc);
    if (!resolved) return;

    const pop = ensurePopover();
    const titleEl = pop.querySelector(".lex-xref-popover-title");
    const bodyEl = pop.querySelector(".lex-xref-popover-body");
    const linkEl = pop.querySelector(".lex-xref-popover-open");
    if (titleEl) titleEl.textContent = "Carregando…";
    if (bodyEl) bodyEl.innerHTML = `<p class="lex-xref-loading">Buscando texto…</p>`;
    if (linkEl) linkEl.href = "#";

    activeBtn?.classList.remove("lex-xref-active");
    activeBtn = btn;
    btn.classList.add("lex-xref-active");
    positionPopover(btn);

    const token = ++loadToken;
    try {
      const preview = await loadPreview(resolved);
      if (token !== loadToken) return;
      if (titleEl) titleEl.textContent = preview.title;
      if (bodyEl) {
        const chunks = String(preview.text || "")
          .split(/\n{2,}/)
          .map((p) => p.trim())
          .filter(Boolean);
        bodyEl.innerHTML = chunks.length
          ? chunks.map((p) => `<p>${esc(shorten(p, 700))}</p>`).join("")
          : `<p class="muted">Trecho indisponível offline. Use <strong>Abrir documento</strong>.</p>`;
      }
      if (linkEl) linkEl.href = preview.hash || "#";
    } catch (err) {
      console.warn("Lex xref:", err);
      if (token !== loadToken) return;
      if (titleEl) titleEl.textContent = "Referência";
      if (bodyEl) bodyEl.innerHTML = `<p class="muted">Não foi possível carregar o trecho. Tente abrir o documento completo.</p>`;
      if (linkEl && resolved.doc) linkEl.href = docOpenHash(resolved.doc, resolved.artNum);
    }
  }

  let clickBound = false;

  function bindClicks(getSourceDoc) {
    if (clickBound) return;
    clickBound = true;
    document.addEventListener("click", (e) => {
      const btn = e.target.closest?.(".lex-xref");
      if (!btn) return;
      e.preventDefault();
      e.stopPropagation();
      const root = btn.closest(".reader-body,.q-card,.study-inline-reader");
      const sourceDoc = getSourceDoc?.() || null;
      openPopover(btn, sourceDoc);
    });
  }

  window.LexCrossRefs = {
    setCatalog,
    enhance,
    enhanceReader(root, sourceDoc) {
      if (!root) return;
      (root.matches?.(TEXT_HOST) ? [root] : root.querySelectorAll?.(TEXT_HOST) || []).forEach((el) => {
        delete el.dataset.xrefDone;
      });
      enhance(root, sourceDoc);
    },
    bind(getSourceDoc) {
      bindClicks(getSourceDoc);
    },
    close: closePopover,
  };
})();
