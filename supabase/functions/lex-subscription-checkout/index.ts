import { getUserFromAuthApi } from "../_shared/auth-user-api.ts";
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
    if (provider !== "init") {
      return respond(false, { error: "Use create-pix-payment ou create-payment após init" }, 400);
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
    const subPrefix = subscriptionId.slice(0, 8);

    return respond(true, {
      subscriptionId,
      amount: amountBrl,
      planId,
      planName: plan.name,
      externalReferencePix: `lex-pix-${authUser.id}-${planId}-${subPrefix}-${shortId}`,
      externalReferenceCard: `lex-card-${authUser.id}-${planId}-${subPrefix}-${shortId}`,
    });
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    console.error("lex-subscription-checkout:", msg);
    return respond(false, { error: msg || "Erro interno" }, 500);
  }
});
