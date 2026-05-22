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

    if (!PLAN_IDS.has(planId)) {
      return respond(false, { error: "Plano inválido" }, 400);
    }
    if (provider !== "pix" && provider !== "card") {
      return respond(false, { error: "Forma de pagamento inválida" }, 400);
    }

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
        provider: provider === "pix" ? "mercadopago" : "stripe",
        amount_cents: plan.price_cents,
      })
      .select("id")
      .single();

    if (subErr || !subRow?.id) {
      console.error("subscription insert:", subErr);
      return respond(false, { error: "Erro ao iniciar assinatura" }, 500);
    }

    const subscriptionId = subRow.id as string;
    const stripePk = Deno.env.get("STRIPE_PUBLISHABLE_KEY") || "";

    if (provider === "pix") {
      const mpToken = Deno.env.get("MP_ACCESS_TOKEN");
      if (!mpToken) return respond(false, { error: "Mercado Pago não configurado" }, 500);

      const extRef = `lex-pix-${authUser.id}-${planId}-${subscriptionId.slice(0, 8)}-${shortId}`;
      const expirationDate = new Date(Date.now() + 30 * 60 * 1000).toISOString();
      const supabaseUrl = (Deno.env.get("SUPABASE_URL") || "").trim().replace(/\/+$/, "");
      const notificationUrl = supabaseUrl ? `${supabaseUrl}/functions/v1/mp-webhook` : "";

      const paymentBody = {
        transaction_amount: amountBrl,
        description: `NaIntegra Lex — ${plan.name}`.slice(0, 200),
        payment_method_id: "pix",
        payer: { email: authUser.email || `${authUser.id}@naintegra.app` },
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
        stripePublishableKey: stripePk,
      });
    }

    const stripeKey = Deno.env.get("STRIPE_SECRET_KEY");
    if (!stripeKey) return respond(false, { error: "Stripe não configurado" }, 500);

    const amountCents = plan.price_cents;
    const params = new URLSearchParams({
      amount: String(amountCents),
      currency: "brl",
      description: `NaIntegra Lex — ${plan.name}`.slice(0, 200),
      "automatic_payment_methods[enabled]": "true",
      "metadata[user_id]": authUser.id,
      "metadata[source]": "lex_subscription",
      "metadata[plan_id]": planId,
      "metadata[subscription_id]": subscriptionId,
    });

    const piRes = await fetch("https://api.stripe.com/v1/payment_intents", {
      method: "POST",
      headers: {
        Authorization: `Basic ${btoa(stripeKey + ":")}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: params,
    });
    const piData = await piRes.json();
    if (!piRes.ok) {
      console.error("Stripe PI:", JSON.stringify(piData));
      return respond(false, { error: piData?.error?.message || "Erro Stripe" }, 400);
    }

    await supabase.schema("lex").from("user_subscriptions").update({
      payment_id: piData.id,
      updated_at: new Date().toISOString(),
    }).eq("id", subscriptionId);

    return respond(true, {
      subscriptionId,
      paymentId: piData.id,
      clientSecret: piData.client_secret,
      provider: "stripe",
      amount: amountBrl,
      planId,
      planName: plan.name,
      stripePublishableKey: stripePk,
    });
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    console.error("lex-subscription-checkout:", msg);
    return respond(false, { error: msg || "Erro interno" }, 500);
  }
});
