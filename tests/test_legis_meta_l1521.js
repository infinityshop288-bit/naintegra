const fs = require("fs");
const path = require("path");
const vm = require("vm");

global.window = global;
global.document = { createElement: () => ({ textContent: "", innerHTML: "" }) };
global.fetch = async () => ({
  ok: true,
  json: async () => JSON.parse(fs.readFileSync(path.join(__dirname, "../web/lex/data/legis_known_meta.json"), "utf8")),
});

const root = path.join(__dirname, "..");
vm.runInThisContext(fs.readFileSync(path.join(root, "web/lex/js/legis-meta.js"), "utf8"));

const url = "https://www.planalto.gov.br/ccivil_03/leis/l1521.htm";

(async () => {
  await LexLegisMeta.loadKnownMeta();
  const fromUrl = LexLegisMeta.parseNormaFromUrl(url, "");
  if (fromUrl?.ano === "2015") {
    console.error("ano incorreto inferido da URL:", fromUrl.ano);
    process.exit(1);
  }
  const meta = LexLegisMeta.metaFromUrl(url, "LEI Nº 1.521, DE 26 DE DEZEMBRO DE 1951.");
  if (!/economia popular/i.test(meta.titulo)) {
    console.error("titulo incorreto:", meta.titulo);
    process.exit(1);
  }
  if (/Imprensa/i.test(meta.titulo)) {
    console.error("titulo ainda aponta Imprensa:", meta.titulo);
    process.exit(1);
  }
  if (meta.secao_lei_seca !== "Penal e Processual") {
    console.error("secao incorreta:", meta.secao_lei_seca);
    process.exit(1);
  }
  console.log("ok", meta.titulo);
})();
