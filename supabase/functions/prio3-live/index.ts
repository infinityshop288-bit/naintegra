/** Cotações ao vivo para o dashboard /xxx/ (Hostinger sem Python). */
const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36";

const TICKERS = [
  "PRIO3", "BRAV3", "PETR4", "MGLU3", "LREN3", "EQTL3", "CMIG4", "ITUB4", "BBDC4", "BBAS3", "BBSE3",
  "PSSA3", "VALE3", "SUZB3", "ABEV3", "MBRF3", "CYRE3", "MRVE3", "DIRR3", "CURY3", "WEGE3",
  "CSNA3", "KNCR11", "MANA11", "RURA11", "RBRP11", "HGLG11", "XPML11", "CLIN11", "MXRF11",
];

type CacheEntry = { ts: number; data: unknown };
const cache = new Map<string, CacheEntry>();

async function fetchText(url: string, referer?: string): Promise<string> {
  const r = await fetch(url, {
    headers: {
      "User-Agent": UA,
      Accept: "*/*",
      ...(referer ? { Referer: referer } : {}),
    },
  });
  if (!r.ok) throw new Error(`HTTP ${r.status} ${url}`);
  return await r.text();
}

async function teCommodity(slug: string) {
  const html = await fetchText(`https://tradingeconomics.com/commodity/${slug}`);
  const m = html.match(/TEChartsMeta\s*=\s*\[\{"value":([0-9.]+)/);
  const price = m ? parseFloat(m[1]) : null;
  const mp = html.match(/,\s*(up|down)\s*([0-9.]+)%\s*from the previous day/i);
  let pct: number | null = null;
  if (mp) {
    pct = parseFloat(mp[2]) * (mp[1].toLowerCase() === "up" ? 1 : -1);
  }
  let prev: number | null = null;
  let change: number | null = null;
  if (price != null && pct != null) {
    prev = price / (1 + pct / 100);
    change = price - prev;
  }
  return {
    price,
    pct,
    change,
    prev,
    unit: "USD/bbl",
    source: "TradingEconomics",
  };
}

let yahooPrimed = false;
async function primeYahoo() {
  if (yahooPrimed) return;
  try {
    await fetchText("https://finance.yahoo.com/quote/PRIO3.SA");
    yahooPrimed = true;
  } catch {
    /* ignore */
  }
}

async function yahooQuote(symbol: string) {
  await primeYahoo();
  const ref = `https://finance.yahoo.com/quote/${symbol}`;
  let meta: Record<string, unknown> | null = null;
  let lastErr: unknown = null;
  for (const host of ["query1", "query2"]) {
    const url =
      `https://${host}.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=1d`;
    try {
      const raw = await fetchText(url, ref);
      const j = JSON.parse(raw);
      meta = j?.chart?.result?.[0]?.meta;
      if (meta) break;
    } catch (e) {
      lastErr = e;
      await new Promise((r) => setTimeout(r, 400));
    }
  }
  if (!meta) throw lastErr ?? new Error("Yahoo indisponível");

  const price = meta.regularMarketPrice as number | undefined;
  let prev = (meta.chartPreviousClose ?? meta.previousClose) as number | undefined;
  let pct: number | null = null;
  let change: number | null = null;
  if (price != null && prev) {
    change = price - prev;
    pct = (change / prev) * 100;
  }
  return {
    price,
    pct,
    change,
    prev,
    unit: (meta.currency as string) || "",
    source: "Yahoo Finance",
    time: meta.regularMarketTime,
  };
}

async function yahooChartCloses(symbol: string): Promise<number[]> {
  await primeYahoo();
  const ref = `https://finance.yahoo.com/quote/${symbol}`;
  const url =
    `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?interval=1d&range=5d`;
  const raw = await fetchText(url, ref);
  const j = JSON.parse(raw);
  const result = j?.chart?.result?.[0];
  const closes = result?.indicators?.quote?.[0]?.close as (number | null)[] | undefined;
  if (!closes) return [];
  return closes.filter((c): c is number => c != null);
}

async function crudeInventory() {
  try {
    const html = await fetchText(
      "https://tradingeconomics.com/united-states/crude-oil-stocks-change",
    );
    const m = html.match(/id="metaDesc"[^>]*content="([^"]+)"/);
    const txt = m?.[1] ?? "";
    const mv = txt.match(
      /(increased|decreased|rose|fell|dropped|declined|climbed|built|drew)\s+by\s+(-?[0-9.]+)\s*million/i,
    );
    const wk = txt.match(/week end(?:ing|ed)\s+([^.]+?)\./i);
    let change: number | null = null;
    if (mv) {
      const val = parseFloat(mv[2]);
      const neg = ["decreased", "fell", "dropped", "declined", "drew"].includes(
        mv[1].toLowerCase(),
      );
      change = neg ? -val : val;
    }
    return {
      change_mmbbl: change,
      semana: wk?.[1]?.trim() ?? null,
      fonte: "EIA (via TradingEconomics)",
    };
  } catch (e) {
    return { change_mmbbl: null, error: String(e) };
  }
}

const lastGood: Record<string, Record<string, unknown>> = {};

async function collectLive() {
  const out: {
    ts: number;
    quotes: Record<string, unknown>;
    inventory: unknown;
    source: string;
  } = {
    ts: Math.floor(Date.now() / 1000),
    quotes: {},
    inventory: null,
    source: "prio3-live",
  };
  const tasks: Record<string, () => Promise<Record<string, unknown>>> = {
    brent: () => teCommodity("brent-crude-oil"),
    wti: () => teCommodity("crude-oil"),
    prio3: () => yahooQuote("PRIO3.SA"),
    brav3: () => yahooQuote("BRAV3.SA"),
    petr4: () => yahooQuote("PETR4.SA"),
    usd: () => yahooQuote("USDBRL=X"),
  };
  await Promise.all(
    Object.entries(tasks).map(async ([key, fn]) => {
      try {
        const q = await fn();
        if (q.price != null) lastGood[key] = q;
        out.quotes[key] = q;
      } catch (e) {
        if (lastGood[key]) {
          out.quotes[key] = { ...lastGood[key], stale: true };
        } else {
          out.quotes[key] = { error: String(e) };
        }
      }
    }),
  );
  out.inventory = await crudeInventory();
  return out;
}

async function multiquotes() {
  const out: { ts: number; quotes: Record<string, unknown> } = {
    ts: Math.floor(Date.now() / 1000),
    quotes: {},
  };
  const symbols = TICKERS.map((t) => `${t}.SA`);
  symbols.push("^BVSP");
  await Promise.all(
    symbols.map(async (sym) => {
      const label = sym === "^BVSP" ? "IBOV" : sym.replace(".SA", "");
      try {
        const closes = await yahooChartCloses(sym);
        if (closes.length < 2) {
          out.quotes[label] = { price: null };
          return;
        }
        const px = closes[closes.length - 1];
        const prev = closes[closes.length - 2];
        out.quotes[label] = {
          price: Math.round(px * 100) / 100,
          pct: Math.round((px / prev - 1) * 10000) / 100,
          prev: Math.round(prev * 100) / 100,
        };
      } catch {
        out.quotes[label] = { price: null };
      }
    }),
  );
  return out;
}

/** Dispara o workflow de atualização quando o snapshot publicado está velho. */
let lastDispatch = 0;

async function dispatchRefresh(ageMin: number) {
  const token = Deno.env.get("GH_DISPATCH_TOKEN")?.trim();
  if (!token) {
    return { dispatched: false, reason: "GH_DISPATCH_TOKEN não configurado" };
  }
  if (Date.now() - lastDispatch < 10 * 60_000) {
    return { dispatched: false, reason: "aguardando refresh anterior" };
  }
  const repo = Deno.env.get("GH_DISPATCH_REPO")?.trim() ||
    "infinityshop288-bit/naintegra";
  const workflow = Deno.env.get("GH_DISPATCH_WORKFLOW")?.trim() ||
    "sync-prio3-to-cursos.yml";
  const r = await fetch(
    `https://api.github.com/repos/${repo}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
        "User-Agent": "prio3-live",
      },
      body: JSON.stringify({ ref: "main", inputs: { refresh: "true" } }),
    },
  );
  if (!r.ok) {
    return { dispatched: false, reason: `GitHub HTTP ${r.status}`, age_min: ageMin };
  }
  lastDispatch = Date.now();
  return { dispatched: true, workflow, age_min: ageMin };
}

function cached<T>(key: string, ttlSec: number, fn: () => Promise<T>): Promise<T> {
  const now = Date.now();
  const hit = cache.get(key);
  if (hit && now - hit.ts < ttlSec * 1000) return Promise.resolve(hit.data as T);
  return fn().then((data) => {
    cache.set(key, { ts: now, data });
    return data;
  });
}

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response(null, { headers: corsHeaders });

  try {
    const body = req.method === "POST" ? await req.json().catch(() => ({})) : {};
    const url = new URL(req.url);
    const endpoint = (body.endpoint ?? url.searchParams.get("endpoint") ?? "live") as string;

    if (endpoint === "live") {
      const data = await cached("live", 20, collectLive);
      return json(data);
    }
    if (endpoint === "multiquotes") {
      const data = await cached("multiquotes", 60, multiquotes);
      return json(data);
    }
    if (endpoint === "refresh") {
      return json(await dispatchRefresh(Number(body.age_min ?? 0)));
    }
    return json(
      { error: "endpoint desconhecido", allowed: ["live", "multiquotes", "refresh"] },
      400,
    );
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
});
