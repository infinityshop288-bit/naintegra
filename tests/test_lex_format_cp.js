/** CP (del2848): blocos Planalto ~~…~~, epígrafes e estrutura padrão. */
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

const url = "https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848.htm";

function block(inner) {
  return `~~\n${inner}\n~~`;
}

const synthetic =
  block("TÍTULO I") +
  block("Da aplicação da lei penal") +
  block("Anterioridade da Lei") +
  block("Art. 1° Não há crime sem lei anterior que o defina. Não há pena sem prévia cominação legal.") +
  block("A lei penal no tempo") +
  block(
    "Art. 2º Ninguém pode ser punido por fato que lei posterior deixa de considerar crime, cessando em virtude dela a execução e os efeitos penais da sentença condenatória."
  ) +
  block(
    "Parágrafo único. A lei posterior, que de outro modo favorece o agente, aplica-se ao fato não definitivamente julgado."
  ) +
  block(
    "Art. 3° A lei excepcional ou temporária, embora decorrido o período de sua duração ou cessadas as circunstâncias que a determinaram, aplica-se ao fato praticado durante sua vigência."
  ) +
  block("Lugar do crime") +
  block(
    "Art. 4° Aplica-se a lei brasileira, sem prejuízo de convenções, tratados e regras de direito internacional, ao crime cometido, no todo ou em parte, no território nacional."
  ) +
  block("Extraterritorialidade") +
  block("Art. 5º Ficam sujeitos à lei brasileira, embora cometidos no estrangeiro:") +
  block("I - os crimes:") +
  block("a) contra a vida ou a liberdade do Presidente da República;");

let body = synthetic;
const bodyPath = process.argv[2];
if (bodyPath) {
  const raw = fs.readFileSync(bodyPath, "utf8");
  body = raw.startsWith('"') ? JSON.parse(raw) : raw;
}

const fmt = LexFormat.formatDocument({ url, body, doc_type: "legislacao" });
const arts = fmt.blocks.filter((b) => b.type === "artigo");

const art1 = arts.find((a) => /^Art\.\s*1/i.test(a.label));
const art2 = arts.find((a) => /^Art\.\s*2/i.test(a.label));
const art3 = arts.find((a) => /^Art\.\s*3/i.test(a.label));
const art4 = arts.find((a) => /^Art\.\s*4/i.test(a.label));
const art5 = arts.find((a) => /^Art\.\s*5/i.test(a.label));

if (!art1 || !/Anterioridade da Lei/i.test(art1.label)) {
  console.error("Art. 1 sem epígrafe:", art1?.label);
  process.exit(1);
}
if (!art2 || !/Parágrafo único/i.test(art2.text)) {
  console.error("Art. 2 sem parágrafo único:", art2?.text?.slice(0, 100));
  process.exit(1);
}
if (art3 && /Lugar do crime/i.test(art3.text)) {
  console.error("Art. 3 ainda contém epígrafe errada");
  process.exit(1);
}
if (!art4 || !/Lugar do crime/i.test(art4.label)) {
  console.error("Art. 4 sem epígrafe no título:", art4?.label);
  process.exit(1);
}
if (!art5 || !/Extraterritorialidade/i.test(art5.label)) {
  console.error("Art. 5 sem epígrafe no título:", art5?.label);
  process.exit(1);
}
if (arts.some((a) => /~~/.test(a.text))) {
  console.error("Marcadores ~~ ainda presentes no corpo");
  process.exit(1);
}

if (bodyPath) {
  if (arts.length < 150) {
    console.error("CP incompleto: apenas", arts.length, "artigos");
    process.exit(1);
  }
  const caps = fmt.blocks.filter((b) => b.type === "capitulo");
  if (caps.length < 10) {
    console.error("CP sem capítulos estruturados:", caps.length);
    process.exit(1);
  }
}

console.log("ok", arts.length, "artigos", art4.label);
