(function () {
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
    return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  }

  function ageSec(iso) {
    if (!iso) return Infinity;
    const t = new Date(iso).getTime();
    return Number.isNaN(t) ? Infinity : (Date.now() - t) / 1000;
  }

  function bar(done, total) {
    const pct = total ? Math.min(100, Math.round((done / total) * 100)) : 0;
    return `<div class="pj-mon-bar" role="progressbar" aria-valuenow="${pct}"><span style="width:${pct}%"></span></div>
      <p class="pj-mon-bar-label">${done} / ${total} · ${pct}%</p>`;
  }

  function render(data, err) {
    if (err && !data) {
      return `<div class="page-head"><h1>Acervo</h1><p>Varredura de legislação, jurisprudência e doutrina.</p></div>
        <div class="empty">Aguardando o loop… ${esc(err)}</div>`;
    }
    const t = data.totals || {};
    const running = Boolean(data.running) && ageSec(data.updated_at) < 120;
    const legisT = t.legislacao || 0;
    const jurisT = (t.sumulas || 0) + (t.temas || 0);
    const doutT = t.doutrina || 0;
    const recent = data.recent || [];
    const current = data.current;
    const p = data.planalto || {};
    return `
      <div class="page-head">
        <h1>Acervo</h1>
        <p>Varredura contínua no Planalto e no LEXML, com resumos da IA para lei, súmula/tema e doutrina. O texto oficial não é inventado.</p>
      </div>
      <div class="pj-mon">
        <div class="pj-mon-status ${running ? "is-on" : "is-off"}">
          <span class="pj-mon-dot"></span>
          <strong>${running ? "Loop ativo" : "Loop parado"}</strong>
          <span class="tag">${esc(data.phase || "")}</span>
          <span class="pj-mon-msg">${esc(data.message || "")}</span>
        </div>
        <div class="pj-mon-kpis">
          <article><small>Leis</small><b>${legisT}</b></article>
          <article><small>Resumos lei</small><b>${t.legis_ia || 0}</b></article>
          <article><small>Súmulas+temas</small><b>${jurisT}</b></article>
          <article><small>Teses júris</small><b>${t.juris_ia || 0}</b></article>
          <article><small>Doutrina</small><b>${doutT}</b></article>
          <article><small>Resumos doutrina</small><b>${t.doutrina_ia || 0}</b></article>
          <article><small>Fila</small><b>${data.fila || 0}</b></article>
          <article><small>LEXML</small><b>${data.descobertas || 0}</b></article>
        </div>
        <div class="pj-mon-grid">
          <section class="pj-mon-card">
            <h2>Legislação</h2>
            ${bar(t.legis_ia || 0, legisT)}
            <p>Planalto neste ciclo: ${p.fetched || 0} lidas · ${p.updated || 0} alteradas · ${p.failed || 0} falhas</p>
          </section>
          <section class="pj-mon-card">
            <h2>Jurisprudência</h2>
            ${bar(t.juris_ia || 0, jurisT)}
            <p>${t.sumulas || 0} súmulas · ${t.temas || 0} temas</p>
          </section>
        </div>
        <section class="pj-mon-card">
          <h2>Doutrina</h2>
          ${bar(t.doutrina_ia || 0, doutT)}
        </section>
        <section class="pj-mon-card">
          <h2>Em elaboração</h2>
          ${
            current
              ? `<p><strong>${esc(current.kind)}</strong> · ${esc(current.titulo || "")}</p>`
              : `<p class="tag">${running ? "Varrendo fontes oficiais ou em espera." : "Nenhum item em curso."}</p>`
          }
          <p class="tag">Modelo ${esc(data.model || "")} · ciclo ${data.cycle || 0} · ${fmtTime(data.updated_at)}</p>
        </section>
        <section class="pj-mon-card">
          <h2>Últimas atualizações</h2>
          <ol class="pj-mon-log">
            ${
              recent
                .slice()
                .reverse()
                .map(
                  (ev) =>
                    `<li><time>${fmtTime(ev.ts)}</time> <span class="tag">${esc(ev.kind)}</span>
                    <span>${esc(ev.tipo)} · ${ev.seconds ?? "—"}s</span>
                    <span>${esc(ev.titulo || ev.id || "")}</span></li>`
                )
                .join("") || "<li>Ainda sem eventos neste run.</li>"
            }
          </ol>
          ${data.last_error ? `<p class="pj-mon-err">Último erro: ${esc(data.last_error)}</p>` : ""}
        </section>
        <p class="tag">
          <a href="./acervo.html">Página dedicada</a> ·
          <a href="./index.html#/lei-seca">Lei seca</a> ·
          <a href="./index.html#/jurisprudencia">Jurisprudência</a> ·
          <a href="./varredura.html">Provas</a>
        </p>
      </div>`;
  }

  async function fetchStatus() {
    const url = window.LEX_CONFIG?.acervoVarreduraStatus || "./data/acervo_varredura_status.json";
    const res = await fetch(`${url}?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(String(res.status));
    return res.json();
  }

  function mountStandalone(root) {
    const tick = async () => {
      try {
        root.innerHTML = render(await fetchStatus());
      } catch (err) {
        root.innerHTML = render(null, err.message || String(err));
      }
    };
    tick();
    return window.setInterval(tick, 2500);
  }

  window.LexAcervoVarredura = { render, fetchStatus, mountStandalone };
})();
