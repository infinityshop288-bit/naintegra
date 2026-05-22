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

function addMonths(date: Date, months: number): Date {
  const d = new Date(date);
  d.setMonth(d.getMonth() + months);
  return d;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  try {
    const { user: authUser, error: authErr } = await getUserFromAuthApi(req);
    if (authErr || !authUser?.id) {
      return respond(false, { error: "Sessão inválida ou expirada" }, 401);
    }

    const { subscriptionId, paymentId, provider } = await req.json();
    if (!subscriptionId || !paymentId) {
      return respond(false, { error: "Dados incompletos" }, 400);
    }

    const supabase = serviceClient();
    const { data: sub, error: subErr } = await supabase
      .schema("lex")
      .from("user_subscriptions")
      .select("id, user_id, plan_id, status, payment_id")
      .eq("id", subscriptionId)
      .maybeSingle();

    if (subErr || !sub) return respond(false, { error: "Assinatura não encontrada" }, 404);
    if (sub.user_id !== authUser.id) return respond(false, { error: "Não autorizado" }, 403);
    if (sub.status === "active") {
      return respond(true, { status: "active", alreadyActive: true });
    }
    if (sub.payment_id && sub.payment_id !== String(paymentId)) {
      return respond(false, { error: "Pagamento não corresponde à assinatura" }, 400);
    }

    let approved = false;

    if (provider === "stripe" || sub.payment_id?.startsWith("pi_")) {
      const stripeKey = Deno.env.get("STRIPE_SECRET_KEY");
      if (!stripeKey) return respond(false, { error: "Stripe não configurado" }, 500);
      const res = await fetch(`https://api.stripe.com/v1/payment_intents/${paymentId}`, {
        headers: { Authorization: `Basic ${btoa(stripeKey + ":")}` },
      });
      const data = await res.json();
      approved = data.status === "succeeded";
    } else {
      const mpToken = Deno.env.get("MP_ACCESS_TOKEN");
      if (!mpToken) return respond(false, { error: "Mercado Pago não configurado" }, 500);
      const res = await fetch(`https://api.mercadopago.com/v1/payments/${paymentId}`, {
        headers: { Authorization: `Bearer ${mpToken}` },
      });
      const data = await res.json();
      approved = (data.status || "").toLowerCase() === "approved";
    }

    if (!approved) {
      return respond(true, { status: "pending", approved: false });
    }

    const now = new Date();
    const months = sub.plan_id === "lex-anual" ? 12 : 1;
    const expiresAt = addMonths(now, months);

    const { error: updErr } = await supabase
      .schema("lex")
      .from("user_subscriptions")
      .update({
        status: "active",
        payment_id: String(paymentId),
        starts_at: now.toISOString(),
        expires_at: expiresAt.toISOString(),
        updated_at: now.toISOString(),
      })
      .eq("id", subscriptionId);

    if (updErr) {
      console.error("activate:", updErr);
      return respond(false, { error: "Erro ao ativar assinatura" }, 500);
    }

    return respond(true, {
      status: "active",
      approved: true,
      expiresAt: expiresAt.toISOString(),
      planId: sub.plan_id,
    });
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    console.error("lex-subscription-confirm:", msg);
    return respond(false, { error: msg || "Erro interno" }, 500);
  }
});
