/**
 * Resolve o utilizador autenticado a partir do JWT da requisição.
 */
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.0";

export type AuthUserId = { id: string; email?: string };

export async function getUserFromAuthApi(req: Request): Promise<{
  user: AuthUserId | null;
  error: string | null;
}> {
  const authHeader = req.headers.get("authorization") ?? "";
  const jwt = authHeader.replace(/^Bearer\s+/i, "").trim();
  if (!jwt) return { user: null, error: "no_jwt" };

  const supabaseUrl = (Deno.env.get("SUPABASE_URL") ?? "").trim().replace(/\/+$/, "");
  if (!supabaseUrl) return { user: null, error: "env" };

  const anonKey = (Deno.env.get("SUPABASE_ANON_KEY") ?? "").trim();
  if (anonKey) {
    const res = await fetch(`${supabaseUrl}/auth/v1/user`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${jwt}`,
        apikey: anonKey,
      },
    });

    if (res.ok) {
      try {
        const body = (await res.json()) as Record<string, unknown>;
        const id = body?.id;
        if (typeof id === "string" && id) {
          return {
            user: {
              id,
              email: typeof body.email === "string" ? body.email : undefined,
            },
            error: null,
          };
        }
      } catch {
        /* tenta fallback abaixo */
      }
    }
  }

  const serviceKey = (Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "").trim();
  if (serviceKey) {
    try {
      const admin = createClient(supabaseUrl, serviceKey, {
        auth: { persistSession: false, autoRefreshToken: false },
      });
      const { data, error } = await admin.auth.getUser(jwt);
      if (!error && data?.user?.id) {
        return {
          user: {
            id: data.user.id,
            email: data.user.email ?? undefined,
          },
          error: null,
        };
      }
    } catch {
      /* ignora e retorna unauthorized */
    }
  }

  return { user: null, error: "unauthorized" };
}
