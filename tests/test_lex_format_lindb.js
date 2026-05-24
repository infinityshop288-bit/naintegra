/** LINDB (del4657): ordinais Planalto quebrados (Art. 1\\no) e arts. 20–30 incluídos. */
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

const url = "https://www.planalto.gov.br/ccivil_03/decreto-lei/del4657.htm";
const synthetic =
  "Art. 1\no\nSalvo disposição contrária, a lei começa a vigorar em todo o país quarenta e cinco dias depois de oficialmente publicada.\n\n" +
  "Art. 2\no\nNão se destinando à vigência temporária.\n\n" +
  "Art. 6\no\nA lei em vigor terá efeito imediato.\n\n" +
  "Art. 6º A lei em vigor terá efeito imediato e geral.\n\n" +
  "Art. 19. Reputam-se válidos todos os atos.\n\n" +
  "Art. \n\t20. Nas esferas administrativa, controladora e judicial.\n\n" +
  "Art. \n\t30. As autoridades públicas devem atuar para aumentar a segurança jurídica.";

let body = synthetic;
const bodyPath = process.argv[2];
if (bodyPath) {
  const raw = fs.readFileSync(bodyPath, "utf8");
  body = raw.startsWith('"') ? JSON.parse(raw) : raw;
}

const fmt = LexFormat.formatDocument({ url, body, doc_type: "legislacao" });
const arts = fmt.blocks.filter((b) => b.type === "artigo");
const nums = arts.map((a) => a.label.replace(/\s+/g, " ").trim());

function hasArt(n) {
  return arts.some((a) => new RegExp(`^Art\\.\\s*${n}\\b`, "i").test(a.label.replace(/\s+/g, " ")));
}

for (const n of [1, 2, 6, 19, 20, 30]) {
  if (!hasArt(n)) {
    console.error(`Art. ${n} ausente. Labels:`, nums);
    process.exit(1);
  }
}

const art6 = arts.find((a) => /^Art\.\s*6\b/i.test(a.label));
if (art6 && art6.text.length > 2500) {
  console.error("Art. 6 engoliu texto demais:", art6.text.length);
  process.exit(1);
}

const art1 = arts.find((a) => /^Art\.\s*1\b/i.test(a.label));
if (!/quarenta e cinco dias/i.test(art1.text)) {
  console.error("Art. 1 incorreto:", art1.text.slice(0, 120));
  process.exit(1);
}

console.log("ok", arts.length, "artigos");
