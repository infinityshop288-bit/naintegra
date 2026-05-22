/** Assinaturas NaIntegra Lex — checkout Pix e cartão (Stripe + wallets). */
(function () {
  const cfg = window.LEX_CONFIG;
  const PLANS = {
    "lex-mensal": { label: "Mensal", price: 19.9, cents: 1990, period: "mês" },
    "lex-anual": { label: "Anual", price: 199.9, cents: 19990, period: "ano", badge: "Economize 16%" },
  };

  let cachedSub = null;
  let stripe = null;
  let elements = null;
  let pollTimer = null;

  function fnUrl(name) {
    return `${cfg.supabaseUrl}/functions/v1/${name}`;
  }

  async function authHeaders() {
    const session = await window.LexAuth.getSession();
    if (!session?.access_token) throw new Error("Faça login para continuar");
    return {
      Authorization: `Bearer ${session.access_token}`,
      apikey: cfg.supabaseAnonKey,
      "Content-Type": "application/json",
    };
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

  async function invokeCheckout(planId, provider) {
    const headers = await authHeaders();
    const res = await fetch(fnUrl("lex-subscription-checkout"), {
      method: "POST",
      headers,
      body: JSON.stringify({ planId, provider }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Erro ao iniciar pagamento");
    return data;
  }

  async function invokeConfirm(subscriptionId, paymentId, provider) {
    const headers = await authHeaders();
    const res = await fetch(fnUrl("lex-subscription-confirm"), {
      method: "POST",
      headers,
      body: JSON.stringify({ subscriptionId, paymentId, provider }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Erro ao confirmar pagamento");
    return data;
  }

  async function pollUntilApproved(subscriptionId, paymentId, provider, onTick) {
    clearInterval(pollTimer);
    return new Promise((resolve, reject) => {
      let tries = 0;
      pollTimer = setInterval(async () => {
        tries += 1;
        try {
          const r = await invokeConfirm(subscriptionId, paymentId, provider);
          if (onTick) onTick(r);
          if (r.approved || r.status === "active") {
            clearInterval(pollTimer);
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
      }, 3000);
    });
  }

  async function ensureStripe(pk) {
    if (!pk) throw new Error("Stripe não configurado");
    if (!window.Stripe) {
      await new Promise((resolve, reject) => {
        const s = document.createElement("script");
        s.src = "https://js.stripe.com/v3/";
        s.onload = resolve;
        s.onerror = () => reject(new Error("Falha ao carregar Stripe"));
        document.head.appendChild(s);
      });
    }
    if (!stripe || stripe._pk !== pk) {
      stripe = window.Stripe(pk);
      stripe._pk = pk;
    }
    return stripe;
  }

  async function mountCardCheckout(container, checkoutData) {
    const st = await ensureStripe(checkoutData.stripePublishableKey);
    elements = st.elements({ clientSecret: checkoutData.clientSecret, locale: "pt-BR" });
    container.innerHTML = `<div id="stripe-payment-element"></div><button type="button" class="btn primary pay-submit" id="stripe-pay-btn">Pagar ${formatBrl(checkoutData.amount)}</button><p class="pay-hint">Google Pay, Apple Pay e cartão aceitos</p>`;
    const paymentElement = elements.create("payment", {
      wallets: { applePay: "auto", googlePay: "auto" },
    });
    paymentElement.mount("#stripe-payment-element");
    const btn = document.getElementById("stripe-pay-btn");
    btn?.addEventListener("click", async () => {
      btn.disabled = true;
      btn.textContent = "Processando…";
      try {
        const { error, paymentIntent } = await st.confirmPayment({
          elements,
          redirect: "if_required",
        });
        if (error) throw error;
        const pid = paymentIntent?.id || checkoutData.paymentId;
        await invokeConfirm(checkoutData.subscriptionId, pid, "stripe");
        invalidateCache();
        window.location.hash = "#/";
        window.location.reload();
      } catch (e) {
        alert(e.message || "Pagamento não concluído");
        btn.disabled = false;
        btn.textContent = `Pagar ${formatBrl(checkoutData.amount)}`;
      }
    });
  }

  function renderPixPanel(data) {
    const qr = data.qrCodeBase64
      ? `<img class="pix-qr" src="data:image/png;base64,${esc(data.qrCodeBase64)}" alt="QR Code PIX" />`
      : "";
    return `
      <div class="pay-pix-panel">
        ${qr}
        <p class="pay-amount">${formatBrl(data.amount)}</p>
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

  async function startPixCheckout(planId, container, statusEl) {
    const data = await invokeCheckout(planId, "pix");
    container.innerHTML = renderPixPanel(data);
    bindPixCopy();
    if (statusEl) statusEl.textContent = "Aguardando confirmação do PIX…";
    await pollUntilApproved(data.subscriptionId, data.paymentId, "mercadopago", (r) => {
      const st = document.getElementById("pix-status");
      if (st && r.approved) st.textContent = "Pagamento confirmado! Redirecionando…";
    });
    window.location.hash = "#/";
    window.location.reload();
  }

  async function startCardCheckout(planId, container) {
    const data = await invokeCheckout(planId, "card");
    await mountCardCheckout(container, data);
  }

  function checkoutHtml(planId) {
    const plan = PLANS[planId] || PLANS["lex-mensal"];
    return `
      <section class="page checkout-page">
        <h1>Finalizar assinatura</h1>
        <p class="lead">Plano <strong>${esc(plan.label)}</strong> — ${formatBrl(plan.price)}/${esc(plan.period)}</p>
        <div class="pay-tabs" role="tablist">
          <button type="button" class="pay-tab active" data-pay-tab="pix">PIX</button>
          <button type="button" class="pay-tab" data-pay-tab="card">Cartão · Google Pay · Apple Pay</button>
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
        if (tab === "pix") await startPixCheckout(planId, panel);
        else await startCardCheckout(planId, panel);
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
      window.LexAuthUI?.open("signup");
    });
    if (document.getElementById("pay-panel")) bindCheckout(planId || "lex-mensal");
  }

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
