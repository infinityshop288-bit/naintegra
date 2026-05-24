/** Smoke test: importação de flashcards (CSV, JSON, TSV, ::). */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

global.window = global;
vm.runInThisContext(fs.readFileSync(path.join(__dirname, "../web/lex/js/flashcards-user.js"), "utf8"));

const { parseImport, normalizeCard } = window.LexFlashcardsUser;

const csv = fs.readFileSync(
  path.join(__dirname, "../examples/flashcards_licitacoes_lei14133.csv"),
  "utf8"
);
const csvParsed = parseImport(csv, { filename: "test.csv" });
if (csvParsed.count < 5) {
  console.error("CSV import failed:", csvParsed.count);
  process.exit(1);
}

const json = JSON.stringify({
  name: "Teste",
  cards: [{ front: "Pergunta?", back: "Resposta." }],
});
const jsonParsed = parseImport(json);
if (jsonParsed.count !== 1 || !/Resposta/.test(jsonParsed.cards[0].back)) {
  console.error("JSON import failed");
  process.exit(1);
}

const tsv = "O que é CF?\tConstituição Federal de 1988\nArt. 5?\tDireitos fundamentais";
const tsvParsed = parseImport(tsv, { filename: "anki.txt" });
if (tsvParsed.count !== 2) {
  console.error("TSV import failed:", tsvParsed.count);
  process.exit(1);
}

const dc = "Pergunta A::Resposta A\nPergunta B::Resposta B";
const dcParsed = parseImport(dc);
if (dcParsed.count !== 2) {
  console.error(":: import failed");
  process.exit(1);
}

if (!normalizeCard({ front: " x ", back: " y " })) {
  console.error("normalizeCard failed");
  process.exit(1);
}

global.localStorage = {
  _d: {},
  getItem(k) {
    return this._d[k] ?? null;
  },
  setItem(k, v) {
    this._d[k] = v;
  },
};
vm.runInThisContext(fs.readFileSync(path.join(__dirname, "../web/lex/js/flashcards-user.js"), "utf8"), { filename: "flashcards-user.js" });
const deck = LexFlashcardsUser.createDeck({
  name: "Teste",
  cards: [{ front: "P1", back: "R1" }],
});
const updated = LexFlashcardsUser.updateCard(deck.slug, 0, { front: "P1 edit", back: "R1 edit" });
if (!updated || updated.cards[0].front !== "P1 edit") {
  console.error("updateCard failed");
  process.exit(1);
}

console.log("ok", csvParsed.count, "csv cards");
