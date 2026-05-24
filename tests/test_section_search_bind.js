/** Campo de busca por seção fica fora de data-section-scope — input deve ser encontrado no documento. */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

global.window = global;

function makeEl(tag) {
  return {
    tagName: tag.toUpperCase(),
    children: [],
    attributes: {},
    hidden: false,
    className: "",
    parentElement: null,
    appendChild(c) {
      c.parentElement = this;
      this.children.push(c);
      return c;
    },
    setAttribute(k, v) {
      this.attributes[k] = String(v);
    },
    getAttribute(k) {
      return this.attributes[k] ?? null;
    },
    querySelectorAll(sel) {
      const out = [];
      walk(this, (node) => {
        if (match(node, sel)) out.push(node);
      });
      return out;
    },
  };
}

function walk(node, fn) {
  if (node.tagName) fn(node);
  for (const c of node.children || []) walk(c, fn);
}

function match(node, sel) {
  const cls = sel.match(/\.([a-z0-9_-]+)/i)?.[1];
  const attr = sel.match(/\[data-section="([^"]+)"\]/);
  if (attr && node.getAttribute("data-section") !== attr[1]) return false;
  if (cls && !node.className.includes(cls)) return false;
  return true;
}

const body = makeEl("div");
const searchWrap = makeEl("div");
const input = makeEl("input");
input.className = "section-search-input";
input.setAttribute("data-section", "lei-seca");
searchWrap.appendChild(input);

const scope = makeEl("div");
scope.className = "section-list-scope";
scope.setAttribute("data-section-scope", "lei-seca");
const card = makeEl("article");
card.className = "law-card";
card.setAttribute("data-search-text", "Lei 8429 improbidade administrativa");
scope.appendChild(card);

body.appendChild(searchWrap);
body.appendChild(scope);

global.document = {
  querySelector(sel) {
    let found = null;
    walk(body, (node) => {
      if (!found && match(node, sel)) found = node;
    });
    return found;
  },
  createElement: () => makeEl("span"),
};

vm.runInThisContext(fs.readFileSync(path.join(__dirname, "..", "web/lex/js/section-search.js"), "utf8"));

const found = LexSectionSearch.sectionInput("lei-seca");
if (!found || found !== input) {
  console.error("sectionInput nao encontrou o campo");
  process.exit(1);
}

const r1 = LexSectionSearch.applyFilter(scope, "improbidade");
if (r1.visible !== 1 || card.hidden) {
  console.error("filtro improbidade falhou", r1, card.hidden);
  process.exit(1);
}

const r2 = LexSectionSearch.applyFilter(scope, "xyz123");
if (r2.visible !== 0 || !card.hidden) {
  console.error("filtro sem match falhou", r2, card.hidden);
  process.exit(1);
}

console.log("ok");
