/**
 * Tour guiado para novos usuários (feedback Google Play / Testers Community).
 */
(function () {
  const STORAGE_KEY = "lex_onboarding_v2";

  const STEPS = [
    {
      title: "Bem-vindo ao NaIntegra Lex",
      body: "Estude legislação, jurisprudência, flashcards e questões para concursos de segurança pública. Tudo gratuito, sem anúncios e sem precisar de conta.",
      icon: "📚",
    },
    {
      title: "Lei seca",
      body: "Leia leis na íntegra, grife trechos, anote e use a narração em áudio artigo a artigo — ideal para revisar no trânsito.",
      icon: "⚖️",
      go: "lei-seca",
    },
    {
      title: "Jurisprudência e favoritos",
      body: "Súmulas e temas do STF/STJ com leitor organizado. Marque precedentes com ★ e revise tudo na página Favoritos.",
      icon: "★",
      go: "jurisprudencia",
    },
    {
      title: "Flashcards e questões",
      body: "Revise com repetição espaçada (SM-2) e treine com questões filtradas por banca, com gabarito e comentários.",
      icon: "🎯",
      go: "flashcards",
    },
    {
      title: "Plano de estudos",
      body: "Monte uma trilha por carreira (Delegado, Magistratura, etc.) com metas diárias de lei, juris e questões.",
      icon: "🗓️",
      go: "plano-estudos",
    },
    {
      title: "Buscar e referências",
      body: "Use Buscar no topo para localizar texto na página. Toque em citações de leis e súmulas para ver o trecho em um balão.",
      icon: "🔍",
    },
    {
      title: "Sincronize seu progresso (opcional)",
      body: "Se quiser usar o app em mais de um aparelho, crie uma conta para salvar grifos, anotações e favoritos na nuvem. É opcional — sem conta, tudo fica salvo no próprio aparelho.",
      icon: "☁️",
    },
  ];

  let overlayEl = null;
  let stepIndex = 0;
  let onComplete = null;

  function playStoreUrl() {
    return (
      window.LEX_CONFIG?.playStoreUrl ||
      "https://play.google.com/store/apps/details?id=br.com.naintegracursos.lex"
    );
  }

  function isDone() {
    try {
      return Boolean(localStorage.getItem(STORAGE_KEY));
    } catch {
      return false;
    }
  }

  function markDone() {
    try {
      localStorage.setItem(STORAGE_KEY, String(Date.now()));
    } catch (_) {
      /* ignore */
    }
  }

  function reset() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (_) {
      /* ignore */
    }
  }

  function esc(s) {
    const el = document.createElement("span");
    el.textContent = s ?? "";
    return el.innerHTML;
  }

  function removeOverlay() {
    overlayEl?.remove();
    overlayEl = null;
    document.body.classList.remove("lex-onboarding-open");
  }

  function finish(skipped) {
    if (!skipped) markDone();
    removeOverlay();
    if (typeof onComplete === "function") onComplete(skipped);
    onComplete = null;
  }

  function renderStep() {
    if (!overlayEl) return;
    const step = STEPS[stepIndex];
    const isLast = stepIndex >= STEPS.length - 1;
    const dots = STEPS.map(
      (_, i) =>
        `<span class="lex-onboarding-dot${i === stepIndex ? " active" : ""}" aria-hidden="true"></span>`
    ).join("");

    overlayEl.innerHTML = `
      <div class="lex-onboarding-backdrop" data-onboarding-backdrop></div>
      <div class="lex-onboarding-card" role="dialog" aria-labelledby="lex-onboarding-title" aria-modal="true">
        <button type="button" class="lex-onboarding-close" data-onboarding-close aria-label="Fechar tour">×</button>
        <div class="lex-onboarding-icon" aria-hidden="true">${esc(step.icon)}</div>
        <p class="lex-onboarding-step">Passo ${stepIndex + 1} de ${STEPS.length}</p>
        <h2 id="lex-onboarding-title" class="lex-onboarding-title">${esc(step.title)}</h2>
        <p class="lex-onboarding-body">${esc(step.body)}</p>
        <div class="lex-onboarding-dots" aria-hidden="true">${dots}</div>
        <div class="lex-onboarding-actions">
          <button type="button" class="btn" data-onboarding-skip>Pular tour</button>
          ${
            step.go
              ? `<button type="button" class="btn" data-onboarding-peek>Ver ${esc(step.title.split(" ")[0])}</button>`
              : ""
          }
          <button type="button" class="btn primary" data-onboarding-next>
            ${isLast ? "Começar a estudar" : "Próximo"}
          </button>
        </div>
      </div>`;

    overlayEl.querySelector("[data-onboarding-close]")?.addEventListener("click", () => finish(true));
    overlayEl.querySelector("[data-onboarding-skip]")?.addEventListener("click", () => finish(true));
    overlayEl.querySelector("[data-onboarding-backdrop]")?.addEventListener("click", () => finish(true));
    overlayEl.querySelector("[data-onboarding-peek]")?.addEventListener("click", () => {
      if (step.go) location.hash = `#/${step.go}`;
    });
    overlayEl.querySelector("[data-onboarding-next]")?.addEventListener("click", () => {
      if (isLast) finish(false);
      else {
        stepIndex += 1;
        renderStep();
      }
    });
  }

  function show(opts = {}) {
    if (opts.force !== true && isDone()) return false;
    removeOverlay();
    stepIndex = 0;
    onComplete = opts.onComplete || null;
    overlayEl = document.createElement("div");
    overlayEl.id = "lex-onboarding";
    overlayEl.className = "lex-onboarding";
    document.body.appendChild(overlayEl);
    document.body.classList.add("lex-onboarding-open");
    renderStep();
    return true;
  }

  /** Exibir tour na home. */
  function maybeShow() {
    if (isDone()) return false;
    const path = (location.hash.replace(/^#/, "") || "/").split("?")[0];
    if (path !== "/" && path !== "") return false;
    if (!document.querySelector(".tiles")) return false;
    return show();
  }

  window.LexOnboarding = {
    STORAGE_KEY,
    STEPS,
    isDone,
    markDone,
    reset,
    show,
    maybeShow,
    playStoreUrl,
  };
})();
