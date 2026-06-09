(function () {
  const cfg = window.DELEGADO_CONFIG;
  let charts = {};

  function $(sel) {
    return document.querySelector(sel);
  }

  function fmtNum(n) {
    if (n == null || Number.isNaN(n)) return "—";
    return new Intl.NumberFormat("pt-BR").format(n);
  }

  function show(el) {
    el.classList.remove("hidden");
  }

  function hide(el) {
    el.classList.add("hidden");
  }

  function setTab(tab) {
    document.querySelectorAll(".tab").forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === tab);
    });
    document.querySelectorAll(".panel").forEach((p) => {
      p.classList.toggle("active", p.id === "panel-" + tab);
    });
    loadPanel(tab);
  }

  async function loadPanel(tab) {
    const loaders = {
      overview: renderOverview,
      content: renderContent,
      publish: renderPublish,
      ads: renderAds,
      monitoring: renderMonitoring,
      competitors: renderCompetitors,
      automations: renderAutomations,
    };
    if (loaders[tab]) await loaders[tab]();
  }

  async function renderOverview() {
    const el = $("#panel-overview");
    el.innerHTML = "<p class='muted'>Carregando KPIs…</p>";
    try {
      const data = await window.DelegadoApi.overview();
      const k = data.kpis || {};
      const pos = data.positioning || {};
      el.innerHTML = `
        <div class="grid grid-4">
          ${kpiCard("Seguidores", k.seguidores, k.fonte)}
          ${kpiCard("Engajamento", k.engajamento, k.fonte)}
          ${kpiCard("Alcance", k.alcance, k.fonte)}
          ${kpiCard("Leads", k.leads, k.fonte)}
        </div>
        <div class="grid grid-2" style="margin-top:1rem">
          <div class="card highlight">
            <h2>Posicionamento no nicho</h2>
            <p><strong>Diferencial:</strong> ${esc(pos.diferencial || "")}</p>
            <p><strong>Público:</strong> ${esc(pos.publico || "")}</p>
            <p><strong>Referência:</strong> ${esc(pos.referencia_crescimento || "")}</p>
            <p><strong>Benchmark direto:</strong> ${esc(pos.benchmark_direto || "")}</p>
            <p><strong>CTA:</strong> ${esc(pos.cta_principal || "")}</p>
          </div>
          <div class="card">
            <h2>Status da API Meta</h2>
            <p class="muted">Fonte: ${esc(k.fonte || "aguardando_api")}</p>
            ${data.error ? `<p class="error">${esc(data.error)}</p>` : ""}
            ${(data.warnings || []).map((w) => `<p class="muted">${esc(w)}</p>`).join("")}
            <button type="button" class="btn ghost small" id="btn-debug-token">Validar token</button>
            <pre id="debug-output" class="muted" style="font-size:0.75rem;overflow:auto;max-height:200px;margin-top:0.75rem"></pre>
          </div>
        </div>`;
      $("#btn-debug-token")?.addEventListener("click", async () => {
        const out = $("#debug-output");
        out.textContent = "Validando…";
        try {
          const dbg = await window.DelegadoApi.debugToken();
          out.textContent = JSON.stringify(dbg, null, 2);
        } catch (e) {
          out.textContent = e.message;
        }
      });
    } catch (e) {
      el.innerHTML = `<p class="error">${esc(e.message)}</p>`;
    }
  }

  function kpiCard(label, value, fonte) {
    const pending = fonte === "aguardando_api" || value == null;
    return `<div class="card">
      <div class="kpi-label">${label}</div>
      <div class="kpi-value">${fmtNum(value)}</div>
      ${pending ? '<div class="kpi-pending">aguardando API</div>' : ""}
    </div>`;
  }

  async function renderContent() {
    const el = $("#panel-content");
    if (el.dataset.ready) return;
    el.dataset.ready = "1";
    let providerOptions = "<option value=''>Padrão (Ollama)</option>";
    try {
      const prov = await window.DelegadoApi.contentProviders();
      providerOptions = (prov.providers || [])
        .map(
          (p) =>
            `<option value="${esc(p.id)}" ${p.id === prov.active ? "selected" : ""} ${
              p.configured ? "" : "disabled"
            }>${esc(p.label)}${p.configured ? "" : " (off)"}</option>`
        )
        .join("");
    } catch (e) {
      providerOptions =
        "<option value=''>Padrão (Ollama)</option>";
    }

    let apiBanner = "";
    const apiOk = await window.DelegadoApi.health();
    if (!apiOk) {
      apiBanner = `<div class="card" style="border-color:#c44">
        <p class="error"><strong>API offline.</strong> ${esc(
          "Inicie no terminal: cd naintegra && PYTHONPATH=src DELEGADO_AI_PROVIDER=ollama python3 -m uvicorn naintegra_meta.api:app --host 127.0.0.1 --port 8787"
        )}</p>
      </div>`;
    }

    el.innerHTML = `
      ${apiBanner}
      <div class="card highlight">
        <h2>Estilo @profalexandrezamboni</h2>
        <p class="muted">Reels «Indo DIRETO ao ponto» + legenda numerada + «Qual a sua opinião?» — adaptado para PF (disclaimer educacional).</p>
        <button type="button" class="btn ghost small" id="btn-show-calendar">Ver cronograma do mês</button>
        <pre id="calendar-preview" class="muted hidden" style="font-size:0.75rem;max-height:220px;overflow:auto"></pre>
      </div>
      <div class="card">
        <h2>Automação (aprovação manual)</h2>
        <p class="muted">Gera post do dia no calendário → fila <code>aguardando_aprovacao</code>. Você publica manualmente na aba Publicação.</p>
        <div class="field-row">
          <label>Dias<input id="pipe-days" type="number" min="1" max="31" value="1" /></label>
          <label>Provedor IA<select id="pipe-provider">${providerOptions}</select></label>
        </div>
        <button type="button" class="btn primary" id="btn-run-pipeline">Gerar fila de hoje</button>
        <p id="pipeline-result" class="muted" style="margin-top:0.75rem"></p>
      </div>
      <div class="card highlight">
        <h2>Pacote completo (texto + imagens)</h2>
        <p class="muted">Legenda longa, roteiro Reels, slides e PNGs prontos (PIL local + DALL-E/Gemini se configurados). Usa biblioteca Marketing Digital + Lex.</p>
        <div class="field-row">
          <label>Tema<input id="pkg-tema" placeholder="Ex.: flagrante vs prisão em flagrante" /></label>
          <label>Formato
            <select id="pkg-formato">
              <option value="carrossel" selected>Carrossel</option>
              <option value="reels">Reels</option>
              <option value="story">Story</option>
            </select>
          </label>
          <label>Texto IA<select id="pkg-text-provider">${providerOptions}</select></label>
          <label>Imagem<select id="pkg-image-provider"><option value="">Auto</option><option value="pillow" selected>Local PIL</option><option value="openai">OpenAI</option><option value="gemini">Gemini</option></select></label>
        </div>
        <label style="display:flex;align-items:center;gap:0.5rem;margin:0.5rem 0">
          <input type="checkbox" id="pkg-ai-images" checked /> Tentar imagens IA (senão só slides PIL)
        </label>
        <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
          <button type="button" class="btn primary" id="btn-generate-package">Gerar pacote postável</button>
          <button type="button" class="btn ghost" id="btn-compare-ias">Comparar IAs (texto)</button>
        </div>
        <p id="pkg-result" class="muted" style="margin-top:0.75rem"></p>
        <div id="pkg-preview" class="pkg-preview-grid"></div>
      </div>
      <div class="card">
        <h2>Gerador de ideias (IA)</h2>
        <p class="muted">Tema + formato → 3 ideias (gancho overlay, roteiro, legenda Zamboni)</p>
        <div class="field-row">
          <label>Tema<input id="idea-tema" placeholder="Ex.: flagrante vs auto de prisão em flagrante" /></label>
          <label>Formato
            <select id="idea-formato">
              <option value="carrossel">Carrossel</option>
              <option value="reels" selected>Reels</option>
              <option value="story">Story</option>
            </select>
          </label>
          <label>Provedor<select id="idea-provider">${providerOptions}</select></label>
        </div>
        <button type="button" class="btn primary" id="btn-generate-ideas">Gerar ideias</button>
        <div id="ideas-output"></div>
      </div>`;

    $("#btn-show-calendar")?.addEventListener("click", async () => {
      const pre = $("#calendar-preview");
      try {
        const res = await window.DelegadoApi.contentCalendar("2026-06");
        pre.textContent = JSON.stringify(res.calendar?.days || [], null, 2);
        pre.classList.remove("hidden");
      } catch (e) {
        pre.textContent = e.message;
        pre.classList.remove("hidden");
      }
    });

    $("#btn-generate-package")?.addEventListener("click", async () => {
      const tema = $("#pkg-tema").value.trim() || $("#idea-tema").value.trim();
      const out = $("#pkg-result");
      const prev = $("#pkg-preview");
      if (tema.length < 3) {
        out.textContent = "Informe um tema com pelo menos 3 caracteres.";
        return;
      }
      out.textContent = "Gerando pacote (texto + imagens)… pode levar alguns minutos.";
      prev.innerHTML = "";
      try {
        const res = await window.DelegadoApi.generatePackage({
          tema,
          formato: $("#pkg-formato").value,
          text_provider: $("#pkg-text-provider").value || null,
          image_provider: $("#pkg-image-provider").value || null,
          use_ai_images: $("#pkg-ai-images").checked,
          save_queue: true,
        });
        const pkg = res.package || {};
        out.textContent = `Pacote ${pkg.package_id} — ${pkg.text_source || ""}. ${
          pkg.queue_id ? "Na fila ✓" : pkg.queue_error || "Revise fila/outbox"
        }`;
        window._lastPackage = pkg;
        const assets = pkg.assets || [];
        prev.innerHTML = "";
        for (const a of assets) {
          const fig = document.createElement("figure");
          fig.className = "pkg-thumb";
          const img = document.createElement("img");
          img.alt = a.label || a.kind || "";
          const cap = document.createElement("figcaption");
          cap.textContent = `${a.label || a.kind || ""} · ${a.image_provider || ""}`;
          fig.append(img, cap);
          prev.append(fig);
          if (a.url) {
            window.DelegadoApi.fetchAsset(a.url)
              .then((blob) => {
                img.src = URL.createObjectURL(blob);
              })
              .catch(() => {
                cap.textContent += " (preview: faça login / API ativa)";
              });
          }
        }
        if (pkg.meta?.roteiro_falas) {
          const pre = document.createElement("pre");
          pre.className = "muted";
          pre.style.gridColumn = "1/-1";
          pre.textContent = pkg.meta.roteiro_falas;
          prev.append(pre);
        }
      } catch (e) {
        out.innerHTML = `<p class="error">${esc(window.DelegadoApi.apiNetworkError(e))}</p>`;
      }
    });

    $("#btn-compare-ias")?.addEventListener("click", async () => {
      const tema = $("#pkg-tema").value.trim();
      const out = $("#pkg-result");
      if (tema.length < 3) {
        out.textContent = "Informe um tema.";
        return;
      }
      out.textContent = "Comparando provedores de texto…";
      try {
        const res = await window.DelegadoApi.comparePackages(tema, $("#pkg-formato").value);
        out.innerHTML =
          "<pre class='muted' style='max-height:240px;overflow:auto'>" +
          esc(JSON.stringify(res, null, 2)) +
          "</pre>";
      } catch (e) {
        out.textContent = window.DelegadoApi.apiNetworkError(e);
      }
    });

    $("#btn-run-pipeline")?.addEventListener("click", async () => {
      const out = $("#pipeline-result");
      out.textContent = "Gerando com Ollama/IA…";
      try {
        const res = await window.DelegadoApi.runPipeline({
          days: Number($("#pipe-days").value) || 1,
          provider: $("#pipe-provider").value || null,
          dry_run: false,
        });
        out.textContent = `OK: ${res.created_count} item(ns) — provedor ${res.provider}. Abra Publicação para aprovar.`;
      } catch (e) {
        out.textContent = window.DelegadoApi.apiNetworkError(e);
      }
    });

    $("#btn-generate-ideas").addEventListener("click", async () => {
      const tema = $("#idea-tema").value.trim();
      const formato = $("#idea-formato").value;
      const provider = $("#idea-provider")?.value || null;
      const out = $("#ideas-output");
      if (tema.length < 3) {
        out.innerHTML = "<p class='error'>Informe um tema com pelo menos 3 caracteres.</p>";
        return;
      }
      out.innerHTML =
        "<p class='muted'>Gerando ideias… Com Ollama local pode levar 1–2 minutos. Aguarde.</p>";
      try {
        const res = await window.DelegadoApi.generateIdeas(tema, formato, provider);
        const sourceNote =
          res.source === "fallback"
            ? "<p class='muted'>Modo template local — IA indisponível.</p>"
            : `<p class='muted'>Fonte: ${esc(res.source || "")}</p>`;
        out.innerHTML =
          sourceNote +
          (res.ideas || [])
          .map(
            (idea, i) => `
          <div class="idea-card">
            <h3>${i + 1}. ${esc(idea.titulo || "Ideia")}</h3>
            <p><strong>Gancho:</strong> ${esc(idea.gancho || "")}</p>
            ${idea.texto_overlay ? `<p><strong>Overlay:</strong> ${esc(idea.texto_overlay)}</p>` : ""}
            ${idea.roteiro_falas ? `<p><strong>Roteiro:</strong> ${esc(idea.roteiro_falas)}</p>` : ""}
            <p>${esc(idea.legenda || "")}</p>
            <p class="hashtags">${esc((idea.hashtags || []).join(" "))}</p>
            <p><strong>CTA:</strong> ${esc(idea.cta || "")}</p>
            <div style="margin-top:0.75rem;display:flex;gap:0.5rem;flex-wrap:wrap">
              <button type="button" class="btn ghost small btn-copy" data-idx="${i}">Copiar legenda</button>
              <button type="button" class="btn ghost small btn-queue" data-idx="${i}">Adicionar à fila</button>
            </div>
          </div>`
          )
          .join("");
        window._lastIdeas = res.ideas;
        out.querySelectorAll(".btn-copy").forEach((btn) => {
          btn.addEventListener("click", () => {
            const idea = window._lastIdeas[Number(btn.dataset.idx)];
            const text = [idea.legenda, (idea.hashtags || []).join(" "), idea.cta]
              .filter(Boolean)
              .join("\n\n");
            navigator.clipboard.writeText(text);
            btn.textContent = "Copiado!";
          });
        });
        out.querySelectorAll(".btn-queue").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const idea = window._lastIdeas[Number(btn.dataset.idx)];
            try {
              await window.DelegadoApi.saveQueueItem({
                titulo: idea.titulo || tema,
                formato: idea.formato_sugerido || formato,
                legenda: idea.legenda || "",
                hashtags: idea.hashtags || [],
                status: "aguardando_aprovacao",
                meta: {
                  gancho: idea.gancho,
                  texto_overlay: idea.texto_overlay,
                  roteiro_falas: idea.roteiro_falas,
                  slides: idea.slides || [],
                },
              });
              btn.textContent = "Na fila ✓";
            } catch (e) {
              alert(e.message);
            }
          });
        });
      } catch (e) {
        out.innerHTML = `<p class="error">${esc(window.DelegadoApi.apiNetworkError(e))}</p>`;
      }
    });
  }

  async function renderPublish() {
    const el = $("#panel-publish");
    el.innerHTML = "<p class='muted'>Carregando fila…</p>";
    try {
      const res = await window.DelegadoApi.getQueue();
      const items = res.items || [];
      el.innerHTML = `
        <div class="grid grid-2">
          <div class="card">
            <h2>Novo item na fila</h2>
            <div class="field-row">
              <label>Título<input id="q-titulo" /></label>
              <label>Formato
                <select id="q-formato">
                  <option value="carrossel">Carrossel</option>
                  <option value="reels">Reels</option>
                  <option value="story">Story</option>
                </select>
              </label>
            </div>
            <div class="field-row">
              <label>URL da mídia (pública)<input id="q-media" placeholder="https://…supabase.co/storage/…" /></label>
            </div>
            <div class="field-row">
              <label>Legenda<textarea id="q-legenda"></textarea></label>
            </div>
            <div class="field-row">
              <label>Agendar (ISO)<input id="q-scheduled" placeholder="2026-06-01T18:00:00-03:00" /></label>
            </div>
            <button type="button" class="btn primary" id="btn-save-queue">Salvar na fila</button>
          </div>
          <div class="card">
            <h2>Publicar agora (Graph API)</h2>
            <p class="muted">Exige URL pública da mídia no Supabase Storage</p>
            <div class="field-row">
              <label>URL imagem/vídeo<input id="pub-url" /></label>
            </div>
            <div class="field-row">
              <label>Legenda<textarea id="pub-caption"></textarea></label>
            </div>
            <div style="display:flex;gap:0.5rem;flex-wrap:wrap">
              <button type="button" class="btn primary" id="btn-pub-image">Publicar imagem</button>
              <button type="button" class="btn ghost" id="btn-pub-reels">Publicar Reels</button>
            </div>
            <p id="pub-result" class="muted" style="margin-top:0.75rem"></p>
          </div>
        </div>
        <div class="card" style="margin-top:1rem">
          <h2>Fila / calendário</h2>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Título</th><th>Formato</th><th>Status</th><th>Agendado</th><th>Aprovação</th><th></th></tr></thead>
              <tbody id="queue-body">${queueRows(items)}</tbody>
            </table>
          </div>
        </div>`;

      bindPublishHandlers(items);
    } catch (e) {
      el.innerHTML = `<p class="error">${esc(e.message)}</p>`;
    }
  }

  function queueRows(items) {
    if (!items.length) return "<tr><td colspan='6' class='muted'>Fila vazia</td></tr>";
    return items
      .map(
        (it) => `<tr>
        <td>${esc(it.titulo)}</td>
        <td>${esc(it.formato)}</td>
        <td><span class="status-pill ${esc(it.status)}">${esc(it.status)}</span></td>
        <td>${esc(it.scheduled_at || "—")}</td>
        <td>
          ${
            it.status === "aguardando_aprovacao"
              ? `<button type="button" class="btn primary small btn-approve-q" data-id="${esc(it.id)}">Aprovar</button>
                 <button type="button" class="btn ghost small btn-reject-q" data-id="${esc(it.id)}">Rejeitar</button>`
              : ""
          }
        </td>
        <td><button type="button" class="btn ghost small btn-del-q" data-id="${esc(it.id)}">Remover</button></td>
      </tr>`
      )
      .join("");
  }

  function bindPublishHandlers() {
    $("#btn-save-queue")?.addEventListener("click", async () => {
      try {
        await window.DelegadoApi.saveQueueItem({
          titulo: $("#q-titulo").value.trim(),
          formato: $("#q-formato").value,
          legenda: $("#q-legenda").value,
          media_url: $("#q-media").value.trim() || null,
          scheduled_at: $("#q-scheduled").value.trim() || null,
          status: $("#q-scheduled").value.trim() ? "agendado" : "rascunho",
        });
        renderPublish();
      } catch (e) {
        alert(e.message);
      }
    });

    $("#btn-pub-image")?.addEventListener("click", async () => {
      const result = $("#pub-result");
      result.textContent = "Publicando…";
      try {
        const res = await window.DelegadoApi.publishImage(
          $("#pub-url").value.trim(),
          $("#pub-caption").value
        );
        result.textContent = "Publicado: " + JSON.stringify(res);
      } catch (e) {
        result.textContent = e.message;
      }
    });

    $("#btn-pub-reels")?.addEventListener("click", async () => {
      const result = $("#pub-result");
      result.textContent = "Processando Reels…";
      try {
        const res = await window.DelegadoApi.publishReels(
          $("#pub-url").value.trim(),
          $("#pub-caption").value
        );
        result.textContent = "Reels publicado: " + JSON.stringify(res);
      } catch (e) {
        result.textContent = e.message;
      }
    });

    document.querySelectorAll(".btn-approve-q").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await window.DelegadoApi.patchQueueStatus(btn.dataset.id, "aprovado");
          renderPublish();
        } catch (e) {
          alert(e.message);
        }
      });
    });
    document.querySelectorAll(".btn-reject-q").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await window.DelegadoApi.patchQueueStatus(btn.dataset.id, "rejeitado");
          renderPublish();
        } catch (e) {
          alert(e.message);
        }
      });
    });
    document.querySelectorAll(".btn-del-q").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await window.DelegadoApi.deleteQueueItem(btn.dataset.id);
          renderPublish();
        } catch (e) {
          alert(e.message);
        }
      });
    });
  }

  async function renderAds() {
    const el = $("#panel-ads");
    el.innerHTML = "<p class='muted'>Carregando campanhas…</p>";
    try {
      const data = await window.DelegadoApi.adsCampaigns();
      const campaigns = data.campaigns?.data || [];
      const insights = (data.account_insights?.data || [])[0] || {};
      const links = data.setup_links || {};
      if (data.ads_blocked) {
        el.innerHTML = `
          <div class="card highlight">
            <h2>Anúncios — autorização pendente</h2>
            <p class="error">${esc(data.error || "Conta de anúncios não autorizou o app.")}</p>
            <p class="muted">${esc(data.hint || "")}</p>
            <p style="margin-top:0.75rem">
              ${links.assign_ad_account ? `<a href="${esc(links.assign_ad_account)}" target="_blank" rel="noopener">Abrir conta de anúncios no Business Manager</a>` : ""}
            </p>
            <p class="muted" style="margin-top:0.5rem">App: Claude · Business: Infinity - Digital</p>
          </div>`;
        return;
      }
      el.innerHTML = `
        <div class="grid grid-4">
          ${kpiCard("Gasto (30d)", insights.spend, "graph_api")}
          ${kpiCard("Impressões", insights.impressions, "graph_api")}
          ${kpiCard("Cliques", insights.clicks, "graph_api")}
          ${kpiCard("CTR", insights.ctr ? insights.ctr + "%" : null, "graph_api")}
        </div>
        <div class="card" style="margin-top:1rem">
          <h2>Campanhas Meta Ads</h2>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Nome</th><th>Status</th><th>Objetivo</th><th>ID</th></tr></thead>
              <tbody>
                ${
                  campaigns.length
                    ? campaigns
                        .map(
                          (c) => `<tr>
                    <td>${esc(c.name)}</td>
                    <td>${esc(c.status)}</td>
                    <td>${esc(c.objective)}</td>
                    <td class="muted">${esc(c.id)}</td>
                  </tr>`
                        )
                        .join("")
                    : "<tr><td colspan='4' class='muted'>Nenhuma campanha ou token Ads pendente</td></tr>"
                }
              </tbody>
            </table>
          </div>
        </div>`;
    } catch (e) {
      el.innerHTML = `<p class="error">${esc(e.message)}</p><p class="muted">Configure META_AD_ACCOUNT_ID e permissões ads_read.</p>`;
    }
  }

  async function renderMonitoring() {
    const el = $("#panel-monitoring");
    el.innerHTML = "<p class='muted'>Carregando insights…</p>";
    try {
      const data = await window.DelegadoApi.monitoring();
      const metrics = flattenInsights(data.account_insights);
      const derived = data.derived_metrics || {};
      const chartMetrics =
        Object.keys(metrics).length > 0
          ? metrics
          : {
              curtidas: derived.total_likes,
              comentários: derived.total_comments,
              interações: derived.total_interactions,
            };
      const media = data.recent_media?.data || [];
      const warn = data.warning
        ? `<p class="muted">${esc(data.warning)}</p>`
        : "";
      el.innerHTML = `
        ${warn}
        <div class="grid grid-2">
          <div class="card">
            <h2>Alcance × Interações</h2>
            <div class="chart-box"><canvas id="chart-monitoring"></canvas></div>
          </div>
          <div class="card">
            <h2>Publicações recentes</h2>
            <div class="table-wrap">
              <table>
                <thead><tr><th>Data</th><th>Tipo</th><th>Curtidas</th><th>Comentários</th><th></th></tr></thead>
                <tbody>
                  ${media
                    .map(
                      (m) => `<tr>
                    <td class="muted">${esc((m.timestamp || "").slice(0, 10))}</td>
                    <td>${esc(m.media_type)}</td>
                    <td>${fmtNum(m.like_count)}</td>
                    <td>${fmtNum(m.comments_count)}</td>
                    <td><button type="button" class="btn ghost small btn-comments" data-id="${esc(m.id)}">Ver</button></td>
                  </tr>`
                    )
                    .join("")}
                </tbody>
              </table>
            </div>
            <div id="comments-box" style="margin-top:1rem"></div>
          </div>
        </div>`;

      if (charts.monitoring) charts.monitoring.destroy();
      const ctx = document.getElementById("chart-monitoring");
      charts.monitoring = new Chart(ctx, {
        type: "bar",
        data: {
          labels: Object.keys(chartMetrics),
          datasets: [
            {
              label: "Valor",
              data: Object.values(chartMetrics),
              backgroundColor: "rgba(201, 168, 76, 0.55)",
              borderColor: "#c9a84c",
              borderWidth: 1,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: "#9a968a" }, grid: { color: "#2a2a32" } },
            y: { ticks: { color: "#9a968a" }, grid: { color: "#2a2a32" } },
          },
        },
      });

      document.querySelectorAll(".btn-comments").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const box = $("#comments-box");
          box.innerHTML = "<p class='muted'>Carregando comentários…</p>";
          try {
            const res = await window.DelegadoApi.comments(btn.dataset.id);
            const comments = res.data || [];
            box.innerHTML =
              comments.length === 0
                ? "<p class='muted'>Sem comentários.</p>"
                : comments
                    .map(
                      (c) => `<div style="padding:0.5rem 0;border-bottom:1px solid var(--border)">
                  <strong>@${esc(c.username || "?")}</strong>
                  <span class="muted"> · ${esc((c.timestamp || "").slice(0, 10))}</span>
                  <p>${esc(c.text || "")}</p>
                </div>`
                    )
                    .join("");
          } catch (e) {
            box.innerHTML = `<p class="error">${esc(e.message)}</p>`;
          }
        });
      });
    } catch (e) {
      el.innerHTML = `<p class="error">${esc(e.message)}</p>`;
    }
  }

  function flattenInsights(payload) {
    const out = {};
    for (const item of payload?.data || []) {
      const vals = item.values || [];
      if (item.name && vals.length) out[item.name] = vals[vals.length - 1].value;
    }
    return out;
  }

  async function renderCompetitors() {
    const el = $("#panel-competitors");
    el.innerHTML = "<p class='muted'>Carregando…</p>";
    try {
      const data = await window.DelegadoApi.competitors();
      const list = data.competitors || [];
      el.innerHTML = `
        <div class="grid grid-2">
          <div class="card">
            <h2>Seguidores no nicho</h2>
            <div class="chart-box"><canvas id="chart-competitors"></canvas></div>
          </div>
          <div class="card highlight">
            <h2>Leitura estratégica</h2>
            <p>${esc(data.positioning?.diferencial || "")}</p>
            <p class="muted">Alvo: ${esc(data.positioning?.referencia_crescimento || "")} · Benchmark: ${esc(data.positioning?.benchmark_direto || "")}</p>
          </div>
        </div>
        <div class="card" style="margin-top:1rem">
          <div class="table-wrap">
            <table>
              <thead><tr><th>Perfil</th><th>Seguidores</th><th>Camada</th><th>Nicho</th></tr></thead>
              <tbody>
                ${list
                  .map((c) => {
                    const isBrand = c.handle === cfg.instagramHandle;
                    return `<tr class="${isBrand ? "highlight" : ""}">
                    <td>${esc(c.handle)}</td>
                    <td>${c.seguidores != null ? fmtNum(c.seguidores) : "aguardando API"}</td>
                    <td>${esc(c.camada)}</td>
                    <td>${esc(c.nicho)}</td>
                  </tr>`;
                  })
                  .join("")}
              </tbody>
            </table>
          </div>
        </div>`;

      if (charts.competitors) charts.competitors.destroy();
      const sorted = list
        .filter((c) => c.seguidores != null)
        .sort((a, b) => b.seguidores - a.seguidores)
        .slice(0, 10);
      charts.competitors = new Chart(document.getElementById("chart-competitors"), {
        type: "bar",
        data: {
          labels: sorted.map((c) => c.handle.replace("@", "")),
          datasets: [
            {
              data: sorted.map((c) => c.seguidores),
              backgroundColor: sorted.map((c) =>
                c.handle === cfg.instagramHandle ? "#c9a84c" : "rgba(201,168,76,0.35)"
              ),
            },
          ],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { ticks: { color: "#9a968a" }, grid: { color: "#2a2a32" } },
            y: { ticks: { color: "#9a968a", font: { size: 10 } }, grid: { display: false } },
          },
        },
      });
    } catch (e) {
      el.innerHTML = `<p class="error">${esc(e.message)}</p>`;
    }
  }

  async function renderAutomations() {
    const el = $("#panel-automations");
    el.innerHTML = "<p class='muted'>Carregando automações…</p>";
    try {
      const data = await window.DelegadoApi.automations();
      const items = data.automations || [];
      el.innerHTML = `
        <p class="muted" style="margin-bottom:1rem">Hipóteses de marketing automatizado qualificadas como vencedoras no nicho Direito Penal / concursos policiais.</p>
        <div class="grid grid-2">
          ${items
            .map(
              (a) => `
            <div class="card">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:0.5rem">
                <h3 style="margin:0">${esc(a.nome)}</h3>
                <span class="status-pill ${esc(a.status)}">${esc(a.status)}</span>
              </div>
              <div class="automation-meta">
                <span class="chip">${esc(a.categoria)}</span>
                <span class="chip ${a.impacto === "alto" ? "alto" : ""}">impacto ${esc(a.impacto)}</span>
                <span class="chip">${esc(a.trigger)}</span>
              </div>
              <p class="muted">${esc(a.descricao)}</p>
              <p class="muted" style="font-size:0.8rem">Integrações: ${esc((a.integracao || []).join(", "))}</p>
              <div style="margin-top:0.75rem;display:flex;gap:0.5rem">
                <button type="button" class="btn ghost small btn-auto-toggle" data-id="${esc(a.id)}" data-status="${a.status === "ativo" ? "pausado" : "ativo"}">
                  ${a.status === "ativo" ? "Pausar" : "Ativar"}
                </button>
              </div>
            </div>`
            )
            .join("")}
        </div>`;

      document.querySelectorAll(".btn-auto-toggle").forEach((btn) => {
        btn.addEventListener("click", async () => {
          try {
            await window.DelegadoApi.setAutomationStatus(btn.dataset.id, btn.dataset.status);
            renderAutomations();
          } catch (e) {
            alert(e.message);
          }
        });
      });
    } catch (e) {
      el.innerHTML = `<p class="error">${esc(e.message)}</p>`;
    }
  }

  function esc(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function initAuth() {
    const loginScreen = $("#login-screen");
    const dashScreen = $("#dashboard-screen");

    const session = await window.DelegadoAuth.getSession();
    if (session?.user?.email) {
      try {
        window.DelegadoAuth.assertAllowedEmail(session.user.email);
        show(dashScreen);
        hide(loginScreen);
        $("#user-email").textContent = session.user.email;
        setTab("overview");
        return;
      } catch {
        await window.DelegadoAuth.signOut();
      }
    }

    show(loginScreen);
    hide(dashScreen);

    $("#login-email").value = cfg.allowedEmail || "";

    $("#btn-login").addEventListener("click", async () => {
      const errEl = $("#login-error");
      hide(errEl);
      try {
        const email = $("#login-email").value.trim();
        const password = $("#login-password").value;
        const s = await window.DelegadoAuth.signInWithPassword(email, password);
        show(dashScreen);
        hide(loginScreen);
        $("#user-email").textContent = s.user.email;
        setTab("overview");
      } catch (e) {
        errEl.textContent = e.message;
        show(errEl);
      }
    });

    $("#btn-logout").addEventListener("click", async () => {
      await window.DelegadoAuth.signOut();
      location.reload();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("#tabs")?.addEventListener("click", (e) => {
      const btn = e.target.closest(".tab");
      if (btn?.dataset.tab) setTab(btn.dataset.tab);
    });
    initAuth();
  });
})();
