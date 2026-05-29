/** Busca global — leis, jurisprudência, questões e flashcards. */
(function () {
  const KIND_LABEL = {
    lei: "Lei",
    juris: "Juris",
    questao: "Questão",
    flash: "Flashcard",
  };

  const FILTER_LABELS = [
    ["all", "Tudo"],
    ["lei", "Leis"],
    ["juris", "Juris"],
    ["questao", "Questões"],
    ["flash", "Cards"],
  ];

  let index = [];
  let activeFilter = "all";
  let selectedIdx = -1;

  function norm(text) {
    return String(text || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "");
  }

  function escHtml(s) {
    const el = document.createElement("span");
    el.textContent = s ?? "";
    return el.innerHTML;
  }

  function routeId(doc) {
    return doc.lex_route_id || doc.external_id;
  }

  function org(d) {
    return { ...(d.organized || {}), ...(d.meta || {}) };
  }

  function buildIndex(documents, decks) {
    const items = [];

    for (const d of documents || []) {
      const o = org(d);
      if (d.doc_type === "legislacao") {
        items.push({
          kind: "lei",
          title: d.title || "Legislação",
          subtitle: d.resumo || o.secao_lei_seca || "",
          href: `#/lei-seca/${encodeURIComponent(routeId(d))}`,
          text: [d.title, d.resumo, d.external_id, o.secao_lei_seca].filter(Boolean).join(" "),
        });
      } else if (d.doc_type === "jurisprudencia" || d.doc_type === "sumula") {
        const preview = window.LexFormat ? window.LexFormat.jurisPreview(d) : o.tribunal;
        items.push({
          kind: "juris",
          title: d.title || "Precedente",
          subtitle: preview || o.tribunal || "",
          href: `#/jurisprudencia/${encodeURIComponent(routeId(d))}`,
          text: [d.title, preview, d.resumo, d.body, o.tribunal, d.external_id, d.catalog_kind].filter(Boolean).join(" "),
        });
      } else if (d.doc_type === "questoes_objetivas" || d.doc_type === "questoes_subjetivas") {
        const meta = d.meta || {};
        const materia = o.materia || "";
        const doutrinaSlug =
          materia === "Português" || materia === "Língua Portuguesa"
            ? "portugues"
            : materia === "Raciocínio Lógico"
              ? "raciocinio-logico"
              : materia === "Informática"
                ? "informatica"
                : null;
        const href = doutrinaSlug
          ? `#/doutrina/${doutrinaSlug}?q=${encodeURIComponent(d.external_id)}`
          : `#/questoes?q=${encodeURIComponent(d.external_id)}`;
        items.push({
          kind: "questao",
          title: (d.body || d.title || "Questão").slice(0, 120),
          subtitle: [o.banca, o.cargo, o.materia].filter(Boolean).join(" · "),
          href,
          text: [d.title, d.body, o.banca, o.cargo, o.materia, meta.gabarito].filter(Boolean).join(" "),
        });
      }
    }

    for (const deck of decks || []) {
      items.push({
        kind: "flash",
        title: deck.name,
        subtitle: deck.category || "Deck de flashcards",
        href: `#/flashcards/${encodeURIComponent(deck.slug)}`,
        text: [deck.name, deck.category, deck.slug].filter(Boolean).join(" "),
      });
      (deck.cards || []).forEach((card) => {
        items.push({
          kind: "flash",
          title: String(card.front || "").slice(0, 100),
          subtitle: deck.name,
          href: `#/flashcards/${encodeURIComponent(deck.slug)}`,
          text: [deck.name, card.front, card.back, card.highlight].filter(Boolean).join(" "),
        });
      });
    }

    index = items;
    return items.length;
  }

  function search(query) {
    const q = norm(query.trim());
    if (q.length < 2) return [];
    const tokens = q.split(/\s+/).filter(Boolean);
    return index
      .filter((item) => {
        if (activeFilter !== "all" && item.kind !== activeFilter) return false;
        const hay = norm(item.text);
        return tokens.every((t) => hay.includes(t));
      })
      .slice(0, 24);
  }

  function renderResults(results, root) {
    const panel = root.querySelector(".global-search-panel");
    if (!panel) return;

    if (!results.length) {
      panel.innerHTML = `<div class="global-search-empty">Nenhum resultado encontrado.</div>`;
      panel.hidden = false;
      return;
    }

    panel.innerHTML = results
      .map(
        (r, i) => `
      <button type="button" class="global-search-item ${i === selectedIdx ? "selected" : ""}" data-href="${escHtml(r.href)}" data-idx="${i}">
        <span class="global-search-kind">${escHtml(KIND_LABEL[r.kind] || r.kind)}</span>
        <span class="global-search-item-title">${escHtml(r.title)}</span>
        ${r.subtitle ? `<span class="global-search-item-sub">${escHtml(r.subtitle)}</span>` : ""}
      </button>`
      )
      .join("");
    panel.hidden = false;

    panel.querySelectorAll(".global-search-item").forEach((btn) => {
      btn.addEventListener("click", () => navigate(btn.getAttribute("data-href"), root));
    });
  }

  function navigate(href, root) {
    if (!href) return;
    closePanel(root);
    const input = root.querySelector(".global-search-input");
    if (input) input.blur();
    location.hash = href.replace(/^#/, "#");
  }

  function closePanel(root) {
    const panel = root.querySelector(".global-search-panel");
    if (panel) {
      panel.hidden = true;
      panel.innerHTML = "";
    }
    selectedIdx = -1;
  }

  function mount(root) {
    if (!root || root.dataset.mounted) return;
    root.dataset.mounted = "1";
    root.innerHTML = `
      <div class="global-search-filters">
        ${FILTER_LABELS.map(
          ([k, label]) =>
            `<button type="button" class="global-search-filter ${k === activeFilter ? "active" : ""}" data-filter="${k}">${label}</button>`
        ).join("")}
      </div>
      <div class="global-search-field">
        <input type="search" class="global-search-input" placeholder="Buscar leis, juris, questões, flashcards…" autocomplete="off" enterkeyhint="search" />
      </div>
      <div class="global-search-panel" hidden></div>`;

    const input = root.querySelector(".global-search-input");
    const panel = root.querySelector(".global-search-panel");

    root.querySelectorAll(".global-search-filter").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeFilter = btn.getAttribute("data-filter") || "all";
        root.querySelectorAll(".global-search-filter").forEach((b) => {
          b.classList.toggle("active", b === btn);
        });
        renderResults(search(input.value), root);
      });
    });

    input.addEventListener("input", () => {
      selectedIdx = -1;
      const results = search(input.value);
      if (input.value.trim().length < 2) closePanel(root);
      else renderResults(results, root);
    });

    input.addEventListener("focus", () => {
      if (input.value.trim().length >= 2) renderResults(search(input.value), root);
    });

    input.addEventListener("keydown", (e) => {
      const results = search(input.value);
      if (e.key === "Escape") {
        closePanel(root);
        input.blur();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        selectedIdx = Math.min(selectedIdx + 1, results.length - 1);
        renderResults(results, root);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        selectedIdx = Math.max(selectedIdx - 1, 0);
        renderResults(results, root);
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const pick = results[selectedIdx >= 0 ? selectedIdx : 0];
        if (pick) navigate(pick.href, root);
      }
    });

    document.addEventListener("click", (e) => {
      if (!root.contains(e.target)) closePanel(root);
    });
  }

  function init(rootEl) {
    const root = rootEl || document.getElementById("global-search");
    if (root) mount(root);
  }

  function refresh(documents, decks) {
    const count = buildIndex(documents, decks);
    const root = document.getElementById("global-search");
    const input = root?.querySelector(".global-search-input");
    if (root && input && input.value.trim().length >= 2) {
      renderResults(search(input.value), root);
    }
    return count;
  }

  window.LexSearch = { init, refresh, search, buildIndex };
})();
