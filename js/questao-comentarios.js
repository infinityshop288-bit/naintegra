/** Comentários públicos em questões (lex.questao_comentarios). */
(function () {
  const cfg = () => window.LEX_CONFIG || {};
  const cache = new Map();
  let inflight = null;

  function escHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  function headers(token, extra) {
    return {
      apikey: cfg().supabaseAnonKey,
      Authorization: `Bearer ${token || cfg().supabaseAnonKey}`,
      Accept: "application/json",
      "Content-Type": "application/json",
      "Accept-Profile": cfg().lexSchema,
      "Content-Profile": cfg().lexSchema,
      ...(extra || {}),
    };
  }

  function authorName(user) {
    return user?.user_metadata?.full_name || user?.email?.split("@")[0] || "Estudante";
  }

  function formatWhen(iso) {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleString("pt-BR", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  }

  function inFilter(qids) {
    const list = (qids || [])
      .map((id) => `"${String(id).replace(/"/g, "")}"`)
      .join(",");
    return encodeURIComponent(`in.(${list})`);
  }

  async function fetchForQuestions(qids, { force = false } = {}) {
    const ids = [...new Set((qids || []).map(String).filter(Boolean))];
    const missing = force ? ids : ids.filter((id) => !cache.has(id));
    if (!missing.length) return cache;

    if (inflight) await inflight;

    inflight = (async () => {
      const res = await fetch(
        `${cfg().supabaseUrl}/rest/v1/questao_comentarios?question_id=${inFilter(missing)}&select=id,question_id,user_id,author_name,body,created_at,updated_at&order=created_at.asc`,
        { headers: headers() }
      );
      if (!res.ok) {
        console.warn("LexQuestaoComentarios fetch:", res.status, await res.text().catch(() => ""));
        for (const id of missing) {
          if (!cache.has(id)) cache.set(id, []);
        }
        return;
      }
      const rows = await res.json();
      for (const id of missing) cache.set(id, []);
      for (const row of rows || []) {
        const qid = String(row.question_id);
        if (!cache.has(qid)) cache.set(qid, []);
        cache.get(qid).push(row);
      }
    })();

    try {
      await inflight;
    } finally {
      inflight = null;
    }
    return cache;
  }

  function getComments(qid) {
    return cache.get(String(qid)) || [];
  }

  function renderSection(qid, { user, editingId = null } = {}) {
    const comments = getComments(qid);
    const uid = user?.id || null;
    const mine = uid ? comments.find((c) => c.user_id === uid) : null;
    const others = uid ? comments.filter((c) => c.user_id !== uid) : comments;
    const ordered = mine ? [...others, mine] : others;

    const list =
      ordered.length > 0
        ? `<div class="q-comments-list">
        ${ordered
          .map((c) => {
            const own = uid && c.user_id === uid;
            const editing = editingId === c.id;
            if (editing) {
              return `
              <article class="q-comment q-comment--edit" data-comment-id="${escHtml(c.id)}">
                <form class="q-comment-edit-form" data-qid="${escHtml(qid)}" data-comment-id="${escHtml(c.id)}">
                  <textarea name="body" rows="3" required maxlength="4000">${escHtml(c.body)}</textarea>
                  <div class="q-comment-form-actions">
                    <button type="button" class="btn q-comment-cancel" data-qid="${escHtml(qid)}">Cancelar</button>
                    <button type="submit" class="btn primary">Salvar</button>
                  </div>
                </form>
              </article>`;
            }
            return `
            <article class="q-comment ${own ? "q-comment--own" : ""}" data-comment-id="${escHtml(c.id)}">
              <header class="q-comment-head">
                <strong>${escHtml(c.author_name || "Estudante")}</strong>
                ${own ? `<span class="q-comment-you">você</span>` : ""}
                <time datetime="${escHtml(c.updated_at || c.created_at)}">${escHtml(formatWhen(c.updated_at || c.created_at))}</time>
              </header>
              <p class="q-comment-body">${escHtml(c.body)}</p>
              ${
                own
                  ? `<div class="q-comment-actions">
                  <button type="button" class="btn btn-sm q-comment-edit" data-qid="${escHtml(qid)}" data-comment-id="${escHtml(c.id)}">Editar</button>
                  <button type="button" class="btn btn-sm err q-comment-delete" data-comment-id="${escHtml(c.id)}" data-qid="${escHtml(qid)}">Excluir</button>
                </div>`
                  : ""
              }
            </article>`;
          })
          .join("")}
      </div>`
        : `<p class="q-comments-empty">Nenhum comentário ainda. Seja o primeiro a compartilhar uma dica.</p>`;

    const compose =
      uid && !mine
        ? `<form class="q-comment-form" data-qid="${escHtml(qid)}">
        <label class="q-comment-compose-label">Seu comentário <small>(visível para todos)</small></label>
        <textarea name="body" rows="3" required maxlength="4000" placeholder="Compartilhe dicas, pegadinhas ou raciocínio…"></textarea>
        <button type="submit" class="btn primary">Publicar comentário</button>
      </form>`
        : uid && mine
          ? ""
          : `<p class="q-comments-login"><a href="#/auth">Faça login</a> para publicar um comentário visível a todos.</p>`;

    return `
      <section class="q-comments" data-q-comments="${escHtml(qid)}" aria-label="Comentários da comunidade">
        <h4 class="q-comments-title">Comentários da comunidade <span class="q-comments-count">${comments.length}</span></h4>
        ${list}
        ${compose}
      </section>`;
  }

  async function publishComment(qid, body, session) {
    if (!session?.user?.id || !session.access_token) {
      throw new Error("login_required");
    }
    const text = String(body || "").trim();
    if (!text) throw new Error("empty");

    const payload = {
      question_id: String(qid),
      user_id: session.user.id,
      author_name: authorName(session.user),
      body: text,
    };

    const res = await fetch(`${cfg().supabaseUrl}/rest/v1/questao_comentarios`, {
      method: "POST",
      headers: headers(session.access_token, {
        Prefer: "resolution=merge-duplicates,return=representation",
      }),
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`publish ${res.status}: ${await res.text().catch(() => "")}`);
    }
    const rows = await res.json();
    const row = Array.isArray(rows) ? rows[0] : rows;
    const list = cache.get(String(qid)) || [];
    const idx = list.findIndex((c) => c.user_id === session.user.id);
    if (idx >= 0) list[idx] = row;
    else list.push(row);
    cache.set(String(qid), list);
    return row;
  }

  async function deleteComment(commentId, qid, session) {
    if (!session?.access_token) throw new Error("login_required");
    const res = await fetch(
      `${cfg().supabaseUrl}/rest/v1/questao_comentarios?id=eq.${encodeURIComponent(commentId)}`,
      { method: "DELETE", headers: headers(session.access_token, { Prefer: "return=minimal" }) }
    );
    if (!res.ok) throw new Error(`delete ${res.status}`);
    const list = (cache.get(String(qid)) || []).filter((c) => c.id !== commentId);
    cache.set(String(qid), list);
  }

  function invalidate(qid) {
    if (qid) cache.delete(String(qid));
    else cache.clear();
  }

  window.LexQuestaoComentarios = {
    fetchForQuestions,
    getComments,
    renderSection,
    publishComment,
    deleteComment,
    invalidate,
    formatWhen,
  };
})();
