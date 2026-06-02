/**
 * Busca permanente no topo — localizar texto na página (como Ctrl+F).
 * Nas listagens, sincroniza com LexSectionSearch quando existir.
 */
(function () {
  const MIN_LEN = 2;
  let rootEl = null;
  let inputEl = null;
  let metaEl = null;
  let marks = [];
  let currentIdx = -1;
  let debounceTimer = null;

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

  function readerBody() {
    return (
      document.querySelector("#reader-body") ||
      document.querySelector(".study-inline-reader-body") ||
      document.querySelector(".juris-reader-embed .reader-body")
    );
  }

  function findTarget() {
    const reader = readerBody();
    if (reader) return reader;
    const scope = sectionScope();
    if (scope) return scope;
    return contentRoot();
  }

  function shouldSkipNode(node) {
    const p = node.parentElement;
    if (!p) return true;
    if (p.closest(".page-find, .global-search, .global-search-panel, .highlight-toolbar, .sidebar, .mobile-nav, #auth-modal-root")) {
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

  function updateMeta() {
    if (!metaEl) return;
    const q = inputEl?.value?.trim() || "";
    if (sectionScope() && tokens(q).length) {
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
    const query = inputEl?.value?.trim() || "";
    const toks = tokens(query);
    if (!toks.length) {
      clearMarks();
      syncSectionSearch("");
      updateMeta();
      return;
    }

    const usedSection = syncSectionSearch(query);
    const target = findTarget();
    if (!usedSection || readerBody()) {
      highlightIn(target, query);
      scrollToMark(0);
    } else {
      clearMarks();
      currentIdx = -1;
      updateMeta();
    }
  }

  function step(delta) {
    const query = inputEl?.value?.trim() || "";
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
    if (inputEl) inputEl.value = "";
    clearMarks();
    syncSectionSearch("");
    updateMeta();
    if (metaEl) metaEl.hidden = true;
  }

  function mount(host) {
    if (!host || host.dataset.mounted) return;
    host.dataset.mounted = "1";
    host.innerHTML = `
      <div class="page-find-inner" role="search" aria-label="Buscar no texto da página">
        <span class="page-find-label">Buscar</span>
        <input
          type="search"
          class="page-find-input"
          id="page-find-input"
          placeholder="Localizar no texto…"
          autocomplete="off"
          enterkeyhint="search"
          aria-controls="page-find-meta"
        />
        <span class="page-find-meta" id="page-find-meta" hidden></span>
        <button type="button" class="page-find-btn" data-page-find-prev title="Ocorrência anterior" aria-label="Anterior">‹</button>
        <button type="button" class="page-find-btn" data-page-find-next title="Próxima ocorrência" aria-label="Próxima">›</button>
        <button type="button" class="page-find-btn page-find-clear" data-page-find-clear title="Limpar busca" aria-label="Limpar">×</button>
      </div>`;

    inputEl = host.querySelector(".page-find-input");
    metaEl = host.querySelector(".page-find-meta");

    inputEl.addEventListener("input", () => {
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

  function init(hostEl) {
    rootEl = hostEl || document.getElementById("page-find");
    if (rootEl) mount(rootEl);

    if (!document.documentElement.dataset.pageFindKeybound) {
      document.documentElement.dataset.pageFindKeybound = "1";
      document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "f") {
          const t = e.target;
          if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
          e.preventDefault();
          inputEl?.focus();
          inputEl?.select();
        }
      });
    }
  }

  function onContentUpdate() {
    const q = inputEl?.value?.trim() || "";
    if (tokens(q).length) runFind();
    else clearMarks();
  }

  function getQuery() {
    return inputEl?.value?.trim() || "";
  }

  function setQuery(q) {
    if (!inputEl) return;
    inputEl.value = q || "";
    runFind();
  }

  window.LexPageFind = {
    init,
    clear,
    runFind,
    onContentUpdate,
    getQuery,
    setQuery,
    focus: () => {
      inputEl?.focus();
      inputEl?.select();
    },
  };
})();
