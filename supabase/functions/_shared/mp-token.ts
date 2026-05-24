/** Token Mercado Pago — aceita nomes usados em VoltGo, Cursos e Lex. */
export function listMercadoPagoTokens(): string[] {
  const names = ["MP_ACCESS_TOKEN", "MERCADOPAGO_ACCESS_TOKEN"] as const;
  const seen = new Set<string>();
  const tokens: string[] = [];
  for (const name of names) {
    const token = Deno.env.get(name)?.trim();
    if (token && !seen.has(token)) {
      seen.add(token);
      tokens.push(token);
    }
  }
  return tokens;
}

export function getMercadoPagoToken(): string | null {
  return listMercadoPagoTokens()[0] ?? null;
}

export function formatMercadoPagoError(data: unknown): string {
  if (data === null || typeof data !== "object") {
    return "Erro ao comunicar com o Mercado Pago";
  }
  const d = data as {
    message?: string;
    error?: string;
    code?: string;
    cause?: Array<{ description?: string; code?: string }>;
  };
  const bits: string[] = [];
  if (d.message) bits.push(d.message);
  if (d.error && d.error !== d.message) bits.push(d.error);
  if (d.code && !bits.some((b) => b.includes(d.code!))) bits.push(d.code);
  if (Array.isArray(d.cause)) {
    for (const c of d.cause) {
      if (c?.description) bits.push(c.description);
      else if (c?.code) bits.push(c.code);
    }
  }
  const s = bits.filter(Boolean).join(" — ");
  return s || "Erro ao processar pagamento no Mercado Pago";
}

export async function mercadoPagoFetch(
  url: string,
  init: RequestInit & { idempotencyKey?: string } = {},
): Promise<Response> {
  const tokens = listMercadoPagoTokens();
  if (!tokens.length) {
    return new Response(JSON.stringify({ message: "Token Mercado Pago não configurado" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }

  let lastResponse: Response | null = null;

  for (let i = 0; i < tokens.length; i++) {
    const token = tokens[i]!;
    const headers = new Headers(init.headers);
    headers.set("Authorization", `Bearer ${token}`);
    if (init.idempotencyKey) {
      headers.set("X-Idempotency-Key", init.idempotencyKey);
    }

    const response = await fetch(url, { ...init, headers });
    lastResponse = response;

    if (response.ok) return response;

    let retryable = false;
    if ((response.status === 403 || response.status === 404) && i < tokens.length - 1) {
      try {
        const data = await response.clone().json();
        retryable = /unauthorized|policy|not found/i.test(formatMercadoPagoError(data));
      } catch {
        retryable = response.status === 404;
      }
    }

    if (!retryable) return response;
  }

  return lastResponse!;
}
