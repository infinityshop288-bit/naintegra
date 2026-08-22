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

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  try {
    const { user: authUser, error: authErr } = await getUserFromAuthApi(req);
    if (authErr || !authUser?.id) {
      return respond(false, { error: "Sessão inválida ou expirada" }, 401);
    }

    const body = await req.json().catch(() => ({}));
    const confirm = body.confirm === true || body.confirm === "true";
    if (!confirm) {
      return respond(false, { error: "Confirme a exclusão da conta" }, 400);
    }

    const supabase = serviceClient();
    const { error: deleteErr } = await supabase.auth.admin.deleteUser(authUser.id);
    if (deleteErr) {
      console.error("delete user:", deleteErr);
      return respond(false, { error: deleteErr.message || "Erro ao excluir conta" }, 500);
    }

    return respond(true, { deleted: true });
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    console.error("lex-delete-account:", msg);
    return respond(false, { error: msg || "Erro interno" }, 500);
  }
});
