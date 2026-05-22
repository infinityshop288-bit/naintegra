import { getUserFromAuthApi } from "./_shared/auth-user-api.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

function respond(ok: boolean, payload: Record<string, unknown>, status = 200) {
  return new Response(JSON.stringify({ ok, ...payload }), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function serviceClient() {
  const url = Deno.env.get("SUPABASE_URL")?.trim();
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")?.trim();
  if (!url || !key) throw new Error("Configuração Supabase incompleta");
  return createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } });
}

function getMercadoPagoToken(): string | null {
  return (
    Deno.env.get("MERCADOPAGO_ACCESS_TOKEN")?.trim() ||
    Deno.env.get("MP_ACCESS_TOKEN")?.trim() ||
    null
  );
}

function resolvePublicBase(req: Request): string {
  const fromEnv = Deno.env.get("APP_PUBLIC_URL")?.trim().replace(/\/$/, "");
  if (fromEnv && /^https:\/\//i.test(fromEnv)) return fromEnv;
  const origin = req.headers.get("origin")?.trim() || "";
  if (/^https:\/\//i.test(origin)) return origin.replace(/\/$/, "");
  return "https://www.naintegracursos.com.br";
}

const PLAN_IDS = new Set(["lex-mensal", "lex-anual"]);

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  try {
    const { user: authUser, error: authErr } = await getUserFromAuthApi(req);
    if (authErr || !authUser?.id) {
      return respond(false, { error: "Sessão inválida ou expirada" }, 401);
    }

    const body = await req.json();
    const planId = String(body.planId || "").trim();
    const provider = String(body.provider || "").trim();
    const payerCpfRaw = typeof body.payerCpf === "string" ? body.payerCpf : "";

    if (!PLAN_IDS.has(planId)) {
      return respond(false, { error: "Plano inválido" }, 400);
    }
    if (provider !== "pix" && provider !== "card") {
      return respond(false, { error: "Forma de pagamento inválida" }, 400);
    }

    const mpToken = getMercadoPagoToken();
    if (!mpToken) return respond(false, { error: "Mercado Pago não configurado" }, 500);

    const supabase = serviceClient();
    const { data: plan, error: planErr } = await supabase
      .schema("lex")
      .from("subscription_plans")
      .select("id, name, price_cents")
      .eq("id", planId)
      .eq("active", true)
      .maybeSingle();

    if (planErr || !plan) {
      return respond(false, { error: "Plano não encontrado" }, 404);
    }

    const amountBrl = plan.price_cents / 100;
    const shortId = crypto.randomUUID().split("-")[0];

    const { data: subRow, error: subErr } = await supabase
      .schema("lex")
      .from("user_subscriptions")
      .insert({
        user_id: authUser.id,
        plan_id: planId,
        status: "pending",
        provider: "mercadopago",
        amount_cents: plan.price_cents,
      })
      .select("id")
      .single();

    if (subErr || !subRow?.id) {
      console.error("subscription insert:", subErr);
      return respond(false, { error: "Erro ao iniciar assinatura" }, 500);
    }

    const subscriptionId = subRow.id as string;
    const extRef = `lex-${provider}-${authUser.id}-${planId}-${subscriptionId.slice(0, 8)}-${shortId}`;
    const supabaseUrl = (Deno.env.get("SUPABASE_URL") || "").trim().replace(/\/+$/, "");
    const notificationUrl = supabaseUrl ? `${supabaseUrl}/functions/v1/mercadopago-webhook` : "";

    if (provider === "pix") {
      const cpfClean = payerCpfRaw.replace(/\D/g, "");
      const expirationDate = new Date(Date.now() + 30 * 60 * 1000).toISOString();

      const payer: Record<string, unknown> = {
        email: authUser.email || `${authUser.id}@naintegra.app`,
      };
      if (cpfClean.length === 11) {
        payer.identification = { type: "CPF", number: cpfClean };
      }

      const paymentBody = {
        transaction_amount: amountBrl,
        description: `NaIntegra Lex — ${plan.name}`.slice(0, 200),
        payment_method_id: "pix",
        payer,
        external_reference: extRef,
        date_of_expiration: expirationDate,
        ...(notificationUrl ? { notification_url: notificationUrl } : {}),
      };

      const res = await fetch("https://api.mercadopago.com/v1/payments", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${mpToken}`,
          "Content-Type": "application/json",
          "X-Idempotency-Key": `lex-pix-${shortId}`,
        },
        body: JSON.stringify(paymentBody),
      });
      const data = await res.json();
      if (!res.ok) {
        console.error("MP PIX:", res.status, JSON.stringify(data));
        return respond(false, { error: data?.message || "Erro ao criar PIX" }, 400);
      }

      const paymentId = String(data.id);
      await supabase.schema("lex").from("user_subscriptions").update({
        payment_id: paymentId,
        updated_at: new Date().toISOString(),
      }).eq("id", subscriptionId);

      return respond(true, {
        subscriptionId,
        paymentId,
        provider: "mercadopago",
        amount: amountBrl,
        planId,
        planName: plan.name,
        qrCode: data.point_of_interaction?.transaction_data?.qr_code || "",
        qrCodeBase64: data.point_of_interaction?.transaction_data?.qr_code_base64 || "",
        ticketUrl: data.point_of_interaction?.transaction_data?.ticket_url || "",
        expiresAt: expirationDate,
      });
    }

    // Cartão — Checkout Pro (Mercado Pago), mesmo padrão VoltGo
    const base = resolvePublicBase(req);
    const preferenceData = {
      items: [
        {
          title: `NaIntegra Lex — ${plan.name}`,
          quantity: 1,
          currency_id: "BRL",
          unit_price: amountBrl,
        },
      ],
      payer: {
        email: authUser.email || `${authUser.id}@naintegra.app`,
      },
      payment_methods: {
        excluded_payment_types: [],
        installments: 12,
      },
      back_urls: {
        success: `${base}/lex/?payment=success#/assinatura`,
        failure: `${base}/lex/?payment=failure#/assinatura`,
        pending: `${base}/lex/?payment=pending#/assinatura`,
      },
      auto_return: "approved",
      statement_descriptor: "NAINTEGRA LEX",
      external_reference: extRef,
    };

    const prefRes = await fetch("https://api.mercadopago.com/checkout/preferences", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${mpToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(preferenceData),
    });
    const prefData = await prefRes.json();
    if (!prefRes.ok) {
      console.error("MP Checkout Pro:", JSON.stringify(prefData));
      return respond(false, { error: prefData?.message || "Erro ao criar checkout" }, 400);
    }

    await supabase.schema("lex").from("user_subscriptions").update({
      payment_id: String(prefData.id),
      updated_at: new Date().toISOString(),
    }).eq("id", subscriptionId);

    return respond(true, {
      subscriptionId,
      paymentId: prefData.id,
      preferenceId: prefData.id,
      initPoint: prefData.init_point,
      sandboxInitPoint: prefData.sandbox_init_point,
      provider: "mercadopago",
      amount: amountBrl,
      planId,
      planName: plan.name,
    });
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    console.error("lex-subscription-checkout:", msg);
    return respond(false, { error: msg || "Erro interno" }, 500);
  }
});
