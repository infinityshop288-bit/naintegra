import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import {
  aiGenerate,
  callWithFallback,
  corsHeaders,
  listConfiguredProviders,
  parseAiProvider,
  type ChatMessage,
} from "../_shared/ai-providers.ts";

type DashboardType = "providers" | "market_insights" | "pattern_analysis" | "ticker_signals" | "chat";

function buildMarketPrompt(context: Record<string, unknown>): string {
  return `Você é analista quantitativo de mercado de capitais brasileiro (ações da B3, petróleo, FIIs, macro).

O JSON abaixo cobre TODOS os papéis da plataforma (ações e FIIs) com previsões TimesFM/estatísticas, além de
volatilidade, cripto e tráfego web. Considere o conjunto dos papéis — não apenas PRIO3 — e produza análise acionável.

Retorne APENAS JSON válido (sem markdown) neste formato:
{
  "resumo": "2-3 frases sobre o cenário do conjunto de papéis",
  "riscos": ["risco 1", "risco 2"],
  "oportunidades": ["oportunidade 1", "oportunidade 2"],
  "series_destaque": [{"id":"...", "leitura":"..."}],
  "papeis_destaque": [{"ticker":"...", "leitura":"..."}],
  "leitura_setorial": "quais setores estão melhor/pior posicionados",
  "macro_juros": "impacto de juros/Selic no cenário",
  "cripto_fluxo": "leitura BTC/ETH vs emergentes",
  "confianca": 0.0
}

Dados:
${JSON.stringify(context).slice(0, 20000)}`;
}

function buildPatternPrompt(context: Record<string, unknown>, seriesId?: string): string {
  const focus = seriesId ? `Foque na série "${seriesId}".` : "Analise todas as categorias e todos os papéis.";
  return `Analise padrões temporais (preços de ações e FIIs, demanda via volume, volatilidade, tráfego web, cripto).
${focus}

Retorne APENAS JSON:
{
  "padroes_detectados": [{"serie":"...", "padrao":"...", "impacto":"..."}],
  "regime_mercado": "risk-on|risk-off|neutro",
  "sinal_prio3": "compra|venda|neutro|aguardar",
  "papeis_em_destaque": [{"ticker":"...", "padrao":"...", "sinal":"compra|venda|neutro|aguardar"}],
  "justificativa": "texto curto"
}

Contexto:
${JSON.stringify(context).slice(0, 18000)}`;
}

function buildSignalsPrompt(papeis: unknown[], horizonte: unknown, macro: unknown): string {
  return `Avalie CADA papel da B3 abaixo (ações e FIIs) usando os dados quantitativos fornecidos:
tendência, previsão do modelo em ${horizonte ?? 21} pregões, regime de volatilidade e padrões técnicos detectados.

Contexto macro: ${String(macro ?? "").slice(0, 800)}

Retorne APENAS JSON válido (sem markdown), com exatamente um objeto por papel recebido e na mesma ordem:
{"sinais":[{"ticker":"PRIO3","sinal":"compra|neutro|venda","confianca":0,"tese":"até 180 caracteres","risco":"até 120 caracteres"}]}

Papéis:
${JSON.stringify(papeis).slice(0, 12000)}`;
}

function parseJsonContent(raw: string): Record<string, unknown> {
  const trimmed = raw.trim();
  try {
    return JSON.parse(trimmed);
  } catch {
    const m = trimmed.match(/\{[\s\S]*\}/);
    if (m) return JSON.parse(m[0]);
    return { resumo: raw, raw: true };
  }
}

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  try {
    const body = await req.json();
    const type = (body.type || "market_insights") as DashboardType;
    const preferred = body.ai_provider ? parseAiProvider(body.ai_provider) : undefined;

    if (type === "providers") {
      const providers = listConfiguredProviders();
      return new Response(
        JSON.stringify({
          priority: providers.map((p) => p.provider),
          providers,
          configured_count: providers.filter((p) => p.configured).length,
        }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    if (type === "chat") {
      const messages = (body.messages || []) as ChatMessage[];
      const system =
        body.system ||
        "Você é analista de mercado NaIntegra. Responda sobre as ações e FIIs da plataforma, Brent, macro, opções e cripto.";
      const chatMessages: ChatMessage[] = [{ role: "system", content: system }, ...messages];
      const { content, provider } = await callWithFallback(chatMessages, body.max_tokens || 2048, preferred);
      return new Response(JSON.stringify({ content, provider, type }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const context = body.context || body.patterns || {};
    let prompt: string;
    let maxTokens: number;
    if (type === "pattern_analysis") {
      prompt = buildPatternPrompt(context, body.series_id);
      maxTokens = body.max_tokens || 2048;
    } else if (type === "ticker_signals") {
      const papeis = (body.papeis || context.papeis || []) as unknown[];
      prompt = buildSignalsPrompt(papeis, body.horizon_dias ?? context.horizon_dias, body.macro ?? context.macro);
      maxTokens = body.max_tokens || 3072;
    } else {
      prompt = buildMarketPrompt(context);
      maxTokens = body.max_tokens || 4096;
    }

    const { content, provider } = await aiGenerate(prompt, maxTokens, preferred);
    let parsed: Record<string, unknown>;
    try {
      parsed = parseJsonContent(content);
    } catch {
      parsed = { resumo: content, raw: true };
    }

    return new Response(
      JSON.stringify({
        type,
        provider,
        model_used: provider,
        ...parsed,
        gerado: new Date().toISOString(),
      }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } },
    );
  } catch (e) {
    console.error("[ai-dashboard]", e);
    return new Response(JSON.stringify({ error: e instanceof Error ? e.message : "Erro desconhecido" }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
