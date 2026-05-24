import { getUserFromAuthApi } from "../_shared/auth-user-api.ts";
import { formatMercadoPagoError, mercadoPagoFetch } from "../_shared/mp-token.ts";
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

function parseLexReference(ref: string): { userId: string; planId: string; subPrefix: string } | null {
  const m = ref.match(/^lex-(?:pix|card)-([0-9a-f-]{36})-(lex-(?:mensal|anual))-([0-9a-f]{8})-/i);
  if (!m) return null;
  return { userId: m[1]!, planId: m[2]!, subPrefix: m[3]! };
}

async function activateSubscription(
  supabase: ReturnType<typeof serviceClient>,
  subscriptionId: string,
  planId: string,
  paymentId: string,
) {
  const now = new Date();
  const months = planId === "lex-anual" ? 12 : 1;
  const expiresAt = addMonths(now, months);

  const { error: updErr } = await supabase
    .schema("lex")
    .from("user_subscriptions")
    .update({
      status: "active",
      payment_id: paymentId,
      starts_at: now.toISOString(),
      expires_at: expiresAt.toISOString(),
      updated_at: now.toISOString(),
    })
    .eq("id", subscriptionId);

  if (updErr) throw updErr;

  return { status: "active", approved: true, expiresAt: expiresAt.toISOString(), planId };
}

async function fetchApprovedLexPayment(
  userId: string,
  planId: string,
  subPrefix: string,
  createdAt: string,
): Promise<string | null> {
  const begin = new Date(createdAt);
  begin.setHours(begin.getHours() - 1);
  const end = new Date();
  end.setHours(end.getHours() + 1);

  const params = new URLSearchParams({
    sort: "date_created",
    criteria: "desc",
    limit: "50",
    range: "date_created",
    begin_date: begin.toISOString(),
    end_date: end.toISOString(),
  });

  const response = await mercadoPagoFetch(`https://api.mercadopago.com/v1/payments/search?${params}`);
  if (!response.ok) return null;

  const payload = (await response.json()) as {
    results?: Array<{ id?: number | string; status?: string; external_reference?: string }>;
  };

  const prefixes = [
    `lex-pix-${userId}-${planId}-${subPrefix}-`,
    `lex-card-${userId}-${planId}-${subPrefix}-`,
  ];
  for (const payment of payload.results ?? []) {
    const ref = String(payment.external_reference || "");
    if (!prefixes.some((needle) => ref.startsWith(needle))) continue;
    if ((payment.status || "").toLowerCase() !== "approved") continue;
    if (payment.id != null) return String(payment.id);
  }

  return null;
}

async function reconcilePendingSubscriptions(
  supabase: ReturnType<typeof serviceClient>,
  userId: string,
) {
  const { data: pending } = await supabase
    .schema("lex")
    .from("user_subscriptions")
    .select("id, plan_id, payment_id, created_at")
    .eq("user_id", userId)
    .eq("status", "pending")
    .order("created_at", { ascending: false });

  for (const sub of pending ?? []) {
    let paymentId = sub.payment_id ? String(sub.payment_id) : "";
    if (paymentId && /^\d+$/.test(paymentId)) {
      const response = await mercadoPagoFetch(`https://api.mercadopago.com/v1/payments/${paymentId}`);
      if (response.ok) {
        const data = (await response.json()) as { status?: string };
        if ((data.status || "").toLowerCase() === "approved") {
          return activateSubscription(supabase, sub.id, sub.plan_id, paymentId);
        }
      }
    }

    const subPrefix = String(sub.id).slice(0, 8);
    paymentId = (await fetchApprovedLexPayment(userId, sub.plan_id, subPrefix, sub.created_at)) || "";
    if (paymentId) {
      return activateSubscription(supabase, sub.id, sub.plan_id, paymentId);
    }
  }

  return null;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  try {
    const { user: authUser, error: authErr } = await getUserFromAuthApi(req);
    if (authErr || !authUser?.id) {
      return respond(false, { error: "Sessão inválida ou expirada" }, 401);
    }

    const body = await req.json();

    if (body.reconcile === true) {
      const supabase = serviceClient();
      const activated = await reconcilePendingSubscriptions(supabase, authUser.id);
      if (activated) return respond(true, activated);
      return respond(true, { status: "pending", approved: false });
    }

    const { subscriptionId, paymentId } = body;
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

    const storedPid = sub.payment_id ? String(sub.payment_id) : "";
    const incomingPid = String(paymentId);
    const storedIsPreference = storedPid && !/^\d+$/.test(storedPid);
    if (storedPid && storedPid !== incomingPid && !storedIsPreference) {
      return respond(false, { error: "Pagamento não corresponde à assinatura" }, 400);
    }

    const response = await mercadoPagoFetch(`https://api.mercadopago.com/v1/payments/${paymentId}`);
    const data = (await response.json()) as Record<string, unknown>;

    if (!response.ok) {
      console.error("MP confirm check:", formatMercadoPagoError(data));
      return respond(false, { error: formatMercadoPagoError(data) }, 502);
    }

    const approved = (String(data.status || "")).toLowerCase() === "approved";
    if (!approved) {
      return respond(true, { status: "pending", approved: false });
    }

    const externalRef = String(data.external_reference || "");
    const parsed = parseLexReference(externalRef);
    if (parsed && parsed.userId !== authUser.id) {
      return respond(false, { error: "Pagamento não corresponde ao usuário" }, 403);
    }

    const activated = await activateSubscription(supabase, subscriptionId, sub.plan_id, incomingPid);
    return respond(true, activated);
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    console.error("lex-subscription-confirm:", msg);
    return respond(false, { error: msg || "Erro interno" }, 500);
  }
});
