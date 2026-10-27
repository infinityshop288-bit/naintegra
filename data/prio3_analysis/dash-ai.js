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

/** Sinal da IA (compra/neutro/venda) para cada papel da plataforma, em lotes. */
async function dashAITickerSignals(papeis, horizonDias, macro, lote = 8) {
  const sinais = [];
  let provider = null;
  for (let i = 0; i < papeis.length; i += lote) {
    const r = await dashAIFetch("ai-dashboard", {
      type: "ticker_signals",
      papeis: papeis.slice(i, i + lote),
      horizon_dias: horizonDias,
      macro,
    });
    provider = provider || r.provider;
    (r.sinais || []).forEach((s) => s.ticker && sinais.push({ ...s, provider: r.provider }));
  }
  return { sinais, provider };
}

/** Chat livre com analista de mercado (legado: Edge Function Supabase). */
async function dashAIChat(messages, system) {
  return dashAIFetch("ai-dashboard", { type: "chat", messages, system });
}

const CODEX_MODELOS = ["gpt-5.6-sol", "gpt-6-astra", "gpt-6-sol", "gpt-6-luna"];

function dashCodexUrl() {
  const porta = location.port;
  if (porta === "8899" || porta === "8123") return "/api/chat";
  return new URL("chat.php", location.href).href;
}

/**
 * Stream da Responses API via proxy (chat.php no Hostinger, /api/chat no live_server).
 * Devolve { texto, itens }. Os itens reasoning/message devem ser reenviados no próximo turno.
 */
async function dashCodexStream({ input, instructions, model, signal, onDelta, onItem }) {
  const escolhido = CODEX_MODELOS.includes(model) ? model : "gpt-5.6-sol";
  const r = await fetch(dashCodexUrl(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: escolhido,
      stream: true,
      instructions: instructions || "",
      input,
    }),
    signal,
  });
  if (!r.ok) {
    const t = await r.text();
    let msg = t.slice(0, 400);
    try {
      const j = JSON.parse(t);
      msg = (j.error && j.error.message) || j.message || msg;
    } catch (_) { /* texto puro */ }
    throw new Error(msg || `HTTP ${r.status}`);
  }
  if (!r.body) throw new Error("resposta sem corpo");
  let texto = "";
  let buffer = "";
  const itens = [];
  const dec = new TextDecoder();
  const reader = r.body.getReader();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += dec.decode(value, { stream: true });
    const linhas = buffer.split("\n");
    buffer = linhas.pop();
    for (const linha of linhas) {
      if (!linha.startsWith("data: ")) continue;
      const raw = linha.slice(6).trim();
      if (!raw || raw === "[DONE]") continue;
      let ev;
      try {
        ev = JSON.parse(raw);
      } catch (_) {
        continue;
      }
      if (ev.type === "error" || ev.error) {
        throw new Error((ev.error && ev.error.message) || ev.message || "erro na stream");
      }
      if (ev.type === "response.output_text.delta") {
        texto += ev.delta || "";
        if (onDelta) onDelta(ev.delta || "", texto);
      }
      if (ev.type === "response.output_item.done" && ev.item) {
        itens.push(ev.item);
        if (onItem) onItem(ev.item);
      }
    }
  }
  return { texto, itens };
}

function dashCodexTexto(data) {
  if (data && data.output_text) return String(data.output_text);
  const partes = [];
  for (const item of (data && data.output) || []) {
    if (item.type !== "message") continue;
    for (const c of item.content || []) {
      if ((c.type === "output_text" || c.type === "text") && c.text) partes.push(c.text);
    }
  }
  return partes.join("");
}

function dashJsonDeTexto(txt) {
  let t = String(txt || "").trim();
  if (t.startsWith("```")) {
    t = t.replace(/^```(?:json)?/i, "").replace(/```$/, "").trim();
  }
  const i = t.indexOf("{");
  const j = t.lastIndexOf("}");
  if (i < 0 || j <= i) throw new Error("sem JSON na resposta da IA");
  return JSON.parse(t.slice(i, j + 1));
}

/** Chamada não-streaming da Codex via proxy — para gerar análise/sinais na página. */
async function dashCodexJson({ input, instructions, model }) {
  const r = await fetch(dashCodexUrl(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: CODEX_MODELOS.includes(model) ? model : "gpt-5.6-sol",
      stream: false,
      instructions: instructions || "Responda APENAS JSON válido, sem markdown.",
      input,
    }),
  });
  const t = await r.text();
  let data;
  try {
    data = JSON.parse(t);
  } catch (_) {
    throw new Error(t.slice(0, 300) || `HTTP ${r.status}`);
  }
  if (!r.ok) throw new Error((data.error && data.error.message) || `HTTP ${r.status}`);
  return dashJsonDeTexto(dashCodexTexto(data));
}
