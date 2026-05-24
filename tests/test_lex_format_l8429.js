/** Lei 8.429: referências internas (art. 1º desta Lei) não podem ser tratadas como cabeçalho. */
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

const url = "https://www.planalto.gov.br/ccivil_03/leis/l8429.htm";
const synthetic =
  "Art. 1° Os atos de improbidade praticados por qualquer agente público. (Revogado)\n\n" +
  "Art. 1º O sistema de responsabilização por atos de improbidade administrativa tutelará a probidade na organização do Estado.\n\n" +
  "Art. 2º Para os efeitos desta Lei, consideram-se agente público o agente político.\n\n" +
  "Art. 9º Constitui ato de improbidade.\n\n" +
  "VI - violar o art. 1º desta Lei, e notadamente:\n" +
  "I - facilitar a indevida incorporação ao patrimônio.\n\n" +
  "Art. 10 Constitui ato de improbidade administrativa que causa lesão ao erário.";

const body = process.argv[2] ? fs.readFileSync(process.argv[2], "utf8") : synthetic;
const fmt = LexFormat.formatDocument({ url, body, doc_type: "legislacao" });
const arts = fmt.blocks.filter((b) => b.type === "artigo");
const labels = arts.map((a) => a.label);
const art1 = arts.find((a) => /^Art\.\s*1[º°o]?$/i.test(a.label.trim()));

if (!art1 || !/responsabiliza[cç][ãa]o|atos de improbidade/i.test(art1.text)) {
  console.error("Art. 1 ausente ou incorreto:", art1?.text?.slice(0, 120));
  process.exit(1);
}
if (!labels.some((l) => /^Art\.\s*2/i.test(l))) {
  console.error("Art. 2 ausente. Labels:", labels.slice(0, 8));
  process.exit(1);
}
if (!labels.some((l) => /^Art\.\s*10/i.test(l))) {
  console.error("Art. 10 ausente. Labels:", labels.slice(-5));
  process.exit(1);
}

console.log("ok", arts.length, "artigos");
