/** Provedores de IA compartilhados — mesma cadeia de fallback dos projetos NaIntegra. */
export const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

export type AiProvider = "groq" | "github" | "gemini" | "claude" | "openrouter";

export const AI_PRIORITY: readonly AiProvider[] = ["groq", "gemini", "github", "openrouter", "claude"];

export const AI_MODELS: Record<AiProvider, string> = {
  groq: Deno.env.get("GROQ_MODEL") || "llama-3.3-70b-versatile",
  github: Deno.env.get("GITHUB_MODEL") || "openai/gpt-4o-mini",
  gemini: Deno.env.get("GEMINI_MODEL") || "gemini-2.5-flash",
  claude: Deno.env.get("CLAUDE_MODEL") || "claude-sonnet-4-20250514",
  openrouter: Deno.env.get("OPENROUTER_MODEL") || "meta-llama/llama-3.3-70b-instruct",
};

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export function parseAiProvider(value: unknown): AiProvider {
  if (value === "groq" || value === "github" || value === "gemini" || value === "claude" || value === "openrouter") {
    return value;
  }
  return "groq";
}

export function listConfiguredProviders(): { provider: AiProvider; model: string; configured: boolean }[] {
  const keys: Record<AiProvider, string> = {
    groq: "GROQ_API_KEY",
    github: "GITHUB_TOKEN",
    gemini: "GEMINI_API_KEY",
    claude: "ANTHROPIC_API_KEY",
    openrouter: "OPENROUTER_API_KEY",
  };
  return AI_PRIORITY.map((provider) => ({
    provider,
    model: AI_MODELS[provider],
    configured: Boolean(Deno.env.get(keys[provider])),
  }));
}

/** Modelos preferidos no Groq, em ordem — a lista da Groq muda com frequência. */
const GROQ_PREFERRED = [
  "llama-3.3-70b-versatile",
  "openai/gpt-oss-120b",
  "moonshotai/kimi-k2-instruct",
  "qwen/qwen3-32b",
  "llama-3.1-8b-instant",
];

let groqModel: string | null = null;

/** Descobre um modelo de chat disponível para a chave (modelos são descontinuados). */
async function discoverGroqModel(key: string): Promise<string> {
  const resp = await fetch("https://api.groq.com/openai/v1/models", {
    headers: { Authorization: `Bearer ${key}` },
  });
  if (!resp.ok) throw new Error(`Groq models ${resp.status}: ${(await resp.text()).slice(0, 120)}`);
  const data = await resp.json();
  const ids: string[] = (data.data || []).map((m: { id: string }) => m.id);
  const pick = GROQ_PREFERRED.find((m) => ids.includes(m)) ||
    ids.find((id) => !/whisper|guard|tts|embed/i.test(id));
  if (!pick) throw new Error("Groq sem modelo de chat disponível");
  return pick;
}

async function groqRequest(model: string, messages: ChatMessage[], maxTokens: number): Promise<Response> {
  const key = Deno.env.get("GROQ_API_KEY")!;
  return fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
    body: JSON.stringify({ model, max_tokens: maxTokens, messages, temperature: 0.7 }),
  });
}

async function callGroq(messages: ChatMessage[], maxTokens: number): Promise<string> {
  const key = Deno.env.get("GROQ_API_KEY");
  if (!key) throw new Error("GROQ_API_KEY not set");
  let model = groqModel || AI_MODELS.groq;
  let resp = await groqRequest(model, messages, maxTokens);
  if (!resp.ok) {
    const erro = (await resp.text()).slice(0, 200);
    const modeloInvalido = /model_not_found|does not exist|decommissioned|deprecated/i.test(erro);
    if (!modeloInvalido) throw new Error(`Groq ${resp.status}: ${erro}`);
    model = await discoverGroqModel(key);
    resp = await groqRequest(model, messages, maxTokens);
    if (!resp.ok) throw new Error(`Groq ${resp.status}: ${(await resp.text()).slice(0, 200)}`);
  }
  groqModel = model;
  const data = await resp.json();
  return data.choices?.[0]?.message?.content || "";
}

async function callGitHub(messages: ChatMessage[], maxTokens: number): Promise<string> {
  const key = Deno.env.get("GITHUB_TOKEN");
  if (!key) throw new Error("GITHUB_TOKEN not set");
  const resp = await fetch("https://models.github.ai/inference/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
    body: JSON.stringify({
      model: AI_MODELS.github,
      max_tokens: maxTokens,
      messages,
      temperature: 0.7,
    }),
  });
  if (!resp.ok) throw new Error(`GitHub ${resp.status}: ${(await resp.text()).slice(0, 200)}`);
  const data = await resp.json();
  return data.choices?.[0]?.message?.content || "";
}

async function callGemini(messages: ChatMessage[], maxTokens: number): Promise<string> {
  const key = Deno.env.get("GEMINI_API_KEY");
  if (!key) throw new Error("GEMINI_API_KEY not set");
  const geminiContents = [];
  for (const msg of messages) {
    if (msg.role === "system") {
      geminiContents.push({ role: "user", parts: [{ text: msg.content }] });
      geminiContents.push({ role: "model", parts: [{ text: "Entendido." }] });
    } else {
      geminiContents.push({
        role: msg.role === "assistant" ? "model" : "user",
        parts: [{ text: msg.content }],
      });
    }
  }
  const resp = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${AI_MODELS.gemini}:generateContent?key=${key}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: geminiContents,
        generationConfig: { temperature: 0.7, maxOutputTokens: maxTokens },
      }),
    },
  );
  if (!resp.ok) throw new Error(`Gemini ${resp.status}: ${(await resp.text()).slice(0, 200)}`);
  const data = await resp.json();
  return data.candidates?.[0]?.content?.parts?.[0]?.text || "";
}

async function callClaude(messages: ChatMessage[], maxTokens: number): Promise<string> {
  const key = Deno.env.get("ANTHROPIC_API_KEY");
  if (!key) throw new Error("ANTHROPIC_API_KEY not set");
  const systemMsg = messages.find((m) => m.role === "system")?.content || "";
  const chatMsgs = messages
    .filter((m) => m.role !== "system")
    .map((m) => ({ role: m.role as "user" | "assistant", content: m.content }));
  const resp = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": key,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: AI_MODELS.claude,
      max_tokens: maxTokens,
      system: systemMsg,
      messages: chatMsgs,
      temperature: 0.7,
    }),
  });
  if (!resp.ok) throw new Error(`Claude ${resp.status}: ${(await resp.text()).slice(0, 200)}`);
  const data = await resp.json();
  return data.content?.[0]?.text || "";
}

async function callOpenRouter(messages: ChatMessage[], maxTokens: number): Promise<string> {
  const key = Deno.env.get("OPENROUTER_API_KEY");
  if (!key) throw new Error("OPENROUTER_API_KEY not set");
  const resp = await fetch("https://openrouter.ai/api/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
    body: JSON.stringify({
      model: AI_MODELS.openrouter,
      max_tokens: maxTokens,
      messages,
      temperature: 0.7,
    }),
  });
  if (!resp.ok) throw new Error(`OpenRouter ${resp.status}: ${(await resp.text()).slice(0, 200)}`);
  const data = await resp.json();
  return data.choices?.[0]?.message?.content || "";
}

const providerFns: Record<AiProvider, (msgs: ChatMessage[], maxTokens: number) => Promise<string>> = {
  groq: callGroq,
  github: callGitHub,
  gemini: callGemini,
  claude: callClaude,
  openrouter: callOpenRouter,
};

export async function callWithFallback(
  messages: ChatMessage[],
  maxTokens: number,
  preferred?: AiProvider,
): Promise<{ content: string; provider: AiProvider }> {
  const order = preferred
    ? [preferred, ...AI_PRIORITY.filter((p) => p !== preferred)]
    : [...AI_PRIORITY];
  const errors: string[] = [];
  for (const provider of order) {
    try {
      const content = await providerFns[provider](messages, maxTokens);
      if (content) return { content, provider };
    } catch (e) {
      errors.push(`${provider}: ${e instanceof Error ? e.message : String(e)}`);
    }
  }
  throw new Error(`All AI providers failed: ${errors.join(" | ")}`);
}

/** Geração one-shot (prompt único) — usado por scrapers e dashboard. */
export async function aiGenerate(
  prompt: string,
  maxTokens = 4096,
  preferred?: AiProvider,
): Promise<{ content: string; provider: AiProvider }> {
  return callWithFallback(
    [
      { role: "system", content: "Responda em português do Brasil. Seja preciso e objetivo." },
      { role: "user", content: prompt },
    ],
    maxTokens,
    preferred,
  );
}
