#!/usr/bin/env node
/** Exporta títulos e resumos (ementa) de todas as leis do catálogo Lex para web/lex/data/legis_summaries.json */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "..");
const globalObj = global;
globalObj.window = globalObj;
globalObj.document = {
  createElement: () => {
    const el = { _t: "" };
    Object.defineProperty(el, "textContent", {
      set(v) {
        el._t = v;
      },
      get() {
        return el._t;
      },
    });
    return el;
  },
};

vm.runInThisContext(fs.readFileSync(path.join(root, "web/lex/js/lex-format.js"), "utf8"));
vm.runInThisContext(fs.readFileSync(path.join(root, "web/lex/js/legis-meta.js"), "utf8"));
eval(
  fs
    .readFileSync(path.join(root, "web/lex/js/config.js"), "utf8")
    .replace("window.LEX_CONFIG", "global.LEX_CONFIG")
);
const cfg = globalObj.LEX_CONFIG;

async function loadKnownMeta() {
  try {
    const raw = fs.readFileSync(path.join(root, "web/lex/data/legis_known_meta.json"), "utf8");
    LexLegisMeta.setKnownMetaCache(JSON.parse(raw).entries || {});
  } catch (_) {
    LexLegisMeta.setKnownMetaCache({});
  }
}

async function rpc(name, body) {
  const res = await fetch(`${cfg.supabaseUrl}/rest/v1/rpc/${name}`, {
    method: "POST",
    headers: {
      apikey: cfg.supabaseAnonKey,
      Authorization: `Bearer ${cfg.supabaseAnonKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw new Error(`${name}: ${res.status}`);
  return res.json();
}

function bodyFrom(chunks) {
  if (typeof chunks === "string") return chunks;
  if (Array.isArray(chunks)) return chunks.map((c) => c.content || c.text || "").join("\n");
  return "";
}

function summaryKey(url) {
  try {
    return new URL(url).pathname.replace(/\/+$/, "").toLowerCase();
  } catch {
    return String(url).split("?")[0].replace(/\/+$/, "").toLowerCase();
  }
}

(async () => {
  await loadKnownMeta();
  const rows = [
    ...(await rpc("list_norma_document_catalog", { p_source: "planalto", p_limit: 500, p_offset: 0 })),
    ...(await rpc("list_norma_document_catalog", { p_source: "rideel_vademecum", p_limit: 500, p_offset: 0 })),
  ];
  const seen = new Set();
  const summaries = {};
  const list = [];

  for (const row of rows) {
    const url = row.url || row.doc_key;
    if (!url || seen.has(url)) continue;
    seen.add(url);
    const src = row.source || "rideel_vademecum";
    let body = "";
    try {
      body = bodyFrom(await rpc("get_norma_document_chunks", { p_source: src, p_url: url }));
    } catch {
      continue;
    }
    if (!body.trim()) continue;

    const meta = LexLegisMeta.metaFromUrl(url, body) || LexLegisMeta.metaFromUrl(url, "");
    if (!meta) continue;

    const entry = {
      titulo: meta.titulo,
      resumo: meta.resumo,
      secao: meta.secao_lei_seca,
      url,
    };
    summaries[summaryKey(url)] = entry;
    list.push(entry);
  }

  list.sort((a, b) => a.titulo.localeCompare(b.titulo, "pt"));

  const outPath = path.join(root, "web/lex/data/legis_summaries.json");
  fs.writeFileSync(
    outPath,
    JSON.stringify(
      {
        generated_at: new Date().toISOString(),
        count: list.length,
        summaries,
        list,
      },
      null,
      2
    )
  );
  console.log(`Wrote ${list.length} law summaries to ${outPath}`);
})();
