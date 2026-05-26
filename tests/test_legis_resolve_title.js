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

  const l6015Title = LexLegisMeta.resolveLegisTitle(
    "https://www.planalto.gov.br/ccivil_03/leis/l6015consolidado.htm",
    "Dispõe sobre os registros públicos",
    "Lei 6.015/1973 — Debêntures"
  );
  if (!/Registros Públicos/i.test(l6015Title) || /Debêntur/i.test(l6015Title)) {
    console.error("l6015 titulo incorreto:", l6015Title);
    process.exit(1);
  }

  const l8036Title = LexLegisMeta.lookupKnownMeta(
    "https://www.planalto.gov.br/ccivil_03/leis/l8036consol.htm"
  )?.titulo;
  if (!/FGTS/i.test(l8036Title || "")) {
    console.error("l8036 titulo incorreto:", l8036Title);
    process.exit(1);
  }

  const cases = [
    ["l11671", /Presídios federais/i, /Desjudicial/i],
    ["l14965", /Concursos públicos/i, /Educação financeira/i],
    ["l15040", /Contrato de Seguro/i, /licita/i],
  ];
  for (const [key, good, bad] of cases) {
    const t = LexLegisMeta.lookupKnownMeta(`https://www.planalto.gov.br/ccivil_03/leis/${key}.htm`)?.titulo || "";
    if (!good.test(t) || bad.test(t)) {
      console.error(`${key} titulo incorreto:`, t);
      process.exit(1);
    }
  }

  console.log("ok resolveLegisTitle");
})();
