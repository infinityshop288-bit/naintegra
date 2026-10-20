(function () {
  const COMMANDS = [
    { cmd: "/pesquisar ", label: "/pesquisar" },
    { cmd: "/elaborar ", label: "/elaborar" },
    { cmd: "/skill ", label: "/skill" },
    { cmd: "/gravar-skill ", label: "/gravar-skill" },
    { cmd: "/docs", label: "/docs" },
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
      .replace(/^## (.+)$/gm, "<h3>$1</h3>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\n\n/g, "</p><p>")
      .replace(/\n/g, "<br>");
    return `<p>${html}</p>`;
  }

  function apiBase() {
    if (location.port === "8770") return "";
    return window.LEX_CONFIG?.lexChatApi || "http://127.0.0.1:8770";
  }

  async function api(path, opts) {
    const res = await fetch(`${apiBase()}${path}`, {
      cache: "no-store",
      ...opts,
      headers: { "Content-Type": "application/json", ...(opts?.headers || {}) },
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || String(res.status));
    return data;
  }

  function render(state) {
    const skills = state.skills || [];
    const docs = state.docs || [];
    const messages = state.messages || [];
    const busy = Boolean(state.busy);
    const err = state.error || "";
    return `
      <div class="page-head">
        <h1>Chat Lex</h1>
        <p>Pesquise o acervo e elabore peças, pareceres e resumos por comando. Skills ficam gravadas em SKILL.md e podem ser reaplicadas.</p>
      </div>
      <div class="lex-chat">
        <aside class="lex-chat-side">
          <h2>Skills</h2>
          <label class="lex-chat-label">Ativa
            <select id="lex-chat-skill">
              <option value="">Nenhuma</option>
              ${skills
                .map(
                  (s) =>
                    `<option value="${esc(s.slug)}" ${state.skill === s.slug ? "selected" : ""}>${esc(s.name)}</option>`
                )
                .join("")}
            </select>
          </label>
          <ul class="lex-chat-skills">
            ${skills
              .map(
                (s) =>
                  `<li><button type="button" class="chip" data-use-skill="${esc(s.slug)}">${esc(s.name)}</button><small>${esc(s.description || "")}</small></li>`
              )
              .join("") || "<li>Nenhuma skill ainda.</li>"}
          </ul>
          <button type="button" class="btn btn-sm" id="lex-chat-new-skill">Gravar skill</button>
          <h2>Documentos</h2>
          <ul class="lex-chat-docs">
            ${docs
              .slice(0, 12)
              .map((d) => `<li><strong>${esc(d.title)}</strong><small>${esc(d.kind)} · ${esc((d.created_at || "").slice(0, 16))}</small></li>`)
              .join("") || "<li>Nenhum documento gravado.</li>"}
          </ul>
        </aside>
        <section class="lex-chat-main">
          <div class="toolbar">
            ${COMMANDS.map((c) => `<button type="button" class="chip" data-cmd="${esc(c.cmd)}">${esc(c.label)}</button>`).join("")}
          </div>
          <div class="lex-chat-log" id="lex-chat-log">
            ${
              messages
                .map(
                  (m) =>
                    `<article class="lex-chat-msg ${m.role}"><span>${m.role === "user" ? "Você" : "IA"}</span>${md(m.content)}</article>`
                )
                .join("") || `<div class="empty">Use /pesquisar, /elaborar ou escolha uma skill.</div>`
            }
          </div>
          ${err ? `<p class="pj-mon-err">${esc(err)}</p>` : ""}
          <form class="lex-chat-form" id="lex-chat-form">
            <textarea id="lex-chat-input" rows="3" placeholder="Ex.: /pesquisar art. 37 CF  ·  /elaborar parecer sobre improbidade  ·  /gravar-skill resumo-lei …" ${busy ? "disabled" : ""}></textarea>
            <button class="btn" type="submit" ${busy ? "disabled" : ""}>${busy ? "Elaborando…" : "Enviar"}</button>
          </form>
          <p class="tag">API em ${esc(apiBase() || location.origin)} · modelo gpt-5.6-sol. Se o chat falhar, rode <code>naintegra-lex-chat</code>.</p>
        </section>
      </div>
      <div class="lex-chat-modal" id="lex-chat-modal" hidden>
        <form id="lex-chat-skill-form" class="lex-chat-card">
          <h3>Gravar skill</h3>
          <label>Nome <input name="nome" required placeholder="parecer-mp" /></label>
          <label>Descrição <input name="descricao" placeholder="Quando usar esta skill" /></label>
          <label>Instruções <textarea name="instrucoes" rows="8" required placeholder="Como a IA deve elaborar…"></textarea></label>
          <div class="toolbar">
            <button class="btn" type="submit">Salvar SKILL.md</button>
            <button class="chip" type="button" id="lex-chat-cancel-skill">Cancelar</button>
          </div>
        </form>
      </div>`;
  }

  async function refreshMeta(state) {
    try {
      const [sk, docs] = await Promise.all([api("/api/lex-chat/skills"), api("/api/lex-chat/documentos")]);
      state.skills = sk.skills || [];
      state.docs = docs.documents || [];
      state.error = "";
    } catch (err) {
      state.error = `Servidor do chat indisponível (${err.message}). No terminal: naintegra-lex-chat`;
    }
  }

  function bind(state, redraw) {
    const log = document.getElementById("lex-chat-log");
    if (log) log.scrollTop = log.scrollHeight;
    document.getElementById("lex-chat-skill")?.addEventListener("change", (ev) => {
      state.skill = ev.target.value;
    });
    document.querySelectorAll("[data-use-skill]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.skill = btn.getAttribute("data-use-skill");
        const input = document.getElementById("lex-chat-input");
        if (input && !input.value.trim()) input.value = `/skill ${state.skill} `;
        input?.focus();
      });
    });
    document.querySelectorAll("[data-cmd]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const input = document.getElementById("lex-chat-input");
        if (!input) return;
        input.value = btn.getAttribute("data-cmd") || "";
        input.focus();
      });
    });
    document.getElementById("lex-chat-new-skill")?.addEventListener("click", () => {
      const modal = document.getElementById("lex-chat-modal");
      if (modal) modal.hidden = false;
    });
    document.getElementById("lex-chat-cancel-skill")?.addEventListener("click", () => {
      const modal = document.getElementById("lex-chat-modal");
      if (modal) modal.hidden = true;
    });
    document.getElementById("lex-chat-skill-form")?.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const fd = new FormData(ev.target);
      try {
        await api("/api/lex-chat/skills", {
          method: "POST",
          body: JSON.stringify({
            nome: fd.get("nome"),
            descricao: fd.get("descricao"),
            instrucoes: fd.get("instrucoes"),
          }),
        });
        document.getElementById("lex-chat-modal").hidden = true;
        await refreshMeta(state);
        redraw();
      } catch (err) {
        state.error = err.message;
        redraw();
      }
    });
    document.getElementById("lex-chat-form")?.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const input = document.getElementById("lex-chat-input");
      const text = (input?.value || "").trim();
      if (!text || state.busy) return;
      state.messages = state.messages || [];
      state.messages.push({ role: "user", content: text });
      state.busy = true;
      state.error = "";
      if (input) input.value = "";
      redraw();
      try {
        const out = await api("/api/lex-chat", {
          method: "POST",
          body: JSON.stringify({
            messages: state.messages.map((m) => ({ role: m.role, content: m.content })),
            skill: state.skill || "",
            model: "gpt-5.6-sol",
          }),
        });
        state.messages.push({ role: "assistant", content: out.text || "" });
        if (out.documents?.length || out.skills?.length) await refreshMeta(state);
      } catch (err) {
        state.error = err.message;
        state.messages.push({ role: "assistant", content: `Não consegui concluir: ${err.message}` });
      } finally {
        state.busy = false;
        redraw();
      }
    });
  }

  window.LexChat = { render, bind, refreshMeta, apiBase };
})();
