/** Modal e painel inline de autenticação — login, cadastro, Google e Apple. */
(function () {
  const VIEWS = ["login", "signup", "recover", "reset-password"];

  function esc(s) {
    const el = document.createElement("span");
    el.textContent = s ?? "";
    return el.innerHTML;
  }

  function authFormFieldsHtml(view) {
    if (view === "reset-password") {
      return `
        <form class="auth-form" data-auth-form="1">
          <label>Nova senha<input type="password" name="password" required minlength="6" autocomplete="new-password" /></label>
          <label>Confirmar senha<input type="password" name="password2" required minlength="6" autocomplete="new-password" /></label>
          <button type="submit" class="btn primary auth-submit">Salvar nova senha</button>
        </form>`;
    }
    if (view === "recover") {
      return `
        <form class="auth-form" data-auth-form="1">
          <label>E-mail<input type="email" name="email" required autocomplete="email" /></label>
          <button type="submit" class="btn primary auth-submit">Enviar link de recuperação</button>
          <p class="auth-switch"><button type="button" class="link-btn" data-auth-view="login">← Voltar ao login</button></p>
        </form>`;
    }
    return `
      <form class="auth-form" data-auth-form="1">
        <label>E-mail<input type="email" name="email" required autocomplete="email" /></label>
        <label>Senha<input type="password" name="password" required minlength="6" autocomplete="${view === "signup" ? "new-password" : "current-password"}" /></label>
        ${
          view === "login"
            ? `<p class="auth-switch"><button type="button" class="link-btn" data-auth-view="recover">Esqueci minha senha</button></p>`
            : ""
        }
        <button type="submit" class="btn primary auth-submit">${view === "signup" ? "Criar conta" : "Entrar"}</button>
        <p class="auth-switch">
          ${
            view === "signup"
              ? `<button type="button" class="link-btn" data-auth-view="login">Já tenho conta</button>`
              : `<button type="button" class="link-btn" data-auth-view="signup">Criar conta</button>`
          }
        </p>
      </form>
      <div class="auth-oauth">
        <p class="auth-oauth-label">ou continue com</p>
        <div class="auth-oauth-btns">
          <button type="button" class="btn oauth google" data-oauth="google">Google</button>
          <button type="button" class="btn oauth apple" data-oauth="apple">Apple</button>
        </div>
      </div>`;
  }

  function inlineAuthHtml(view, msg) {
    return `
      <div class="landing-auth-panel" id="entrar">
        <div class="landing-auth-tabs" role="tablist">
          <button type="button" class="landing-auth-tab ${view === "login" ? "active" : ""}" data-landing-auth-view="login">Entrar</button>
          <button type="button" class="landing-auth-tab ${view === "signup" ? "active" : ""}" data-landing-auth-view="signup">Criar conta</button>
        </div>
        <h2 class="landing-auth-title">${view === "signup" ? "Criar conta" : "Entrar"}</h2>
        ${msg ? `<p class="auth-msg">${esc(msg)}</p>` : ""}
        ${authFormFieldsHtml(view)}
      </div>`;
  }

  function modalHtml(view, msg) {
    const titles = {
      login: "Entrar na sua conta",
      signup: "Criar conta",
      recover: "Recuperar senha",
      "reset-password": "Definir nova senha",
    };
    return `
      <div class="auth-modal-backdrop" id="auth-modal-backdrop">
        <div class="auth-modal" role="dialog" aria-labelledby="auth-title">
          <button type="button" class="auth-close" id="auth-close" aria-label="Fechar">×</button>
          <h2 id="auth-title" class="auth-title">${esc(titles[view] || "Conta")}</h2>
          ${msg ? `<p class="auth-msg">${esc(msg)}</p>` : ""}
          ${authFormFieldsHtml(view)}
        </div>
      </div>`;
  }

  function bindAuthContainer(container, view, opts) {
    const onViewChange = opts?.onViewChange || ((next) => open(next));
    const onSuccess = opts?.onSuccess || (() => close());
    const showModalViews = opts?.modal !== false;

    container.querySelectorAll("[data-auth-view]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const next = btn.getAttribute("data-auth-view");
        if (showModalViews || next === "recover") {
          onViewChange(next);
        }
      });
    });

    container.querySelectorAll("[data-oauth]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await window.LexAuth.signInWithOAuth(btn.getAttribute("data-oauth"));
        } catch (err) {
          onViewChange(view, err.message || "Não foi possível iniciar login social.");
        }
      });
    });

    const form = container.querySelector("[data-auth-form]");
    form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const email = String(fd.get("email") || "").trim();
      const password = String(fd.get("password") || "");
      const submit = form.querySelector(".auth-submit");
      if (submit) submit.disabled = true;
      form.querySelector(".auth-error")?.remove();
      try {
        if (view === "login") {
          await window.LexAuth.signInWithPassword(email, password);
          onSuccess();
        } else if (view === "signup") {
          await window.LexAuth.signUp(email, password);
          onViewChange("login", "Conta criada. Confirme seu e-mail se solicitado e faça login.");
        } else if (view === "recover") {
          await window.LexAuth.resetPassword(email);
          onViewChange("login", "Enviamos um link de recuperação para seu e-mail.");
        } else if (view === "reset-password") {
          const p2 = String(fd.get("password2") || "");
          if (password !== p2) throw new Error("As senhas não coincidem.");
          await window.LexAuth.updatePassword(password);
          onSuccess();
          location.hash = "#/";
        }
      } catch (err) {
        const msgEl = document.createElement("p");
        msgEl.className = "auth-error";
        msgEl.textContent = err.message || "Erro ao autenticar.";
        form.prepend(msgEl);
      } finally {
        if (submit) submit.disabled = false;
      }
    });
  }

  function bindTopbarPublicNav() {
    document.querySelectorAll(".topbar-public-nav [data-scroll-to]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.preventDefault();
        if (!document.body.classList.contains("lex-public-mode")) {
          location.hash = "#/";
          setTimeout(() => {
            document.getElementById(el.getAttribute("data-scroll-to"))?.scrollIntoView({ behavior: "smooth", block: "start" });
          }, 50);
          return;
        }
        document.getElementById(el.getAttribute("data-scroll-to"))?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }

  function scrollToLandingAuth(view) {
    const target = document.getElementById("entrar") || document.getElementById("landing-auth-root");
    target?.scrollIntoView({ behavior: "smooth", block: "start" });
    const root = document.getElementById("landing-auth-root");
    if (root) mountLandingAuth(root, view || "login");
  }

  async function renderTopbarUser(user) {
    const slot = document.getElementById("auth-slot");
    if (!slot) return;
    if (user) {
      const subscribed = window.LexSubscription ? await window.LexSubscription.isSubscribed() : false;
      slot.innerHTML = `
        <div class="auth-user">
          <span class="auth-user-name" title="${esc(user.email || "")}">${esc(window.LexAuth.userLabel(user))}</span>
          ${subscribed ? "" : '<a class="btn sm primary" href="#/assinatura?plan=lex-anual">Assinar</a>'}
          <button type="button" class="btn sm" id="auth-logout">Sair</button>
        </div>`;
      document.getElementById("auth-logout")?.addEventListener("click", async () => {
        await window.LexAuth.signOut();
      });
    } else {
      slot.innerHTML = `
        <button type="button" class="btn sm" id="auth-signup-open">Criar conta</button>
        <button type="button" class="btn sm primary" id="auth-open">Entrar</button>`;
      document.getElementById("auth-open")?.addEventListener("click", () => {
        if (document.body.classList.contains("lex-public-mode")) scrollToLandingAuth("login");
        else open("login");
      });
      document.getElementById("auth-signup-open")?.addEventListener("click", () => {
        if (document.body.classList.contains("lex-public-mode")) scrollToLandingAuth("signup");
        else open("signup");
      });
      bindTopbarPublicNav();
    }
  }

  function close() {
    document.getElementById("auth-modal-root")?.replaceChildren();
  }

  function open(view, msg) {
    const root = document.getElementById("auth-modal-root");
    if (!root) return;
    root.innerHTML = modalHtml(view, msg);
    bindAuthContainer(root, view, {
      modal: true,
      onViewChange: (next, message) => open(next, message),
      onSuccess: close,
    });
    document.getElementById("auth-close")?.addEventListener("click", close);
    document.getElementById("auth-modal-backdrop")?.addEventListener("click", (e) => {
      if (e.target.id === "auth-modal-backdrop") close();
    });
  }

  function mountLandingAuth(container, initialView, msg) {
    if (!container) return;
    let view = initialView || "login";
    const paint = (nextView, nextMsg) => {
      view = nextView || view;
      container.innerHTML = inlineAuthHtml(view, nextMsg);
      bindAuthContainer(container, view, {
        modal: false,
        onViewChange: (next, message) => paint(next, message),
        onSuccess: () => {},
      });
      container.querySelectorAll("[data-landing-auth-view]").forEach((btn) => {
        btn.addEventListener("click", () => {
          paint(btn.getAttribute("data-landing-auth-view"));
        });
      });
    };
    paint(initialView, msg);
  }

  async function init(onSession) {
    await renderTopbarUser(null);
    const session = await window.LexAuth.getSession().catch(() => null);
    await renderTopbarUser(session?.user ?? null);
    if (onSession) await onSession(session);

    window.LexAuth.onAuthStateChange(async (sess) => {
      await renderTopbarUser(sess?.user ?? null);
      if (onSession) await onSession(sess);
      if (location.hash.includes("/assinatura") && window.LexSubscription) {
        const r = location.hash.replace(/^#/, "") || "/";
        const qIdx = r.indexOf("?");
        const params = new URLSearchParams(qIdx >= 0 ? r.slice(qIdx + 1) : "");
        const planId = params.get("plan") || "lex-mensal";
        const html = await window.LexSubscription.renderAssinaturaPage(planId);
        const app = document.getElementById("app");
        if (app) app.innerHTML = html;
        window.LexSubscription.bindAssinaturaPage(planId);
      }
    });

    if (location.hash.includes("auth/reset-password")) {
      open("reset-password");
    } else if (location.hash.includes("auth/login")) {
      if (document.body.classList.contains("lex-public-mode")) {
        scrollToLandingAuth("login");
      } else {
        open("login");
      }
    }
  }

  window.LexAuthUI = { init, open, close, renderTopbarUser, mountLandingAuth, scrollToLandingAuth };
})();
