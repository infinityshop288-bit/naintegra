/**
 * Monitor ao vivo da varredura de provas jurídicas e do loop de IA.
 */
(function () {
  const CAREER_LABEL = {
    juiz: "Juiz",
    promotor: "Promotor",
    defensor: "Defensor",
    procurador: "Procurador",
  };

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fmtTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  function ageSec(iso) {
    if (!iso) return Infinity;
    const t = new Date(iso).getTime();
    return Number.isNaN(t) ? Infinity : (Date.now() - t) / 1000;
  }

  function bar(done, total) {
    const pct = total ? Math.min(100, Math.round((done / total) * 100)) : 0;
    return `<div class="pj-mon-bar" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100">
      <span style="width:${pct}%"></span>
    </div>
    <p class="pj-mon-bar-label">${done} / ${total} · ${pct}%</p>`;
  }

  function live(data) {
    const running = Boolean(data?.running) && ageSec(data?.updated_at) < 90;
    const phase = running ? data.phase || "ia" : "parado";
    return { running, phase };
  }

  function render(data, err) {
    if (err && !data) {
      return `<div class="page-head">
        <h1>Varredura</h1>
        <p>Monitor da coleta e da elaboração por IA (Codex · Responses API).</p>
      </div>
      <div class="empty">Aguardando o loop… ${esc(err)}</div>`;
    }
    const t = data.totals || {};
    const { running, phase } = live(data);
    const fila = Number(data.fila || (t.pendente || 0) + (t.acervo || 0));
    const eta = data.eta_minutes == null ? "—" : data.eta_minutes < 1 ? "< 1 min" : `${data.eta_minutes} min`;
    const current = data.current;
    const recent = data.recent || [];
    const carreiras = t.carreiras || {};
    return `
      <div class="page-head">
        <h1>Varredura</h1>
        <p>Monitor ao vivo: varre juiz, promotor, defensor e procurador (2024–2026) e elabora gabarito da IA em loop contínuo.</p>
      </div>
      <div class="pj-mon">
        <div class="pj-mon-status ${running ? "is-on" : "is-off"}">
          <span class="pj-mon-dot" aria-hidden="true"></span>
          <strong>${running ? "Loop ativo" : "Loop parado"}</strong>
          <span class="tag">${esc(phase)}</span>
          <span class="pj-mon-msg">${esc(data.message || "")}</span>
        </div>
        <div class="pj-mon-kpis">
          <article><small>Catálogo</small><b>${t.catalogo || 0}</b></article>
          <article><small>Respostas IA</small><b>${t.ia || 0}</b></article>
          <article><small>Fila</small><b>${fila}</b></article>
          <article><small>Ciclo</small><b>${data.cycle || 0}</b></article>
          <article><small>Neste run</small><b>${data.done_this_run || 0}</b></article>
          <article><small>Ritmo</small><b>${data.rate_per_min || 0}/min</b></article>
          <article><small>ETA</small><b>${esc(eta)}</b></article>
          <article><small>Erros</small><b>${data.errors || 0}</b></article>
        </div>
        <div class="pj-mon-grid">
          <section class="pj-mon-card">
            <h2>Progresso da IA</h2>
            ${bar(t.ia || 0, t.catalogo || 0)}
            <p>Discursivas ${t.subjetivas_ia || 0}/${t.subjetivas || 0} · Objetivas ${t.objetivas_ia || 0}/${t.objetivas || 0}</p>
            ${bar(t.subjetivas_ia || 0, t.subjetivas || 0)}
            ${bar(t.objetivas_ia || 0, t.objetivas || 0)}
          </section>
          <section class="pj-mon-card">
            <h2>Acervo citado</h2>
            <p>Dispositivo integral em ${t.com_dispositivo || 0} questões</p>
            ${bar(t.com_dispositivo || 0, t.catalogo || 0)}
            <p>Jurisprudência em ${t.com_juris || 0} questões</p>
            ${bar(t.com_juris || 0, t.catalogo || 0)}
            <p class="tag">Modelo ${esc(data.model || "gpt-5.6-sol")} · atualizado ${fmtTime(data.updated_at)}</p>
          </section>
        </div>
        <section class="pj-mon-card">
          <h2>Carreiras</h2>
          <div class="pj-mon-careers">
            ${Object.keys(CAREER_LABEL)
              .map(
                (k) =>
                  `<span><em>${esc(CAREER_LABEL[k])}</em> ${carreiras[k] || 0}</span>`
              )
              .join("")}
          </div>
        </section>
        <section class="pj-mon-card">
          <h2>Em elaboração</h2>
          ${
            current
              ? `<p><strong>${current.tipo === "questoes_subjetivas" ? "Discursiva" : "Objetiva"}</strong>
                 · ${esc(current.materia || "—")} · ${esc((current.carreiras || []).join(", "))}
                 · ${esc(current.banca || "")} ${esc(current.ano || "")}</p>
                 <p>${esc(current.titulo || "")}</p>`
              : `<p class="tag">${running ? "Sem item neste instante — varrendo ou em espera." : "Nenhum item em curso."}</p>`
          }
        </section>
        <section class="pj-mon-card">
          <h2>Últimas elaborações</h2>
          <ol class="pj-mon-log">
            ${
              recent
                .slice()
                .reverse()
                .map(
                  (ev) =>
                    `<li><time>${fmtTime(ev.ts)}</time>
                    <span class="tag">${esc(ev.kind || "")}</span>
                    <span>${esc(ev.tipo === "questoes_subjetivas" ? "discursiva" : "objetiva")} · ${esc(ev.materia || "")} · ${ev.seconds ?? "—"}s</span>
                    <span>${esc(ev.titulo || ev.id || "")}</span></li>`
                )
                .join("") || "<li>Ainda sem eventos neste run.</li>"
            }
          </ol>
          ${data.last_error ? `<p class="pj-mon-err">Último erro: ${esc(data.last_error)}</p>` : ""}
        </section>
        <p class="tag">Abra também <a href="./varredura.html">a página dedicada</a> · catálogo em <a href="./index.html#/provas-juridicas">Provas jurídicas</a></p>
      </div>`;
  }

  async function fetchStatus() {
    const url = window.LEX_CONFIG?.provasVarreduraStatus || "./data/provas_varredura_status.json";
    const res = await fetch(`${url}?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(String(res.status));
    return res.json();
  }

  function mountStandalone(root) {
    let timer = 0;
    const tick = async () => {
      try {
        const data = await fetchStatus();
        root.innerHTML = render(data);
      } catch (err) {
        root.innerHTML = render(null, err.message || String(err));
      }
    };
    tick();
    timer = window.setInterval(tick, 2000);
    return () => window.clearInterval(timer);
  }

  window.LexProvasVarredura = { render, fetchStatus, mountStandalone, live };
})();
