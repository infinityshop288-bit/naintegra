/**
 * Busca permanente — localizar qualquer palavra no conteúdo aberto (lei, juris, questão, lista).
 */
(function () {
  const MIN_LEN = 2;
  let metaEl = null;
  let marks = [];
  let currentIdx = -1;
  let debounceTimer = null;
  const inputs = new Set();

  function norm(text) {
    return String(text || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function tokens(query) {
    const q = norm(query.trim());
    if (q.length < MIN_LEN) return [];
    return q.split(/\s+/).filter(Boolean);
  }

  function contentRoot() {
    return document.getElementById("app") || document.querySelector(".content");
  }

  function sectionScope() {
    return document.querySelector("[data-section-scope]");
  }

  /** Leitor de lei/juris aberto (página cheia, embed ou plano de estudos). */
  function openDocumentScope() {
    const candidates = [
      document.getElementById("reader-body"),
      document.querySelector("#juris-reader-embed .reader-body"),
      document.querySelector(".juris-reader-embed .reader-body"),
      document.querySelector(".study-inline-reader-body"),
      document.querySelector(".study-inline-reader-host .reader-body"),
    ];
    for (const el of candidates) {
      if (el && el.textContent?.trim()) return el;
    }
    return null;
  }

  function readerBody() {
    return openDocumentScope();
  }

  function findTarget() {
    const doc = openDocumentScope();
    if (doc) return doc;
    const scope = sectionScope();
    if (scope) return scope;
    return contentRoot();
  }

  function shouldSkipNode(node) {
    const p = node.parentElement;
    if (!p) return true;
    if (
      p.closest(
        ".page-find, .reader-find, .global-search, .global-search-panel, .highlight-toolbar, .sidebar, .mobile-nav, #auth-modal-root"
      )
    ) {
      return true;
    }
    if (p.closest("[hidden], [aria-hidden='true']")) return true;
    const tag = p.tagName;
    if (["SCRIPT", "STYLE", "NOSCRIPT", "INPUT", "TEXTAREA", "SELECT", "BUTTON"].includes(tag)) return true;
    if (p.classList.contains("lex-page-find-mark")) return true;
    return false;
  }

  function clearMarks() {
    for (const mark of marks) {
      const parent = mark.parentNode;
      if (!parent) continue;
      parent.replaceChild(document.createTextNode(mark.textContent), mark);
      parent.normalize();
    }
    marks = [];
    currentIdx = -1;
  }

  function buildHighlightPattern(query) {
    const toks = tokens(query);
    if (!toks.length) return null;
    const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    try {
      return new RegExp(toks.map(esc).join("|"), "gi");
    } catch {
      return null;
    }
  }

  function wrapTextNode(node, re) {
    const text = node.textContent;
    if (!text || !re.test(text)) {
      re.lastIndex = 0;
      return;
    }
    re.lastIndex = 0;
    const frag = document.createDocumentFragment();
    let last = 0;
    let m;
    while ((m = re.exec(text)) !== null) {
      if (m.index > last) frag.appendChild(document.createTextNode(text.slice(last, m.index)));
      const mark = document.createElement("mark");
      mark.className = "lex-page-find-mark";
      mark.textContent = m[0];
      frag.appendChild(mark);
      marks.push(mark);
      last = m.index + m[0].length;
      if (m[0].length === 0) re.lastIndex += 1;
    }
    if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
    node.parentNode.replaceChild(frag, node);
  }

  function highlightIn(container, query) {
    clearMarks();
    const re = buildHighlightPattern(query);
    if (!re || !container) return;
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) {
      if (!shouldSkipNode(walker.currentNode)) nodes.push(walker.currentNode);
    }
    for (const node of nodes) wrapTextNode(node, re);
  }

  function syncSectionSearch(query) {
    const scope = sectionScope();
    const SS = window.LexSectionSearch;
    if (!scope || !SS) return false;
    const section = scope.getAttribute("data-section-scope");
    if (!section) return false;
    const sectionInput = SS.sectionInput(section);
    if (sectionInput && sectionInput.value !== query) sectionInput.value = query;
    SS.applyFilter(scope, query);
    return true;
  }

  function primaryInput() {
    return document.getElementById("page-find-input") || inputs.values().next().value;
  }

  function getQuery() {
    return primaryInput()?.value?.trim() || "";
  }

  function syncAllInputs(value, source) {
    for (const inp of inputs) {
      if (inp !== source && inp.value !== value) inp.value = value;
    }
  }

  function updatePlaceholders() {
    const inDoc = Boolean(openDocumentScope());
    const ph = inDoc ? "Buscar neste documento…" : "Buscar nesta página…";
    for (const inp of inputs) inp.placeholder = ph;
  }

  function updateMeta() {
    if (!metaEl) metaEl = document.getElementById("page-find-meta");
    const q = getQuery();
    if (!metaEl) return;
    if (!openDocumentScope() && sectionScope() && tokens(q).length) {
      const meta = document.querySelector(
        `[data-section-meta="${sectionScope().getAttribute("data-section-scope")}"]`
      );
      if (meta && !meta.hidden && meta.textContent) {
        metaEl.textContent = meta.textContent;
        metaEl.hidden = false;
        return;
      }
    }
    if (!marks.length) {
      metaEl.textContent = tokens(q).length ? "Nenhuma ocorrência" : "";
      metaEl.hidden = !tokens(q).length;
      return;
    }
    metaEl.textContent = `${currentIdx + 1} / ${marks.length}`;
    metaEl.hidden = false;
    document.querySelectorAll("[data-reader-find-meta]").forEach((el) => {
      el.textContent = metaEl.textContent;
      el.hidden = metaEl.hidden;
    });
  }

  function scrollToMark(idx) {
    if (!marks.length) {
      updateMeta();
      return;
    }
    currentIdx = ((idx % marks.length) + marks.length) % marks.length;
    marks.forEach((m, i) => m.classList.toggle("lex-page-find-current", i === currentIdx));
    marks[currentIdx].scrollIntoView({ behavior: "smooth", block: "center" });
    updateMeta();
  }

  function runFind() {
    const query = getQuery();
    const toks = tokens(query);
    if (!toks.length) {
      clearMarks();
      if (!openDocumentScope()) syncSectionSearch("");
      updateMeta();
      return;
    }

    const docScope = openDocumentScope();
    if (docScope) {
      highlightIn(docScope, query);
      scrollToMark(0);
      updateMeta();
      return;
    }

    const usedSection = syncSectionSearch(query);
    const target = findTarget();
    if (!usedSection) {
      highlightIn(target, query);
      scrollToMark(0);
    } else {
      clearMarks();
      currentIdx = -1;
      updateMeta();
    }
  }

  function step(delta) {
    const query = getQuery();
    if (!tokens(query).length) return;
    if (marks.length) {
      scrollToMark(currentIdx + delta);
      return;
    }
    if (typeof window.find === "function") {
      window.find(query, false, delta < 0, false, false, false, false);
    }
  }

  function clear() {
    syncAllInputs("", null);
    clearMarks();
    syncSectionSearch("");
    updateMeta();
    if (metaEl) metaEl.hidden = true;
    document.querySelectorAll("[data-reader-find-meta]").forEach((el) => {
      el.hidden = true;
    });
  }

  function bindInput(inputEl, host, { compact = false } = {}) {
    if (!inputEl || inputs.has(inputEl)) return;
    inputs.add(inputEl);

    inputEl.addEventListener("input", () => {
      syncAllInputs(inputEl.value, inputEl);
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(runFind, 120);
    });

    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        clear();
        inputEl.blur();
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (e.shiftKey) step(-1);
        else step(1);
      }
    });

    host.querySelector("[data-page-find-prev]")?.addEventListener("click", () => step(-1));
    host.querySelector("[data-page-find-next]")?.addEventListener("click", () => step(1));
    host.querySelector("[data-page-find-clear]")?.addEventListener("click", () => {
      clear();
      inputEl.focus();
    });
  }

  function findHtml({ compact = false, inputId = "page-find-input", metaId = "page-find-meta" } = {}) {
    const label = compact ? "" : `<span class="page-find-label">Buscar</span>`;
    const metaAttr = compact ? "data-reader-find-meta" : `id="${metaId}"`;
    return `
      <div class="page-find-inner ${compact ? "page-find-inner--compact" : ""}" role="search" aria-label="Buscar no texto aberto">
        ${label}
        <input
          type="search"
          class="page-find-input"
          id="${compact ? "" : inputId}"
          placeholder="Buscar nesta página…"
          autocomplete="off"
          enterkeyhint="search"
          aria-controls="${metaId}"
        />
        <span class="page-find-meta" ${metaAttr} hidden></span>
        <button type="button" class="page-find-btn" data-page-find-prev title="Anterior" aria-label="Anterior">‹</button>
        <button type="button" class="page-find-btn" data-page-find-next title="Próxima" aria-label="Próxima">›</button>
        <button type="button" class="page-find-btn page-find-clear" data-page-find-clear title="Limpar" aria-label="Limpar">×</button>
      </div>`;
  }

  function mount(host, opts = {}) {
    if (!host || host.dataset.mounted) return;
    host.dataset.mounted = "1";
    host.innerHTML = findHtml(opts);
    const inputEl = host.querySelector(".page-find-input");
    if (!opts.compact && inputEl) inputEl.id = "page-find-input";
    if (!opts.compact) metaEl = host.querySelector("#page-find-meta");
    bindInput(inputEl, host, opts);
    updatePlaceholders();
    const q = getQuery();
    if (tokens(q).length) runFind();
  }

  function mountReaderHost(container) {
    const host = container?.querySelector?.("[data-reader-find-host]");
    if (!host) return;
    mount(host, { compact: true });
    updatePlaceholders();
    const q = getQuery();
    if (tokens(q).length) runFind();
  }

  function init(hostEl) {
    const top = hostEl || document.getElementById("page-find");
    if (top) mount(top);

    if (!document.documentElement.dataset.pageFindKeybound) {
      document.documentElement.dataset.pageFindKeybound = "1";
      document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
          const t = e.target;
          if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
          e.preventDefault();
          const inp = primaryInput();
          inp?.focus();
          inp?.select();
        }
      });
    }
  }

  function onContentUpdate() {
    updatePlaceholders();
    document.querySelectorAll("[data-reader-find-host]").forEach((host) => {
      if (!host.dataset.mounted) mount(host, { compact: true });
    });
    const q = getQuery();
    if (tokens(q).length) runFind();
    else clearMarks();
  }

  function setQuery(q) {
    syncAllInputs(q || "", null);
    runFind();
  }

  window.LexPageFind = {
    init,
    clear,
    runFind,
    onContentUpdate,
    mountReaderHost,
    getQuery,
    setQuery,
    focus: () => {
      const inp = primaryInput();
      inp?.focus();
      inp?.select();
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => init());
  } else {
    init();
  }
})();
