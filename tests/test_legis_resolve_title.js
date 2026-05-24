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

const L1521 = "https://www.planalto.gov.br/ccivil_03/leis/l1521.htm";
const L12037 = "https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2009/lei/l12037.htm";

(async () => {
  await LexLegisMeta.loadKnownMeta();

  const l1521BadBody =
    "LEI Nº 1.521, DE 26 DE DEZEMBRO DE 1951.\nAltera dispositivos da legislação vigente sobre crimes contra a economia popular.";
  const l1521Title = LexLegisMeta.resolveLegisTitle(L1521, l1521BadBody, "Lei 1.521/2015 — Imprensa");
  if (!/economia popular/i.test(l1521Title)) {
    console.error("l1521 titulo incorreto:", l1521Title);
    process.exit(1);
  }
  if (/Imprensa/i.test(l1521Title)) {
    console.error("l1521 ainda aponta Imprensa:", l1521Title);
    process.exit(1);
  }

  const l12037Body =
    "LEI Nº 12.037, DE 1º DE OUTUBRO DE 2009.\nDispõe sobre a identificação criminal do civilmente identificado.";
  const l12037Title = LexLegisMeta.resolveLegisTitle(
    L12037,
    "Texto antigo LEI Nº 12.037, DE 1990.\nRevoga disposições.",
    "Lei 12.037/2009 — Identificação criminal"
  );
  if (l12037Title !== "Lei 12.037/2009 — Identificação criminal") {
    console.error("l12037 titulo regrediu:", l12037Title);
    process.exit(1);
  }

  if (
    !LexLegisMeta.shouldPreferKnownLegisTitle(
      "Lei 1.521/1951 — Imprensa",
      "Lei 1.521/1951 — Crimes contra a economia popular"
    )
  ) {
    console.error("shouldPreferKnownLegisTitle deveria preferir metadado curado");
    process.exit(1);
  }

  console.log("ok resolveLegisTitle");
})();
