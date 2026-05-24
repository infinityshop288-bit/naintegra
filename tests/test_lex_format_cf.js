/** Smoke test: CF — artigos permanentes antes do ADCT. */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

global.window = global;
global.document = {
  createElement: () => {
    const o = { _t: "" };
    Object.defineProperty(o, "textContent", {
      set(v) {
        o._t = v;
      },
      get() {
        return o._t;
      },
    });
    Object.defineProperty(o, "innerHTML", {
      get() {
        return String(o._t || "");
      },
    });
    return o;
  },
};

const root = path.join(__dirname, "..");
vm.runInThisContext(fs.readFileSync(path.join(root, "web/lex/js/legis-meta.js"), "utf8"));
vm.runInThisContext(fs.readFileSync(path.join(root, "web/lex/js/lex-format.js"), "utf8"));

const cfUrl = "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm";

function assertCfOrder(body, label) {
  const fmt = LexFormat.formatDocument({ url: cfUrl, body, doc_type: "legislacao" });
  const arts = fmt.blocks.filter((b) => b.type === "artigo");
  const art1 = arts.find((a) => /^Art\.\s*1/i.test(a.label) && !/ADCT/i.test(a.label));
  const art3 = arts.find((a) => /^Art\.\s*3/i.test(a.label) && !/ADCT/i.test(a.label));
  const art250 = arts.find((a) => /^Art\.\s*250/i.test(a.label) && !/ADCT/i.test(a.label));
  const adct1 = arts.find((a) => /ADCT/i.test(a.label) && /1/.test(a.label));
  const adctIdx = arts.findIndex((a) => /ADCT/i.test(a.label));
  const lastCfIdx = arts.reduce(
    (acc, a, i) => (!/ADCT/i.test(a.label) ? i : acc),
    -1
  );

  if (!art1 || !/República Federativa/i.test(art1.text)) {
    console.error(`[${label}] CF Art. 1 incorreto:`, art1?.text?.slice(0, 80));
    process.exit(1);
  }
  if (!adct1 || !/compromisso/i.test(adct1.text)) {
    console.error(`[${label}] ADCT Art. 1 ausente ou incorreto:`, adct1?.text?.slice(0, 80));
    process.exit(1);
  }
  if (adctIdx >= 0 && lastCfIdx >= 0 && adctIdx <= lastCfIdx) {
    console.error(`[${label}] ADCT aparece antes do fim dos artigos da CF`);
    process.exit(1);
  }
  if (art3 && adct1) {
    const i3 = arts.indexOf(art3);
    const iAdct = arts.indexOf(adct1);
    if (iAdct <= i3) {
      console.error(`[${label}] ADCT Art. 1 antes do Art. 3 da CF`);
      process.exit(1);
    }
  }
  if (art250 && adct1 && arts.indexOf(adct1) <= arts.indexOf(art250)) {
    console.error(`[${label}] ADCT antes do Art. 250`);
    process.exit(1);
  }
  if (!fmt.ementa || !/organiza[cç][ãa]o do Estado/i.test(fmt.ementa)) {
    console.error(`[${label}] CF ementa incorreta:`, fmt.ementa);
    process.exit(1);
  }
  if (fmt.epigrafe !== "Constituição Federal de 1988") {
    console.error(`[${label}] CF epígrafe incorreta:`, fmt.epigrafe);
    process.exit(1);
  }
  return arts.length;
}

const simpleBody = process.argv[2]
  ? fs.readFileSync(process.argv[2], "utf8")
  : "Texto compilado\n\nTÍTULO I\n\nArt. 1º A República Federativa do Brasil.\n\nAto das Disposições Constitucionais Transitórias\n\nArt. 1º O Presidente da República prestará o compromisso.";

const withInlineRef =
  "Texto compilado\n\nTÍTULO I\n\nArt. 1º A República Federativa do Brasil.\n\nArt. 3º Conforme o Ato das Disposições Constitucionais Transitórias, princípios.\n\nArt. 250º O sufragio é universal.\n\nAto das Disposições Constitucionais Transitórias\n\nArt. 1º O Presidente da República prestará o compromisso.";

const n1 = assertCfOrder(simpleBody, "simples");
const n2 = assertCfOrder(withInlineRef, "citação inline");
const n3 = process.argv[2] ? assertCfOrder(simpleBody, "arquivo") : n1;

console.log("ok", n1, n2, n3, "artigos (amostras)");
