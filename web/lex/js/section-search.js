/** Busca por tema nas páginas de listagem (Cards, Lei Seca, Juris, Questões). */
(function () {
  function norm(text) {
    return String(text || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function sectionInput(section) {
    return document.querySelector(`.section-search-input[data-section="${section}"]`);
  }

  function tokens(query) {
    const q = norm(query.trim());
    if (q.length < 2) return [];
    return q.split(/\s+/).filter(Boolean);
  }

  function matches(query, text) {
    const toks = tokens(query);
    if (!toks.length) return true;
    const hay = norm(text);
    return toks.every((t) => hay.includes(t));
  }

  function escAttr(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;");
  }

  function bar(section, value, placeholder) {
    const ph = placeholder || "Buscar por tema…";
    return `
      <div class="section-search" data-section="${escAttr(section)}">
        <input
          type="search"
          class="section-search-input"
          data-section="${escAttr(section)}"
          value="${escAttr(value || "")}"
          placeholder="${escAttr(ph)}"
          autocomplete="off"
          enterkeyhint="search"
        />
        <span class="section-search-meta" data-section-meta="${escAttr(section)}"></span>
      </div>`;
  }

  function applyFilter(scopeEl, query) {
    if (!scopeEl) return { visible: 0, total: 0 };
    const items = scopeEl.querySelectorAll("[data-search-text]");
    let visible = 0;
    items.forEach((el) => {
      const ok = matches(query, el.getAttribute("data-search-text") || "");
      el.hidden = !ok;
      if (ok) visible += 1;
    });

    scopeEl.querySelectorAll("[data-search-group]").forEach((group) => {
      const groupItems = group.querySelectorAll("[data-search-text]");
      const anyVisible = [...groupItems].some((el) => !el.hidden);
      group.hidden = groupItems.length > 0 && !anyVisible;
    });

    const section = scopeEl.getAttribute("data-section-scope");
    const meta = section ? document.querySelector(`[data-section-meta="${section}"]`) : scopeEl.querySelector("[data-section-meta]");
    if (meta) {
      const toks = tokens(query);
      if (!toks.length) {
        meta.textContent = "";
        meta.hidden = true;
      } else {
        meta.textContent = visible
          ? `${visible} resultado${visible === 1 ? "" : "s"}`
          : "Nenhum resultado";
        meta.hidden = false;
      }
    }

    const empty = scopeEl.querySelector("[data-section-empty]");
    if (empty) empty.hidden = visible > 0 || !tokens(query).length;

    return { visible, total: items.length };
  }

  function bind(scopeEl, section, onQueryChange) {
    if (!scopeEl) return;
    const input = sectionInput(section);
    if (!input || input.dataset.bound) return;
    input.dataset.bound = "1";

    let hashTimer;
    input.addEventListener("input", () => {
      applyFilter(scopeEl, input.value);
      clearTimeout(hashTimer);
      hashTimer = setTimeout(() => {
        if (onQueryChange) onQueryChange(input.value);
      }, 450);
    });

    if (input.value.trim().length >= 2) applyFilter(scopeEl, input.value);
  }

  function deckText(deck) {
    const cards = deck.cards || [];
    return [
      deck.name,
      deck.category,
      deck.slug,
      ...cards.flatMap((c) => [c.front, c.back, c.highlight]),
    ]
      .filter(Boolean)
      .join(" ");
  }

  function lawText(d, orgFn) {
    const o = orgFn(d);
    return [d.title, d.resumo, o.secao_lei_seca, ...(o.tags_incidencia || []), d.external_id]
      .filter(Boolean)
      .join(" ");
  }

  function jurisText(d, orgFn) {
    const o = orgFn(d);
    const preview = window.LexFormat ? window.LexFormat.jurisPreview(d) : "";
    return [d.title, preview, o.tribunal, o.materia, d.catalog_kind, d.body, d.external_id]
      .filter(Boolean)
      .join(" ");
  }

  function questaoText(d, orgFn) {
    const o = orgFn(d);
    const meta = d.meta || {};
    return [d.title, d.body, o.banca, o.cargo, o.materia, o.ano, meta.gabarito, meta.comentario]
      .filter(Boolean)
      .join(" ");
  }

  window.LexSectionSearch = {
    norm,
    tokens,
    matches,
    bar,
    bind,
    applyFilter,
    sectionInput,
    deckText,
    lawText,
    jurisText,
    questaoText,
  };
})();
