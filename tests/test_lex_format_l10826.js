const fs = require("fs");
const path = require("path");
const vm = require("vm");

global.window = global;
global.document = { createElement: () => ({ textContent: "", innerHTML: "" }) };
global.fetch = async () => ({
  ok: true,
  json: async () =>
    JSON.parse(fs.readFileSync(path.join(__dirname, "../web/lex/data/legis_known_meta.json"), "utf8")),
});

const root = path.join(__dirname, "..");
vm.runInThisContext(fs.readFileSync(path.join(root, "web/lex/js/legis-meta.js"), "utf8"));
vm.runInThisContext(fs.readFileSync(path.join(root, "web/lex/js/lex-format.js"), "utf8"));

const url = "https://www.planalto.gov.br/ccivil_03/leis/2003/l10.826.htm";
const sample = [
  "LEI No 10.826, DE 22 DE DEZEMBRO DE 2003.",
  "Dispõe sobre registro, posse e comercialização de armas de fogo e munição.",
  "CAPÍTULO I",
  ...Array.from({ length: 15 }, (_, i) => `Art. ${i + 1}o Texto do artigo ${i + 1}.`),
  ...Array.from({ length: 20 }, () => "~~ Regulamento ~~"),
].join("\n");

(async () => {
  await LexLegisMeta.loadKnownMeta();
  const meta = LexLegisMeta.lookupKnownMeta(url);
  if (!/Estatuto do Desarmamento/i.test(meta?.titulo || "")) {
    console.error("titulo incorreto:", meta?.titulo);
    process.exit(1);
  }
  if (/Fundos de investimento/i.test(meta?.titulo || "")) {
    console.error("titulo ainda aponta fundos:", meta?.titulo);
    process.exit(1);
  }
  const doc = { url, doc_type: "legislacao", body: sample };
  LexFormat.ensureFormatted(doc);
  const arts = doc.formatted?.articles?.length || 0;
  if (arts < 10) {
    console.error("poucos artigos formatados:", arts);
    process.exit(1);
  }
  console.log("ok", meta.titulo, arts, "artigos no sample");
})();
