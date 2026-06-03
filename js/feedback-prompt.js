/**
 * Convite de feedback / avaliação na Play Store (recomendação Testers Community).
 */
(function () {
  const DISMISS_KEY = "lex_feedback_dismissed";
  const SESSIONS_KEY = "lex_session_count";
  const SHOWN_KEY = "lex_feedback_shown_at";
  const MIN_SESSIONS = 4;
  const COOLDOWN_MS = 30 * 24 * 60 * 60 * 1000;

  function playStoreUrl() {
    return (
      window.LEX_CONFIG?.playStoreUrl ||
      "https://play.google.com/store/apps/details?id=br.com.naintegracursos.lex"
    );
  }

  function bumpSession() {
    try {
      const n = parseInt(localStorage.getItem(SESSIONS_KEY) || "0", 10) + 1;
      localStorage.setItem(SESSIONS_KEY, String(n));
      return n;
    } catch {
      return 0;
    }
  }

  function shouldShow() {
    try {
      if (localStorage.getItem(DISMISS_KEY) === "1") return false;
      const shown = parseInt(localStorage.getItem(SHOWN_KEY) || "0", 10);
      if (shown && Date.now() - shown < COOLDOWN_MS) return false;
      const sessions = parseInt(localStorage.getItem(SESSIONS_KEY) || "0", 10);
      return sessions >= MIN_SESSIONS;
    } catch {
      return false;
    }
  }

  function markShown() {
    try {
      localStorage.setItem(SHOWN_KEY, String(Date.now()));
    } catch (_) {
      /* ignore */
    }
  }

  function dismissPermanent() {
    try {
      localStorage.setItem(DISMISS_KEY, "1");
    } catch (_) {
      /* ignore */
    }
    remove();
  }

  function remove() {
    document.getElementById("lex-feedback-banner")?.remove();
  }

  function esc(s) {
    const el = document.createElement("span");
    el.textContent = s ?? "";
    return el.innerHTML;
  }

  function render() {
    if (!shouldShow()) return;
    remove();
    const host = document.getElementById("app") || document.getElementById("main");
    if (!host) return;

    const banner = document.createElement("div");
    banner.id = "lex-feedback-banner";
    banner.className = "lex-feedback-banner";
    banner.setAttribute("role", "region");
    banner.setAttribute("aria-label", "Avalie o aplicativo");
    banner.innerHTML = `
      <div class="lex-feedback-inner">
        <p><strong>O Lex está ajudando nos seus estudos?</strong> Sua avaliação na Play Store ajuda outros concurseiros a encontrarem o app.</p>
        <div class="lex-feedback-actions">
          <a class="btn sm primary" href="${esc(playStoreUrl())}" target="_blank" rel="noopener noreferrer" data-feedback-rate>Avaliar na Play Store</a>
          <a class="btn sm" href="#/contato" data-feedback-contact>Sugerir melhoria</a>
          <button type="button" class="btn sm" data-feedback-later>Agora não</button>
          <button type="button" class="link-btn" data-feedback-dismiss>Não perguntar de novo</button>
        </div>
        <button type="button" class="lex-feedback-close" aria-label="Fechar">×</button>
      </div>`;

    host.insertAdjacentElement("afterbegin", banner);
    markShown();

    banner.querySelector("[data-feedback-rate]")?.addEventListener("click", () => dismissPermanent());
    banner.querySelector("[data-feedback-later]")?.addEventListener("click", () => remove());
    banner.querySelector("[data-feedback-dismiss]")?.addEventListener("click", () => dismissPermanent());
    banner.querySelector(".lex-feedback-close")?.addEventListener("click", () => remove());
  }

  function init() {
    bumpSession();
    requestAnimationFrame(() => {
      setTimeout(render, 1200);
    });
  }

  window.LexFeedbackPrompt = {
    init,
    render,
    dismissPermanent,
    bumpSession,
    playStoreUrl,
  };
})();
