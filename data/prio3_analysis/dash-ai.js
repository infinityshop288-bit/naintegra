/** Cliente Supabase Edge Functions — mesmas IAs do projeto NaIntegra Cursos. */
const DASH_AI = {
  url: "https://voybsggeedpwcfdadnzt.supabase.co",
  anonKey:
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZveWJzZ2dlZWRwd2NmZGFkbnp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNzU2MTQsImV4cCI6MjA4ODc1MTYxNH0.dy5AgSd1VWdP4WLGXy5V89pA4jgHijngHJjScApOo70",
};

async function dashAIFetch(fn, body) {
  const r = await fetch(`${DASH_AI.url}/functions/v1/${fn}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${DASH_AI.anonKey}`,
      apikey: DASH_AI.anonKey,
    },
    body: JSON.stringify(body || {}),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
  return data;
}

/** Lista provedores configurados (Groq, GitHub, Gemini, Claude, OpenRouter). */
async function dashAIProviders() {
  return dashAIFetch("ai-dashboard", { type: "providers" });
}

/** Análise de mercado a partir do contexto ai_patterns. */
async function dashAIMarketInsights(context) {
  return dashAIFetch("ai-dashboard", { type: "market_insights", context });
}

/** Detecção de padrões (vendas, vol, cripto, tráfego). */
async function dashAIPatternAnalysis(context, seriesId) {
  return dashAIFetch("ai-dashboard", { type: "pattern_analysis", context, series_id: seriesId });
}

/** Chat livre com analista de mercado. */
async function dashAIChat(messages, system) {
  return dashAIFetch("ai-dashboard", { type: "chat", messages, system });
}
