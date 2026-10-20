/**
 * Provas jurídicas — juiz, promotor, defensor e procurador de Estado (últimos 2 anos).
 * Mostra gabarito da banca, resposta da IA, dispositivo legal integral e jurisprudência.
 */
(function () {
  const CAREERS = [
    { id: "all", label: "Todas as carreiras" },
    { id: "juiz", label: "Juiz" },
    { id: "promotor", label: "Promotor" },
    { id: "defensor", label: "Defensor" },
    { id: "procurador", label: "Procurador de Estado" },
  ];
  const TIPOS = [
    { id: "all", label: "Objetivas e subjetivas" },
    { id: "questoes_objetivas", label: "Objetivas" },
    { id: "questoes_subjetivas", label: "Subjetivas" },
  ];

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function md(text) {
    const raw = String(text || "").trim();
    if (!raw) return "<p>—</p>";
    const html = raw
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/^### (.+)$/gm, "<h3>$1</h3>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\n\n/g, "</p><p>")
      .replace(/\n/g, "<br>");
    return `<p>${html}</p>`;
  }

  function parseAlts(meta) {
    return window.LexData?.parseAlternativas?.(meta?.alternativas) || [];
  }

  function gabaritoKey(gabarito, alts) {
    const g = String(gabarito || "").trim().toUpperCase();
    if (!g) return "";
    if (/^[A-E]$/.test(g)) return g;
    const hit = alts.find((a) => g.includes(a.key));
    return hit ? hit.key : g.slice(0, 1);
  }

  async function load() {
    const url = window.LEX_CONFIG?.provasJuridicasFallback || "./data/provas_juridicas.json";
    const res = await fetch(url);
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    return data.documents || [];
  }

  function renderCard(d, ctx) {
    const meta = d.meta || {};
    const o = d.organized || {};
    const alts = parseAlts(meta);
    const isObj = d.doc_type === "questoes_objetivas" && alts.length;
    const qid = d.external_id;
    const qa = ctx.qAnswerState(qid);
    const correctKey = isObj ? gabaritoKey(meta.gabarito_banca, alts) : "";
    const acertou = isObj && qa.revealed && qa.correct === true;
    const errou = isObj && qa.revealed && qa.correct === false;

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
              return `<button type="button" class="${cls}" data-pj-id="${esc(qid)}" data-alt-key="${esc(a.key)}" ${
                qa.revealed ? "disabled" : ""
              }><span class="q-alt-key">${esc(a.key)})</span><span class="q-alt-text">${esc(a.text)}</span></button>`;
            })
            .join("")}
        </div>
        ${
          !qa.revealed
            ? `<button type="button" class="btn primary q-check-btn" data-pj-check="${esc(qid)}" ${
                qa.pick ? "" : "disabled"
              }>Conferir resposta</button>`
            : `<div class="q-result ${acertou ? "ok" : "err"}">${
                acertou ? "✓ Você acertou!" : "✗ Você errou."
              }${correctKey ? ` Gabarito da banca: <strong>${esc(correctKey)}</strong>.` : ""}</div>`
        }`;
    }

    const cargos = (d.carreiras_prova || []).map((c) => CAREERS.find((x) => x.id === c)?.label || c);
    const dispositivos = meta.dispositivos || [];
    const juris = meta.jurisprudencia || [];

    return `
      <article class="question-card prova-card ${acertou ? "question-card-ok" : errou ? "question-card-err" : ""}" data-q="${esc(qid)}">
        <div class="meta-row">
          ${o.banca ? `<span class="tag">${esc(o.banca)} ${esc(o.ano || "")}</span>` : ""}
          ${cargos.map((c) => `<span class="tag">${esc(c)}</span>`).join("")}
          ${o.materia ? `<span class="tag">${esc(o.materia)}</span>` : ""}
          <span class="tag">${isObj ? "Objetiva" : "Subjetiva"}</span>
        </div>
        <p class="q-enunciado">${esc(d.body || d.title)}</p>
        ${altsHtml}
        ${
          !isObj
            ? `<button type="button" class="btn primary" data-pj-reveal="${esc(qid)}" ${
                qa.revealed ? "hidden" : ""
              }>Ver gabarito da banca e resposta da IA</button>`
            : ""
        }
        <div class="gabarito-panel prova-respostas" ${qa.revealed ? "" : "hidden"}>
          <section class="prova-bloco">
            <h3>Gabarito da banca</h3>
            ${
              isObj && correctKey
                ? `<p>Alternativa <strong>${esc(correctKey)}</strong>.</p>`
                : ""
            }
            <p>${esc(meta.resposta_banca || "A banca não divulgou espelho textual além do gabarito.")}</p>
          </section>
          <section class="prova-bloco prova-bloco-ia">
            <h3>Resposta da IA</h3>
            ${md(meta.resposta_ia)}
          </section>
          <section class="prova-bloco">
            <h3>Citação direta do dispositivo legal</h3>
            ${
              dispositivos.length
                ? dispositivos
                    .map(
                      (x) =>
                        `<blockquote class="prova-dispositivo"><cite>${esc(x.lei)} — art. ${esc(
                          x.artigo
                        )}</cite><pre>${esc(x.texto)}</pre></blockquote>`
                    )
                    .join("")
                : `<p>Não foi localizado o dispositivo integral no acervo Lex para este comando.</p>`
            }
          </section>
          <section class="prova-bloco">
            <h3>Jurisprudência</h3>
            ${
              juris.length
                ? juris
                    .map(
                      (j) =>
                        `<blockquote class="prova-juris"><cite>${esc(j.ref || j.tribunal)}</cite><p>${esc(
                          j.texto
                        )}</p></blockquote>`
                    )
                    .join("")
                : `<p>Sem súmula ou tese correspondente no acervo para este comando.</p>`
            }
          </section>
        </div>
      </article>`;
  }

  function applyFilter(docs, filter) {
    return docs.filter((d) => {
      if (filter.carreira !== "all" && !(d.carreiras_prova || []).includes(filter.carreira)) return false;
      if (filter.tipo !== "all" && d.doc_type !== filter.tipo) return false;
      if (filter.banca !== "all" && (d.organized || {}).banca !== filter.banca) return false;
      return true;
    });
  }

  function render(ctx) {
    const docs = ctx.state.provasJuridicas || [];
    const filter = ctx.state.pjFilter || { carreira: "all", tipo: "all", banca: "all" };
    const filtered = applyFilter(docs, filter);
    const bancas = ["all", ...new Set(docs.map((d) => d.organized?.banca).filter(Boolean))];
    const pageSize = 25;
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
    const page = Math.min(Math.max(1, ctx.state.pjPage || 1), totalPages);
    ctx.state.pjPage = page;
    const pageItems = filtered.slice((page - 1) * pageSize, page * pageSize);
    const objs = docs.filter((d) => d.doc_type === "questoes_objetivas").length;
    const subs = docs.filter((d) => d.doc_type === "questoes_subjetivas").length;

    if (ctx.state.provasLoading) {
      return `<div class="page-head"><h1>Provas jurídicas</h1><p>Varrendo questões de juiz, promotor, defensor e procurador…</p></div><div class="loading">Aguarde…</div>`;
    }

    return `
      <div class="page-head">
        <h1>Provas jurídicas</h1>
        <p>Questões <strong>objetivas e subjetivas</strong> de juiz, promotor, defensor e procurador de Estado dos últimos 2 anos. Cada item traz o <strong>gabarito da banca</strong>, a <strong>resposta da IA</strong>, a <strong>citação integral do artigo</strong> e a <strong>jurisprudência</strong> do acervo. <a href="#/provas-varredura">Monitor da varredura</a></p>
      </div>
      <p class="tag" style="margin:0 0 1rem">${objs} objetivas · ${subs} subjetivas · ${docs.length} no recorte 2024–2026</p>
      <div class="toolbar">
        ${CAREERS.map(
          (c) =>
            `<button type="button" class="chip ${filter.carreira === c.id ? "active" : ""}" data-pj-carreira="${esc(
              c.id
            )}">${esc(c.label)}</button>`
        ).join("")}
      </div>
      <div class="toolbar">
        ${TIPOS.map(
          (t) =>
            `<button type="button" class="chip ${filter.tipo === t.id ? "active" : ""}" data-pj-tipo="${esc(t.id)}">${esc(
              t.label
            )}</button>`
        ).join("")}
      </div>
      <div class="toolbar">
        ${bancas
          .map(
            (b) =>
              `<button type="button" class="chip ${filter.banca === b ? "active" : ""}" data-pj-banca="${esc(
                b
              )}">${b === "all" ? "Todas as bancas" : esc(b)}</button>`
          )
          .join("")}
      </div>
      <p class="tag" style="margin:0 0 1rem">${filtered.length} no filtro · página ${page} de ${totalPages}</p>
      <div class="card-list">
        ${pageItems.map((d) => renderCard(d, ctx)).join("") || `<div class="empty">Nenhuma questão neste filtro.</div>`}
      </div>
      <div class="toolbar" style="margin-top:1rem">
        <button class="chip" data-pj-page="prev" ${page <= 1 ? "disabled" : ""}>← Anterior</button>
        <button class="chip" data-pj-page="next" ${page >= totalPages ? "disabled" : ""}>Próxima →</button>
      </div>`;
  }

  function bind(ctx) {
    const setFilter = (patch) => {
      ctx.state.pjFilter = { ...(ctx.state.pjFilter || { carreira: "all", tipo: "all", banca: "all" }), ...patch };
      ctx.state.pjPage = 1;
      ctx.render();
    };
    document.querySelectorAll("[data-pj-carreira]").forEach((btn) => {
      btn.addEventListener("click", () => setFilter({ carreira: btn.getAttribute("data-pj-carreira") }));
    });
    document.querySelectorAll("[data-pj-tipo]").forEach((btn) => {
      btn.addEventListener("click", () => setFilter({ tipo: btn.getAttribute("data-pj-tipo") }));
    });
    document.querySelectorAll("[data-pj-banca]").forEach((btn) => {
      btn.addEventListener("click", () => setFilter({ banca: btn.getAttribute("data-pj-banca") }));
    });
    document.querySelectorAll("[data-pj-page]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (btn.getAttribute("data-pj-page") === "prev") ctx.state.pjPage = Math.max(1, (ctx.state.pjPage || 1) - 1);
        else ctx.state.pjPage = (ctx.state.pjPage || 1) + 1;
        ctx.render();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
    });
    document.querySelectorAll("[data-pj-id]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const qa = ctx.qAnswerState(btn.getAttribute("data-pj-id"));
        if (qa.revealed) return;
        qa.pick = btn.getAttribute("data-alt-key");
        ctx.render();
      });
    });
    document.querySelectorAll("[data-pj-check]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const qid = btn.getAttribute("data-pj-check");
        const qa = ctx.qAnswerState(qid);
        if (!qa.pick || qa.revealed) return;
        qa.revealed = true;
        const d = (ctx.state.provasJuridicas || []).find((x) => x.external_id === qid);
        const alts = parseAlts(d?.meta);
        const key = gabaritoKey(d?.meta?.gabarito_banca, alts);
        qa.correct = qa.pick === key;
        ctx.persistQAnswers();
        ctx.render();
      });
    });
    document.querySelectorAll("[data-pj-reveal]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const qa = ctx.qAnswerState(btn.getAttribute("data-pj-reveal"));
        qa.revealed = true;
        ctx.persistQAnswers();
        ctx.render();
      });
    });
  }

  window.LexProvasJuridicas = { CAREERS, load, render, bind };
})();
