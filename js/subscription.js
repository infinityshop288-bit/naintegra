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
      const session = await window.LexAuth.getSession();
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
    const data = await res.json();
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
    const data = await res.json();
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
        backUrlPath: "/lex/",
        statementDescriptor: "NAINTEGRA LEX",
      },
      false
    );
  }

  async function pollUntilApproved(subscriptionId, paymentId, onTick) {
    clearInterval(pollTimer);
    return new Promise((resolve, reject) => {
      let tries = 0;
      pollTimer = setInterval(async () => {
        tries += 1;
        try {
          const status = await checkPaymentStatus(paymentId);
          if (onTick) onTick(status);
          if (status.status === "approved") {
            clearInterval(pollTimer);
            const r = await invokeConfirm(subscriptionId, paymentId, "mercadopago");
            invalidateCache();
            resolve(r);
          } else if (tries > 120) {
            clearInterval(pollTimer);
            reject(new Error("Tempo esgotado aguardando pagamento PIX"));
          }
        } catch (e) {
          clearInterval(pollTimer);
          reject(e);
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
    container.innerHTML = renderPixPanel(pix, init.amount);
    bindPixCopy();
    await pollUntilApproved(init.subscriptionId, pix.paymentId, (r) => {
      const st = document.getElementById("pix-status");
      if (st && r.status === "approved") st.textContent = "Pagamento confirmado! Redirecionando…";
    });
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
      JSON.stringify({ subscriptionId: init.subscriptionId, planId })
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
    const paymentId = params.get("payment_id") || params.get("collection_id");
    if (!paymentId) return;
    if (paymentStatus !== "success" && paymentStatus !== "approved" && paymentStatus !== "pending") return;

    const raw = sessionStorage.getItem(PENDING_KEY);
    if (!raw) return;

    try {
      const pending = JSON.parse(raw);
      if (paymentStatus === "pending") {
        window.location.hash = "#/assinatura";
        return;
      }
      await invokeConfirm(pending.subscriptionId, paymentId, "mercadopago");
      sessionStorage.removeItem(PENDING_KEY);
      invalidateCache();
      cleanPaymentQuery();
      window.location.hash = "#/";
      window.location.reload();
    } catch (e) {
      console.warn("payment return:", e);
    }
  }

  function checkoutHtml(planId) {
    const plan = PLANS[planId] || PLANS["lex-mensal"];
    return `
      <section class="page checkout-page">
        <h1>Finalizar assinatura</h1>
        <p class="lead">Plano <strong>${esc(plan.label)}</strong> — ${formatBrl(plan.price)}/${esc(plan.period)}</p>
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

  function bindCheckout(planId) {
    const panel = document.getElementById("pay-panel");
    if (!panel) return;

    async function loadTab(tab) {
      panel.innerHTML = `<div class="loading-inline">Preparando pagamento…</div>`;
      document.querySelectorAll(".pay-tab").forEach((b) => {
        b.classList.toggle("active", b.dataset.payTab === tab);
      });
      try {
        if (tab === "pix") {
          const cpf = document.getElementById("pay-cpf")?.value || "";
          const cpfClean = cpf.replace(/\D/g, "");
          if (cpfClean.length !== 11) {
            panel.innerHTML = `<p class="auth-msg">Informe um CPF válido (11 dígitos) para gerar o PIX.</p>`;
            return;
          }
          await startPixCheckout(planId, panel, cpf);
        } else {
          await startCardCheckout(planId, panel);
        }
      } catch (e) {
        panel.innerHTML = `<p class="auth-msg">${esc(e.message)}</p>`;
      }
    }

    document.querySelectorAll(".pay-tab").forEach((btn) => {
      btn.addEventListener("click", () => loadTab(btn.dataset.payTab));
    });
    loadTab("pix");
  }

  async function renderAssinaturaPage(planId) {
    const user = await window.LexAuth.getUser();
    if (!user) {
      return `
        <section class="page checkout-page">
          <h1>Assine o NaIntegra Lex</h1>
          <p class="lead">Entre ou crie sua conta para continuar com o pagamento.</p>
          <button type="button" class="btn primary" id="checkout-auth-open">Entrar / Criar conta</button>
        </section>`;
    }
    if (await isSubscribed(true)) {
      return `
        <section class="page checkout-page">
          <h1>Assinatura ativa</h1>
          <p class="lead">Você já tem acesso completo ao NaIntegra Lex.</p>
          <a class="btn primary" href="#/">Ir para a plataforma</a>
        </section>`;
    }
    return checkoutHtml(planId || "lex-mensal");
  }

  function bindAssinaturaPage(planId) {
    document.getElementById("checkout-auth-open")?.addEventListener("click", () => {
      window.LexAuthUI?.open("login");
    });
    if (document.getElementById("pay-panel")) bindCheckout(planId || "lex-mensal");
  }

  handlePaymentReturn();

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
