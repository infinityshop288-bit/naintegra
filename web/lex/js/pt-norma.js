/**
 * Normalização de português jurídico (norma culta) para texto de crawl.
 * Ortografia, tipografia, citações e artefatos comuns do Planalto/Trilhante.
 */
(function () {
  const VERSION = 2;

  const MOJIBAKE = [
    ["Ã¡", "á"],
    ["Ã©", "é"],
    ["Ã­", "í"],
    ["Ã³", "ó"],
    ["Ãº", "ú"],
    ["Ã¢", "â"],
    ["Ãª", "ê"],
    ["Ã´", "ô"],
    ["Ã£", "ã"],
    ["Ãµ", "õ"],
    ["Ã§", "ç"],
    ["Ã‰", "É"],
    ["Ãš", "Ú"],
    ["Ãƒ", "Ã"],
    ["Ã•", "Õ"],
    ["Âº", "º"],
    ["Â§", "§"],
    ["ï¿½", ""],
    ["\uFFFD", ""],
  ];

  /** Palavras frequentes sem acento em crawls (somente palavra inteira). */
  const ACCENT_WORDS = [
    ["nao", "não"],
    ["sera", "será"],
    ["serao", "serão"],
    ["sao", "são"],
    ["estara", "estará"],
    ["estarao", "estarão"],
    ["podera", "poderá"],
    ["poderao", "poderão"],
    ["devera", "deverá"],
    ["deverao", "deverão"],
    ["houvera", "houverá"],
    ["tambem", "também"],
    ["porem", "porém"],
    ["alem", "além"],
    ["apos", "após"],
    ["ate", "até"],
    ["ja", "já"],
    ["la", "lá"],
    ["so", "só"],
    ["numero", "número"],
    ["numeros", "números"],
    ["artigo", "artigo"],
    ["publico", "público"],
    ["publica", "pública"],
    ["publicos", "públicos"],
    ["publicas", "públicas"],
    ["unico", "único"],
    ["unica", "única"],
    ["ultimo", "último"],
    ["ultima", "última"],
    ["constituicao", "constituição"],
    ["organica", "orgânica"],
    ["jurisdicao", "jurisdição"],
    ["competencia", "competência"],
    ["violacao", "violação"],
    ["decisao", "decisão"],
    ["condenacao", "condenação"],
    ["ilicitos", "ilícitos"],
    ["ilicita", "ilícita"],
    ["ilicito", "ilícito"],
    ["administracao", "administração"],
    ["obrigacao", "obrigação"],
    ["obrigacoes", "obrigações"],
    ["disposicao", "disposição"],
    ["disposicoes", "disposições"],
    ["revogacao", "revogação"],
    ["alteracao", "alteração"],
    ["redacao", "redação"],
    ["vigencia", "vigência"],
    ["eficacia", "eficácia"],
    ["licitacao", "licitação"],
    ["contratacao", "contratação"],
    ["sancao", "sanção"],
    ["sancoes", "sanções"],
    ["extraordinario", "extraordinário"],
    ["ordinario", "ordinário"],
    ["publicacao", "publicação"],
    ["sumula", "súmula"],
    ["sumulas", "súmulas"],
    ["observancia", "observância"],
    ["obrigatoria", "obrigatória"],
    ["obrigatorio", "obrigatório"],
    ["repercussao", "repercussão"],
    ["paragrafo", "parágrafo"],
    ["paragrafos", "parágrafos"],
    ["alinea", "alínea"],
    ["alineas", "alíneas"],
    ["codigo", "código"],
    ["codigos", "códigos"],
    ["provisoria", "provisória"],
    ["convenio", "convênio"],
    ["plenario", "plenário"],
    ["plenaria", "plenária"],
    ["tributaria", "tributária"],
    ["tributario", "tributário"],
    ["previdenciario", "previdenciário"],
    ["previdenciaria", "previdenciária"],
    ["intervencao", "intervenção"],
    ["sindicancia", "sindicância"],
    ["anulatoria", "anulatória"],
    ["convalidacao", "convalidação"],
    ["ratificacao", "ratificação"],
    ["homologacao", "homologação"],
    ["adjudicacao", "adjudicação"],
    ["habilitacao", "habilitação"],
    ["qualificacao", "qualificação"],
    ["impugnacao", "impugnação"],
    ["especie", "espécie"],
    ["especies", "espécies"],
    ["beneficio", "benefício"],
    ["beneficios", "benefícios"],
    ["previdencia", "previdência"],
    ["seguranca", "segurança"],
    ["atribuicao", "atribuição"],
    ["atribuicoes", "atribuições"],
    ["responsabilizacao", "responsabilização"],
    ["responsabilizacoes", "responsabilizações"],
    ["indenizacao", "indenização"],
    ["indenizacoes", "indenizações"],
    ["reparacao", "reparação"],
    ["reparacoes", "reparações"],
    ["indenizatorio", "indenizatório"],
    ["indenizatoria", "indenizatória"],
  ];

  const GLUED_LEGAL = [
    "público",
    "pública",
    "públicos",
    "públicas",
    "privado",
    "privada",
    "dolosamente",
    "culposamente",
    "administrativa",
    "administrativo",
    "administrativos",
    "constitucionais",
    "jurídica",
    "jurídico",
    "dolosa",
    "doloso",
    "efetivamente",
    "comprovadamente",
    "obrigatoriamente",
    "expressamente",
    "especificamente",
    "respectivamente",
    "independentemente",
    "cumulativamente",
    "subsidiariamente",
    "alternativamente",
  ];

  const GLUED_PREPS = [
    "nos",
    "nas",
    "num",
    "numa",
    "pelo",
    "pela",
    "pelos",
    "pelas",
    "que",
    "por",
    "como",
    "para",
    "sem",
    "sobre",
    "entre",
    "contra",
    "mediante",
    "conforme",
    "durante",
  ];

  function matchCase(source, target) {
    if (source === source.toUpperCase()) return target.toUpperCase();
    if (source[0] === source[0].toUpperCase()) {
      return target.charAt(0).toUpperCase() + target.slice(1);
    }
    return target;
  }

  function fixMojibake(text) {
    let t = String(text || "");
    if (!/[ÃÂï¿½\uFFFD]/.test(t)) return t;
    for (const [bad, good] of MOJIBAKE) {
      t = t.split(bad).join(good);
    }
    return t;
  }

  function fixWordAccents(text) {
    let t = text;
    for (const [wrong, right] of ACCENT_WORDS) {
      if (wrong === right) continue;
      t = t.replace(new RegExp(`\\b${wrong}\\b`, "gi"), (m) => matchCase(m, right));
    }
    return t;
  }

  function fixTypography(text) {
    let t = String(text || "");
    t = t.replace(/\s+([,;:.!?])/g, "$1");
    t = t.replace(/([,;:])(?=[A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç])/g, "$1 ");
    t = t.replace(/\.(?=[A-Za-zÁÉÍÓÚÂÊÔÃÕÇ])/g, ". ");
    t = t.replace(/\(\s+/g, "(");
    t = t.replace(/\s+\)/g, ")");
    t = t.replace(/\.{2,}/g, ".");
    t = t.replace(/,{2,}/g, ",");
    t = t.replace(/[ \t]{2,}/g, " ");
    t = t.replace(/\s+\n/g, "\n");
    t = t.replace(/\n{3,}/g, "\n\n");
    return t;
  }

  function fixLegalCitations(text) {
    let t = text;
    t = t.replace(/\bSumula\b/g, "Súmula");
    t = t.replace(/\bsumula\b/g, "súmula");
    t = t.replace(/\bSUMULA\b/g, "SÚMULA");
    t = t.replace(/\bS[úu]mula\s+Vinculante\b/gi, "Súmula Vinculante");
    t = t.replace(/\bn\.\s*º\b/gi, "nº");
    t = t.replace(/\bn\.\s*°/gi, "nº");
    t = t.replace(/\bN\.\s*º\b/g, "Nº");
    t = t.replace(/\b§\s*(\d+)\s*°/gi, "§ $1º");
    t = t.replace(/\b§\s*(\d+)\s*o\b/gi, "§ $1º");
    t = t.replace(/\bArt\.\s*(\d+)\s*°/gi, "Art. $1º");
    t = t.replace(/\bart\.\s*(\d+)\s*°/gi, "art. $1º");
    t = t.replace(/\bArt\.\s*(\d+)\s+o\b/gi, "Art. $1º");
    t = t.replace(/\bart\.\s*(\d+)\s+o\b/gi, "art. $1º");
    t = t.replace(/\bart\.\s*(\d+)o\b/gi, "art. $1º");
    t = t.replace(/\bArt\.\s*(\d+)o\b/gi, "Art. $1º");
    t = t.replace(/\bParagrafo\s+unico\b/gi, "Parágrafo único");
    t = t.replace(/\bparagrafo\s+unico\b/gi, "parágrafo único");
    t = t.replace(/\bDecreto\s*-\s*Lei\b/gi, "Decreto-Lei");
    t = t.replace(/\bLei\s+Complementar\s+n[º°.]?\s*/gi, "Lei Complementar ");
    t = t.replace(/\bLei\s+n[º°.]?\s*/gi, "Lei ");
    t = t.replace(/\bConstituicao\s+Federal\b/gi, "Constituição Federal");
    t = t.replace(/\bRecurso\s+Extraordinario\b/gi, "Recurso Extraordinário");
    t = t.replace(/\bRecurso\s+Ordinario\b/gi, "Recurso Ordinário");
    t = t.replace(/\bRepercussao\s+Geral\b/gi, "Repercussão Geral");
    t = t.replace(/\bRecurso\s+Repetitivo\b/gi, "Recurso Repetitivo");
    t = t.replace(/\bTema\s+de\s+Repetitivo\b/gi, "Tema de Repetitivo");
    return t;
  }

  function fixCrawlPhrasing(text) {
    return String(text || "")
      .replace(/\b((?:nesta|desta|esta)\s+Lei)\s+(os|as)\b/gi, "$1, $2")
      .replace(/\badministração\s+pública\s+(convênio|contrato)\b/gi, "administração pública, $1")
      .replace(/\bConsti\s+tui\b/gi, "Constitui")
      .replace(/\bConversacao\d*\b/gi, "")
      .replace(/\bnao\s+podera\b/gi, "não poderá")
      .replace(/\bnao\s+podem\b/gi, "não podem")
      .replace(/\bnao\s+se\s+aplica\b/gi, "não se aplica")
      .replace(/\bhao\s+crime\b/gi, "há crime")
      .replace(/\bnao\s+ha\b/gi, "não há");
  }

  function splitStuckWords(text) {
    let t = text;
    const glued = [...GLUED_LEGAL, ...GLUED_PREPS].sort((a, b) => b.length - a.length);
    for (const w of glued) {
      const esc = w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      t = t.replace(
        new RegExp(`([a-záéíóúãõç]{4,})(${esc})(?=\\s|[.,;:)\\]\\-]|$)`, "gi"),
        (full, head, tail) => {
          if (/vincul$/i.test(head) && /^ante$/i.test(tail)) return full;
          if (/inconform$/i.test(head) && /^e$/i.test(tail)) return full;
          return `${head} ${tail}`;
        }
      );
    }
    t = t.replace(/([a-záéíóúãõç])([A-ZÁÉÍÓÚÃÕÇ])/g, "$1 $2");
    return t.replace(/[ \t]{2,}/g, " ");
  }

  function fixBrokenSyllables(text) {
    const noMerge = new Set([
      "de", "da", "do", "dos", "das", "em", "no", "na", "nos", "nas", "ao", "aos",
      "ou", "se", "um", "uma", "e", "a", "o", "as", "os", "que", "por", "para", "com",
      "art", "arts", "lei", "cf",
    ]);
    return String(text || "").replace(
      /(^|\n)([A-Za-zÁÉÍÓÚáéíóúÃÕÇãõç]{1,4})\s*\n+\s*([a-záéíóúãõç])/gm,
      (full, bol, head, tail) => {
        if (noMerge.has(head.toLowerCase())) return `${bol}${head} ${tail}`;
        return `${bol}${head}${tail}`;
      }
    );
  }

  /**
   * @param {string} text
   * @param {{ domain?: 'legis'|'juris'|'all' }} [opts]
   */
  function apply(text, opts = {}) {
    if (!text) return "";
    let t = fixMojibake(text);
    t = fixBrokenSyllables(t);
    t = fixLegalCitations(t);
    t = fixWordAccents(t);
    t = splitStuckWords(t);
    t = fixCrawlPhrasing(t);
    if (opts.domain !== "juris") {
      t = fixTypography(t);
    } else {
      t = t.replace(/[ \t]{2,}/g, " ");
    }
    if (window.LexLegisMeta?.normalizeLeiReferences) {
      t = window.LexLegisMeta.normalizeLeiReferences(t);
    }
    return t;
  }

  window.LexPtNorma = {
    VERSION,
    apply,
    fixMojibake,
    fixTypography,
    fixLegalCitations,
    fixWordAccents,
    splitStuckWords,
  };
})();
