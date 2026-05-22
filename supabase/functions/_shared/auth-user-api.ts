/**
 * Resolve o utilizador autenticado via GET /auth/v1/user.
 */
export type AuthUserId = { id: string; email?: string };

export async function getUserFromAuthApi(req: Request): Promise<{
  user: AuthUserId | null;
  error: string | null;
}> {
  const authHeader = req.headers.get("authorization") ?? "";
  const jwt = authHeader.replace(/^Bearer\s+/i, "").trim();
  if (!jwt) return { user: null, error: "no_jwt" };

  const supabaseUrl = (Deno.env.get("SUPABASE_URL") ?? "").trim().replace(/\/+$/, "");
  const anonKey = (Deno.env.get("SUPABASE_ANON_KEY") ?? "").trim();
  if (!supabaseUrl || !anonKey) {
    return { user: null, error: "env" };
  }

  const res = await fetch(`${supabaseUrl}/auth/v1/user`, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${jwt}`,
      apikey: anonKey,
    },
  });

  if (res.status === 401 || res.status === 403) {
    return { user: null, error: "unauthorized" };
  }
  if (!res.ok) return { user: null, error: "auth_http" };

  try {
    const body = (await res.json()) as Record<string, unknown>;
    const id = body?.id;
    if (typeof id !== "string" || !id) return { user: null, error: "bad_payload" };
    return {
      user: {
        id,
        email: typeof body.email === "string" ? body.email : undefined,
      },
      error: null,
    };
  } catch {
    return { user: null, error: "parse" };
  }
}
