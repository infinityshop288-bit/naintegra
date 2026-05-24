/** Assinaturas NaIntegra Lex — checkout PIX e cartão via Mercado Pago (padrão VoltGo). */
(function () {
  const cfg = window.LEX_CONFIG;
  const PLANS = {
    "lex-mensal": { label: "Mensal", price: 19.9, cents: 1990, period: "mês" },
    "lex-anual": { label: "Anual", price: 199.9, cents: 19990, period: "ano", badge: "Economize 16%" },
  };

  const MP_CHECKOUT_HOSTS = [
    "www.mercadopago.com.br",
    "mercadopago.com.br",
    "www.mercadopago.com",
    "mercadopago.com",
  ];

  const PENDING_KEY = "lex_pending_checkout";

  let cachedSub = null;
  let pollTimer = null;

  function lexCanonicalBaseUrl() {
    const origin = (cfg.siteOrigin || window.location.origin).replace(/\/$/, "");
    const path = cfg.lexPublicPath || "/lex/";
    const normalized = path.startsWith("/") ? path : `/${path}`;
    return `${origin}${normalized.replace(/\/$/, "")}`;
  }

  function lexCheckoutReturnPath() {
    const path = cfg.lexPublicPath || "/lex/";
    const base = path.startsWith("/") ? path : `/${path}`;
    return `${base.endsWith("/") ? base : `${base}/`}index.html`;
  }

  function fnUrl(name) {
    return `${cfg.supabaseUrl}/functions/v1/${name}`;
  }

  async function edgeHeaders(requireUser) {
    const headers = {
      apikey: cfg.supabaseAnonKey,
      "Content-Type": "application/json",
      Authorization: `Bearer ${cfg.supabaseAnonKey}`,
    };
    if (requireUser) {
      const client = window.LexAuth.getClient();
      let session = await window.LexAuth.getSession();
      if (!session?.access_token) throw new Error("Faça login para continuar");
      const expiresAtMs = (session.expires_at || 0) * 1000;
      if (expiresAtMs - Date.now() < 120000) {
        const { data, error } = await client.auth.refreshSession();
        if (error) throw new Error("Sessão expirada. Entre novamente.");
        session = data.session;
      }
      if (!session?.access_token) throw new Error("Faça login para continuar");
      headers.Authorization = `Bearer ${session.access_token}`;
    }
    return headers;
  }

  async function invokeEdge(name, body, requireUser) {
    const res = await fetch(fnUrl(name), {
      method: "POST",
      headers: await edgeHeaders(requireUser),
      body: JSON.stringify(body),
    });
    let data;
    try {
      data = await res.json();
    } catch {
      throw new Error("Resposta inválida do servidor de pagamento");
    }
    if (!res.ok || data.error) throw new Error(data.error || "Erro ao processar pagamento");
    return data;
  }

  function isTrustedMercadoPagoCheckoutUrl(href) {
    try {
      const u = new URL(href);
      if (u.protocol !== "https:") return false;
      const h = u.hostname.toLowerCase();
      if (MP_CHECKOUT_HOSTS.includes(h)) return true;
      return (
        h.endsWith(".mercadopago.com.br") ||
        h.endsWith(".mercadopago.com") ||
        h.endsWith(".mercadolibre.com")
      );
    } catch {
      return false;
    }
  }

  function formatBrl(n) {
    return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }

  function esc(s) {
    const el = document.createElement("span");
    el.textContent = s ?? "";
    return el.innerHTML;
  }

  async function fetchActiveSubscription(force) {
    if (!force && cachedSub !== null) return cachedSub;
    const user = await window.LexAuth.getUser();
    if (!user) {
      cachedSub = null;
      return null;
    }
    const client = window.LexAuth.getClient();
    const now = new Date().toISOString();
    const { data, error } = await client
      .schema(cfg.lexSchema)
      .from("user_subscriptions")
      .select("id, plan_id, status, expires_at, starts_at")
      .eq("user_id", user.id)
      .eq("status", "active")
      .gt("expires_at", now)
      .order("expires_at", { ascending: false })
      .limit(1)
      .maybeSingle();
    if (error) {
      console.warn("subscription check:", error);
      cachedSub = null;
      return null;
    }
    cachedSub = data;
    return data;
  }

  async function isSubscribed(force) {
    const sub = await fetchActiveSubscription(force);
    return Boolean(sub);
  }

  function invalidateCache() {
    cachedSub = null;
  }

  async function fetchLastContentUpdate() {
    try {
      const client = window.LexAuth.getClient();
      const { data } = await client
        .schema(cfg.lexSchema)
        .from("content_metadata")
        .select("value")
        .eq("key", "last_content_update")
        .maybeSingle();
      if (data?.value) return new Date(data.value);
    } catch (e) {
      console.warn(e);
    }
    if (cfg.lastContentUpdate) return new Date(cfg.lastContentUpdate);
    return null;
  }

  function formatDatePt(d) {
    if (!d) return "—";
    return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
  }

  async function renderSidebarUpdate() {
    const el = document.getElementById("sidebar-last-update");
    if (!el) return;
    const d = await fetchLastContentUpdate();
    el.textContent = d ? `Acervo atualizado em ${formatDatePt(d)}` : "";
  }

  async function initCheckout(planId) {
    const res = await fetch(fnUrl("lex-subscription-checkout"), {
      method: "POST",
      headers: await edgeHeaders(true),
      body: JSON.stringify({ planId, provider: "init" }),
    });
    let data;
    try {
      data = await res.json();
    } catch {
      throw new Error("Erro ao iniciar assinatura");
    }
    if (!res.ok || !data.ok) throw new Error(data.error || "Erro ao iniciar assinatura");
    return data;
  }

  async function invokeConfirm(subscriptionId, paymentId, provider) {
    const res = await fetch(fnUrl("lex-subscription-confirm"), {
      method: "POST",
      headers: await edgeHeaders(true),
      body: JSON.stringify({ subscriptionId, paymentId, provider: provider || "mercadopago" }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Erro ao confirmar pagamento");
    return data;
  }

  async function reconcilePendingSubscription() {
    const res = await fetch(fnUrl("lex-subscription-confirm"), {
      method: "POST",
      headers: await edgeHeaders(true),
      body: JSON.stringify({ reconcile: true }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) return null;
    if (data.status === "active" && data.approved) {
      invalidateCache();
      return data;
    }
    return null;
  }

  function savePendingPixCheckout(subscriptionId, paymentId, amount) {
    sessionStorage.setItem(
      PENDING_KEY,
      JSON.stringify({ subscriptionId, paymentId, amount, provider: "pix", savedAt: Date.now() })
    );
  }

  function loadPendingPixCheckout() {
    try {
      const raw = sessionStorage.getItem(PENDING_KEY);
      if (!raw) return null;
      const data = JSON.parse(raw);
      if (data.provider !== "pix" || !data.subscriptionId || !data.paymentId) return null;
      if (Date.now() - (data.savedAt || 0) > 86400000) {
        sessionStorage.removeItem(PENDING_KEY);
        return null;
      }
      return data;
    } catch {
      return null;
    }
  }

  function clearPendingCheckout() {
    sessionStorage.removeItem(PENDING_KEY);
  }

  async function checkPaymentStatus(paymentId) {
    return invokeEdge("check-payment-status", { paymentId }, false);
  }

  async function createPixPayment(init, user, cpf) {
    return invokeEdge(
      "create-pix-payment",
      {
        amount: init.amount,
        description: `NaIntegra Lex — ${init.planName}`,
        payerEmail: user.email,
        payerName: window.LexAuth.userLabel(user),
        payerCpf: cpf.replace(/\D/g, ""),
        externalReference: init.externalReferencePix,
      },
      false
    );
  }

  async function createCardPayment(init, user) {
    return invokeEdge(
      "create-payment",
      {
        productName: `NaIntegra Lex — ${init.planName}`,
        productPrice: init.amount,
        payerEmail: user.email,
        payerName: window.LexAuth.userLabel(user),
        externalReference: init.externalReferenceCard,
        publicBaseUrl: lexCanonicalBaseUrl(),
        backUrlPath: lexCheckoutReturnPath(),
        statementDescriptor: "NAINTEGRA LEX",
      },
      false
    );
  }

  async function pollUntilApproved(subscriptionId, paymentId, onTick) {
    clearInterval(pollTimer);
    return new Promise((resolve, reject) => {
      let tries = 0;
      let transientErrors = 0;
      pollTimer = setInterval(async () => {
        tries += 1;
        try {
          const status = await checkPaymentStatus(paymentId);
          transientErrors = 0;
          if (onTick) onTick(status);
          if (status.status === "approved") {
            clearInterval(pollTimer);
            const r = await invokeConfirm(subscriptionId, paymentId, "mercadopago");
            clearPendingCheckout();
            invalidateCache();
            resolve(r);
          } else if (tries > 120) {
            clearInterval(pollTimer);
            reject(new Error("Tempo esgotado aguardando pagamento PIX"));
          }
        } catch (e) {
          transientErrors += 1;
          console.warn("pix poll:", e);
          if (transientErrors >= 6 || tries > 120) {
            clearInterval(pollTimer);
            reject(e);
          }
        }
      }, 5000);
    });
  }

  function renderPixPanel(data, amount) {
    const qr = data.qrCodeBase64
      ? `<img class="pix-qr" src="data:image/png;base64,${esc(data.qrCodeBase64)}" alt="QR Code PIX" />`
      : "";
    return `
      <div class="pay-pix-panel">
        ${qr}
        <p class="pay-amount">${formatBrl(amount)}</p>
        <p class="pay-hint">Escaneie o QR Code ou copie o código PIX</p>
        <div class="pix-copy-row">
          <input type="text" readonly class="pix-code" id="pix-copy-code" value="${esc(data.qrCode || "")}" />
          <button type="button" class="btn sm" id="pix-copy-btn">Copiar</button>
        </div>
        <p class="pay-status" id="pix-status">Aguardando pagamento…</p>
      </div>`;
  }

  function bindPixCopy() {
    document.getElementById("pix-copy-btn")?.addEventListener("click", async () => {
      const inp = document.getElementById("pix-copy-code");
      if (!inp) return;
      try {
        await navigator.clipboard.writeText(inp.value);
        document.getElementById("pix-copy-btn").textContent = "Copiado!";
      } catch {
        inp.select();
        document.execCommand("copy");
      }
    });
  }

  async function startPixCheckout(planId, container, cpf) {
    const user = await window.LexAuth.getUser();
    if (!user) throw new Error("Faça login para continuar");

    const init = await initCheckout(planId);
    const pix = await createPixPayment(init, user, cpf);
    savePendingPixCheckout(init.subscriptionId, pix.paymentId, init.amount);
    container.innerHTML = renderPixPanel(pix, init.amount);
    bindPixCopy();
    await pollUntilApproved(init.subscriptionId, pix.paymentId, (r) => {
      const st = document.getElementById("pix-status");
      if (st && r.status === "approved") st.textContent = "Pagamento confirmado! Redirecionando…";
    });
    clearPendingCheckout();
    window.location.hash = "#/";
    window.location.reload();
  }

  async function startCardCheckout(planId, container) {
    const user = await window.LexAuth.getUser();
    if (!user) throw new Error("Faça login para continuar");

    const init = await initCheckout(planId);
    const card = await createCardPayment(init, user);
    const initPoint = card.initPoint || card.sandboxInitPoint;
    if (!initPoint || !isTrustedMercadoPagoCheckoutUrl(initPoint)) {
      throw new Error("URL de checkout inválida");
    }
    sessionStorage.setItem(
      PENDING_KEY,
      JSON.stringify({
        subscriptionId: init.subscriptionId,
        planId,
        preferenceId: card.preferenceId || null,
        provider: "card",
        savedAt: Date.now(),
      })
    );
    container.innerHTML = `<p class="pay-hint">Redirecionando para o Mercado Pago…</p>`;
    window.location.assign(initPoint);
  }

  function cleanPaymentQuery() {
    const url = new URL(window.location.href);
    ["payment", "status", "collection_status", "payment_id", "collection_id", "preference_id", "external_reference"].forEach(
      (k) => url.searchParams.delete(k)
    );
    const clean = url.pathname + (url.search ? url.search : "") + (window.location.hash || "");
    window.history.replaceState({}, "", clean);
  }

  async function handlePaymentReturn() {
    const params = new URLSearchParams(window.location.search);
    const paymentStatus = params.get("payment") || params.get("status") || params.get("collection_status");
    if (!paymentStatus) return;

    const raw = sessionStorage.getItem(PENDING_KEY);
    const paymentId = params.get("payment_id") || params.get("collection_id");

    if (paymentStatus === "failure") {
      sessionStorage.removeItem(PENDING_KEY);
      cleanPaymentQuery();
      window.location.hash = "#/assinatura";
      return;
    }

    if (paymentStatus === "pending") {
      cleanPaymentQuery();
      window.location.hash = "#/assinatura";
      return;
    }

    if (paymentStatus !== "success" && paymentStatus !== "approved") return;

    cleanPaymentQuery();

    if (paymentId && raw) {
      try {
        const pending = JSON.parse(raw);
        await invokeConfirm(pending.subscriptionId, paymentId, "mercadopago");
        sessionStorage.removeItem(PENDING_KEY);
        invalidateCache();
        window.location.hash = "#/";
        window.location.reload();
        return;
      } catch (e) {
        console.warn("payment return confirm:", e);
        try {
          const reconciled = await reconcilePendingSubscription();
          if (reconciled?.status === "active") {
            sessionStorage.removeItem(PENDING_KEY);
            invalidateCache();
            window.location.hash = "#/";
            window.location.reload();
            return;
          }
        } catch (reconcileErr) {
          console.warn("payment return reconcile:", reconcileErr);
        }
      }
    }

    if (paymentStatus === "success" || paymentStatus === "approved") {
      try {
        const reconciled = await reconcilePendingSubscription();
        if (reconciled?.status === "active") {
          sessionStorage.removeItem(PENDING_KEY);
          invalidateCache();
          window.location.hash = "#/";
          window.location.reload();
          return;
        }
      } catch (e) {
        console.warn("payment return reconcile:", e);
      }
    }

    sessionStorage.removeItem(PENDING_KEY);
    window.location.hash = "#/assinatura";

    let tries = 0;
    const poll = setInterval(async () => {
      tries += 1;
      try {
        if (await isSubscribed(true)) {
          clearInterval(poll);
          invalidateCache();
          window.location.hash = "#/";
          window.location.reload();
        } else if (tries >= 24) {
          clearInterval(poll);
        }
      } catch (e) {
        console.warn("subscription poll:", e);
        if (tries >= 24) clearInterval(poll);
      }
    }, 5000);
  }

  async function tryResumePendingPixCheckout(container) {
    const pending = loadPendingPixCheckout();
    if (!pending || !container) return false;
    container.innerHTML = renderPixPanel(
      { qrCode: "", qrCodeBase64: "", amount: pending.amount },
      pending.amount
    );
    const st = document.getElementById("pix-status");
    if (st) st.textContent = "Retomando verificação do pagamento PIX…";
    try {
      await pollUntilApproved(pending.subscriptionId, pending.paymentId, (r) => {
        if (st && r.status === "approved") st.textContent = "Pagamento confirmado! Redirecionando…";
      });
      window.location.hash = "#/";
      window.location.reload();
      return true;
    } catch (e) {
      console.warn("resume pix checkout:", e);
      return false;
    }
  }

  async function tryReconcileOnLoad() {
    const user = await window.LexAuth.getUser();
    if (!user) return;
    if (await isSubscribed(false)) return;
    try {
      const r = await reconcilePendingSubscription();
      if (r?.status === "active") {
        window.location.hash = "#/";
        window.location.reload();
      }
    } catch (e) {
      console.warn("reconcile:", e);
    }
  }

  function normalizePlanId(planId) {
    return PLANS[planId] ? planId : "lex-mensal";
  }

  function planPickerHtml(selectedId) {
    const sel = normalizePlanId(selectedId);
    const mensal = PLANS["lex-mensal"];
    const anual = PLANS["lex-anual"];
    return `
      <div class="pay-plan-pick" role="group" aria-label="Escolha o plano">
        <button type="button" class="pay-plan-option ${sel === "lex-mensal" ? "active" : ""}" data-plan-pick="lex-mensal">
          <span class="pay-plan-name">Mensal</span>
          <span class="pay-plan-price">${formatBrl(mensal.price)}<small>/mês</small></span>
          <span class="pay-plan-note">Cancele quando quiser</span>
        </button>
        <button type="button" class="pay-plan-option ${sel === "lex-anual" ? "active" : ""}" data-plan-pick="lex-anual">
          <span class="pay-plan-name">Anual</span>
          <span class="pay-plan-price">${formatBrl(anual.price)}<small>/ano</small></span>
          <span class="pay-plan-note">≈ ${formatBrl(anual.price / 12)}/mês</span>
        </button>
      </div>`;
  }

  function bindPlanPicker(selectedId) {
    document.querySelectorAll("[data-plan-pick]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-plan-pick");
        if (!id || id === normalizePlanId(selectedId)) return;
        location.hash = `#/assinatura?plan=${encodeURIComponent(id)}`;
      });
    });
  }

  function checkoutHtml(planId) {
    const sel = normalizePlanId(planId);
    const plan = PLANS[sel];
    return `
      <section class="page checkout-page">
        <h1>Finalizar assinatura</h1>
        <p class="lead">Escolha o plano e a forma de pagamento.</p>
        ${planPickerHtml(sel)}
        <p class="pay-plan-summary">Plano <strong>${esc(plan.label)}</strong> — ${formatBrl(plan.price)}/${esc(plan.period)}</p>
        <div class="pay-cpf-row">
          <label for="pay-cpf">CPF (obrigatório para PIX)</label>
          <input type="text" id="pay-cpf" class="pix-code" inputmode="numeric" placeholder="000.000.000-00" maxlength="14" />
        </div>
        <div class="pay-tabs" role="tablist">
          <button type="button" class="pay-tab active" data-pay-tab="pix">PIX</button>
          <button type="button" class="pay-tab" data-pay-tab="card">Cartão</button>
        </div>
        <div id="pay-panel" class="pay-panel"></div>
        <p class="pay-legal">Ao pagar, você concorda com os termos de uso e política de privacidade do NaIntegra Cursos. O conteúdo é licenciado para uso pessoal — cópia e redistribuição são proibidas.</p>
      </section>`;
  }

  function checkoutLoginHtml(planId) {
    const sel = normalizePlanId(planId);
    const plan = PLANS[sel];
    return `
      <section class="page checkout-page">
        <h1>Assine o NaIntegra Lex</h1>
        <p class="lead">Escolha seu plano e entre na conta para continuar.</p>
        ${planPickerHtml(sel)}
        <p class="pay-plan-summary">Plano selecionado: <strong>${esc(plan.label)}</strong> — ${formatBrl(plan.price)}/${esc(plan.period)}</p>
        <button type="button" class="btn primary" id="checkout-auth-open">Entrar / Criar conta</button>
      </section>`;
  }

  function bindCheckout(planId) {
    const sel = normalizePlanId(planId);
    const panel = document.getElementById("pay-panel");
    if (!panel) return;

    let activeTab = "pix";

    function renderCheckoutUi() {
      if (activeTab === "pix") {
        panel.innerHTML = `
          <p class="pay-hint">Informe o CPF acima e clique para gerar o QR Code.</p>
          <button type="button" class="btn primary block" id="pay-action-btn">Gerar QR Code PIX</button>`;
      } else {
        panel.innerHTML = `
          <p class="pay-hint">Você será redirecionado ao Mercado Pago para pagar com cartão, Google Pay ou Apple Pay (até 12x).</p>
          <button type="button" class="btn primary block" id="pay-action-btn">Continuar para pagamento</button>`;
      }
      document.getElementById("pay-action-btn")?.addEventListener("click", runPayment);
    }

    function showPayError(message) {
      panel.innerHTML = `
        <p class="auth-msg">${esc(message)}</p>
        <button type="button" class="btn block" id="pay-retry">Tentar novamente</button>`;
      document.getElementById("pay-retry")?.addEventListener("click", renderCheckoutUi);
    }

    async function runPayment() {
      panel.innerHTML = `<div class="loading-inline">Preparando pagamento…</div>`;
      try {
        if (activeTab === "pix") {
          const cpf = document.getElementById("pay-cpf")?.value || "";
          const cpfClean = cpf.replace(/\D/g, "");
          if (cpfClean.length !== 11) {
            showPayError("Informe um CPF válido (11 dígitos) para gerar o PIX.");
            return;
          }
          await startPixCheckout(sel, panel, cpf);
        } else {
          await startCardCheckout(sel, panel);
        }
      } catch (e) {
        showPayError(e.message || "Erro ao processar pagamento");
      }
    }

    document.querySelectorAll(".pay-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeTab = btn.dataset.payTab || "pix";
        document.querySelectorAll(".pay-tab").forEach((b) => {
          b.classList.toggle("active", b.dataset.payTab === activeTab);
        });
        renderCheckoutUi();
      });
    });

    tryResumePendingPixCheckout(panel).then((resumed) => {
      if (!resumed) renderCheckoutUi();
    });
  }

  async function renderAssinaturaPage(planId) {
    const sel = normalizePlanId(planId);
    const user = await window.LexAuth.getUser();
    if (!user) return checkoutLoginHtml(sel);
    if (await isSubscribed(true)) {
      return `
        <section class="page checkout-page">
          <h1>Assinatura ativa</h1>
          <p class="lead">Você já tem acesso completo ao NaIntegra Lex.</p>
          <a class="btn primary" href="#/">Ir para a plataforma</a>
        </section>`;
    }
    return checkoutHtml(sel);
  }

  function bindAssinaturaPage(planId) {
    const sel = normalizePlanId(planId);
    bindPlanPicker(sel);
    document.getElementById("checkout-auth-open")?.addEventListener("click", () => {
      window.LexAuthUI?.open("login");
    });
    if (document.getElementById("pay-panel")) bindCheckout(sel);
  }

  handlePaymentReturn();
  tryReconcileOnLoad();

  window.LexSubscription = {
    PLANS,
    formatBrl,
    isSubscribed,
    fetchActiveSubscription,
    invalidateCache,
    renderSidebarUpdate,
    renderAssinaturaPage,
    bindAssinaturaPage,
    formatDatePt,
    fetchLastContentUpdate,
  };
})();
