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

const CASES = [
  {
    url: "https://www.planalto.gov.br/ccivil_03/leis/l1079.htm",
    expectAno: "1950",
    expectNum: "1.079",
    rejectAno: "2010",
  },
  {
    url: "https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848.htm",
    expectAno: "1940",
    expectNum: "2.848",
    rejectAno: "2028",
  },
  {
    url: "https://www.planalto.gov.br/ccivil_03/leis/l0605.htm",
    expectAno: "1949",
    expectNum: "605",
    rejectNum: "0.605",
  },
  {
    url: "https://www.planalto.gov.br/ccivil_03/leis/l8429.htm",
    expectAno: "1992",
    rejectAno: "1984",
  },
  {
    url: "https://www.planalto.gov.br/ccivil_03/leis/l1521.htm",
    expectAno: "1951",
    rejectAno: "2015",
    titleMatch: /economia popular/i,
    titleReject: /Imprensa/i,
  },
];

(async () => {
  await LexLegisMeta.loadKnownMeta();

  for (const c of CASES) {
    const norma = LexLegisMeta.parseNormaFromUrl(c.url, "");
    if (c.expectAno && norma?.ano !== c.expectAno) {
      console.error(`${c.url}: ano esperado ${c.expectAno}, obteve ${norma?.ano}`);
      process.exit(1);
    }
    if (c.rejectAno && norma?.ano === c.rejectAno) {
      console.error(`${c.url}: ano incorreto ${c.rejectAno}`);
      process.exit(1);
    }
    if (c.expectNum && norma?.numero !== c.expectNum) {
      console.error(`${c.url}: numero esperado ${c.expectNum}, obteve ${norma?.numero}`);
      process.exit(1);
    }
    if (c.rejectNum && norma?.numero === c.rejectNum) {
      console.error(`${c.url}: numero incorreto ${c.rejectNum}`);
      process.exit(1);
    }
    const meta = LexLegisMeta.metaFromUrl(c.url, "");
    if (c.titleMatch && !c.titleMatch.test(meta.titulo)) {
      console.error(`${c.url}: titulo incorreto ${meta.titulo}`);
      process.exit(1);
    }
    if (c.titleReject && c.titleReject.test(meta.titulo)) {
      console.error(`${c.url}: titulo rejeitado ${meta.titulo}`);
      process.exit(1);
    }
  }

  const ref605 = LexLegisMeta.formatNormaRef(LexLegisMeta.parseNormaFromUrl(
    "https://www.planalto.gov.br/ccivil_03/leis/l0605.htm",
    ""
  ));
  if (!/^Lei 605\/1949/.test(ref605 || "")) {
    console.error("referencia l0605 incorreta:", ref605);
    process.exit(1);
  }

  console.log("ok", CASES.length, "casos");
})();
