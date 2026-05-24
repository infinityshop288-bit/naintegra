/** Metadados e formatação de referências normativas (Lei 8.429/1992). */
(function () {
  function formatLeiNumber(raw) {
    let digits = String(raw ?? "").replace(/\D/g, "");
    digits = digits.replace(/^0+/, "") || "0";
    if (!digits) return "";
    if (digits.length <= 3) return digits;
    return `${digits.slice(0, -3)}.${digits.slice(-3)}`;
  }

  function extractYearFromBody(body) {
    if (!body) return null;
    const m = body.match(
      /(?:LEI|DECRETO-LEI|DECRETO)\s+N[º°.]?\s*[\d.]+\s*,?\s*DE\s+\d+\s+DE\s+\S+\s+DE\s+(\d{4})/i
    );
    return m?.[1] || null;
  }

  function extractYearFromUrl(url) {
    const u = url || "";
    const pathYear = u.match(/\/(\d{4})\/(?:lei|decreto|mp|medida|emc)/i);
    if (pathYear) return pathYear[1];
    const ato = u.match(/_ato\d{4}-\d{4}\/(\d{4})\//i);
    if (ato) return ato[1];
    const senado = u.match(/data=(\d{4})/i);
    if (senado) return senado[1];
    return null;
  }

  function anoFromKnownMeta(url) {
    const known = lookupKnownMeta(url || "");
    return known?.titulo?.match(/\/(\d{4})\b/)?.[1] || null;
  }

  function normaAno(url, body) {
    return extractYearFromBody(body) || anoFromKnownMeta(url) || extractYearFromUrl(url) || null;
  }

  let knownMetaCache = null;

  function normalizeKnownKey(url) {
    const u = String(url || "").toLowerCase();
    const path = u.includes("://") ? u.split("planalto.gov.br").pop() || u.split("senado.leg.br").pop() || u : u;
    return path.split("?")[0].replace(/\/+$/, "");
  }

  /** l10.741.htm → l10741, l6015consolidado.htm → l6015 */
  function extractLegisSlug(url) {
    const path = normalizeKnownKey(url);
    const m = path.match(/\/(lcp|del|emc|d|l)(\d[\d.]*?)(?:consolidado|consol|compilada|comp|cons|orig|_)?\.htm/i);
    if (!m) return null;
    const prefix = m[1].toLowerCase();
    const digits = m[2].replace(/\./g, "");
    if (prefix === "lcp") return `lcp${digits}`;
    if (prefix === "del") return `del${digits}`;
    if (prefix === "emc") return `emc${digits}`;
    if (prefix === "d") return `d${digits}`;
    return `l${digits}`;
  }

  function legisCanonicalKey(url) {
    if (/urn:lex:/i.test(String(url || ""))) return null;
    return extractLegisSlug(url) || normalizeKnownKey(url).toLowerCase();
  }

  function lookupKnownMeta(url) {
    if (!knownMetaCache) return null;
    const u = String(url || "").toLowerCase();
    for (const [key, meta] of Object.entries(knownMetaCache)) {
      if (u.includes(String(key).toLowerCase())) return meta;
    }
    const path = normalizeKnownKey(url);
    if (knownMetaCache[path]) return knownMetaCache[path];
    const slug = extractLegisSlug(url);
    if (!slug) return null;
    const variants = new Set([slug, slug.replace(/^l0+/i, "l"), slug.replace(/^lcp0+/i, "lcp")]);
    for (const v of variants) {
      if (knownMetaCache[v]) return knownMetaCache[v];
    }
    return null;
  }

  async function loadKnownMeta() {
    if (knownMetaCache) return knownMetaCache;
    try {
      const cfg = window.LEX_CONFIG || {};
      const res = await fetch(cfg.legisKnownMetaFallback || "./data/legis_known_meta.json");
      if (!res.ok) return {};
      const data = await res.json();
      knownMetaCache = data.entries || {};
      return knownMetaCache;
    } catch (_) {
      knownMetaCache = {};
      return knownMetaCache;
    }
  }

  function setKnownMetaCache(entries) {
    knownMetaCache = entries || {};
  }

  function parseNormaFromUrl(url, body) {
    const u = url || "";
    if (/constituicao\.htm/i.test(u)) {
      return { tipo: "Constituição", numero: "", ano: "1988" };
    }
    const emc = u.match(/\/emc(\d+)\.htm/i);
    if (emc) {
      return {
        tipo: "Emenda Constitucional",
        numero: emc[1],
        ano: normaAno(u, body),
      };
    }
    const lcp = u.match(/\/lcp(\d+)\.htm/i);
    if (lcp) {
      return {
        tipo: "Lei Complementar",
        numero: formatLeiNumber(lcp[1]),
        ano: normaAno(u, body),
      };
    }
    const del = u.match(/\/del(\d+)\.htm/i);
    if (del) {
      return {
        tipo: "Decreto-Lei",
        numero: formatLeiNumber(del[1]),
        ano: normaAno(u, body),
      };
    }
    const dec = u.match(/\/d(\d+)(?:cons)?\.htm/i);
    if (dec) {
      return {
        tipo: "Decreto",
        numero: formatLeiNumber(dec[1]),
        ano: normaAno(u, body),
      };
    }
    const lei = u.match(/\/l([\d.]+?)(?:consolidado|consol|compilada|comp|cons|orig|_)?\.htm/i);
    if (lei) {
      return {
        tipo: "Lei",
        numero: formatLeiNumber(lei[1].replace(/\./g, "")),
        ano: normaAno(u, body),
      };
    }
    const senado = u.match(/[?&]numero=(\d+)/i);
    if (senado) {
      return {
        tipo: "Lei",
        numero: formatLeiNumber(senado[1]),
        ano: extractYearFromUrl(u) || extractYearFromBody(body),
      };
    }
    return null;
  }

  function formatNormaRef(norma, subtitle) {
    if (!norma) return null;
    const ano = norma.ano || "????";
    let ref;
    if (norma.tipo === "Constituição") ref = "Constituição Federal de 1988";
    else if (norma.tipo === "Emenda Constitucional") ref = `EC nº ${norma.numero}/${ano}`;
    else ref = `${norma.tipo} ${norma.numero}/${ano}`;
    return subtitle ? `${ref} — ${subtitle}` : ref;
  }

  const EMENTA_OVERRIDES = [
    { re: /constituicao\.htm/i, resumo: "Estabelece a organização do Estado, direitos fundamentais e a estrutura da República Federativa do Brasil." },
    { re: /l1521/i, resumo: "Altera dispositivos da legislação vigente sobre crimes contra a economia popular." },
    { re: /l8429/i, resumo: "Previne e reprime atos de improbidade administrativa e regula processo de apuração e julgamento." },
    { re: /l8112|8112cons/i, resumo: "Dispõe sobre o regime jurídico dos servidores públicos civis da União, autarquias e fundações públicas." },
    { re: /l9784/i, resumo: "Regula o processo administrativo no âmbito da Administração Pública Federal." },
    { re: /l9882/i, resumo: "Regula a ação popular, a ação civil pública e o procedimento das ações de controle concentrado de constitucionalidade." },
    { re: /l12016/i, resumo: "Regula o mandado de segurança individual e coletivo contra ato de autoridade pública." },
    { re: /del2848|cod_pen/i, resumo: "Define os crimes e fixa as penas do Direito Penal brasileiro (Código Penal)." },
    { re: /del3689/i, resumo: "Estabelece normas de processo penal (Código de Processo Penal)." },
    { re: /l11340/i, resumo: "Cria mecanismos para coibir a violência doméstica e familiar contra a mulher (Lei Maria da Penha)." },
    { re: /l7210/i, resumo: "Define normas para a execução das penas e medidas alternativas (Lei de Execução Penal)." },
    { re: /l8072/i, resumo: "Define crimes hediondos, restringe benefícios e estabelece medidas de segurança específicas." },
    { re: /l12830/i, resumo: "Dispõe sobre investigação criminal conduzida pelo delegado de polícia e inquérito policial." },
    { re: /l13105/i, resumo: "Estabelece normas processuais civis (Código de Processo Civil)." },
    { re: /l13300/i, resumo: "Regula o mandado de injunção e o mandado de segurança coletivo." },
    { re: /l10406|2002\/l10406/i, resumo: "Introduz o Código Civil e consolida normas de direito privado." },
    { re: /del5452/i, resumo: "Consolida as leis do trabalho (CLT)." },
    { re: /l8212|8212cons/i, resumo: "Dispõe sobre o plano de custeio e arrecadação da Previdência Social." },
    { re: /l8078/i, resumo: "Estabelece normas de proteção e defesa do consumidor (CDC)." },
    { re: /l9514/i, resumo: "Regula a alienação fiduciária de bens imóveis e dá outras providências." },
    { re: /l8666/i, resumo: "Regula licitações e contratos administrativos (Lei de Licitações, revogada em parte pela Lei 14.133/2021)." },
    { re: /l9307/i, resumo: "Dispõe sobre a arbitragem e cria a Câmara de Arbitragem Empresarial." },
    { re: /l6858/i, resumo: "Dispõe sobre pagamento, a terceiros, de valores devidos por instituições financeiras a falecidos." },
    { re: /l9503/i, resumo: "Institui o Código de Trânsito Brasileiro (CTB)." },
    { re: /d22626/i, resumo: "Dispõe sobre juros em contratos e estabelece limites (Lei da Usura)." },
    { re: /l11343/i, resumo: "Institui o Sistema Nacional de Políticas Públicas sobre Drogas (Lei de Drogas)." },
    { re: /l10826|l10\.826/i, resumo: "Regula registro, posse e comercialização de armas de fogo e munição (Estatuto do Desarmamento)." },
    { re: /l13146/i, resumo: "Institui a Lei Brasileira de Inclusão da Pessoa com Deficiência (Estatuto da Pessoa com Deficiência)." },
    { re: /l12965/i, resumo: "Estabelece princípios, garantias, direitos e deveres para o uso da internet (Marco Civil)." },
    { re: /l13709/i, resumo: "Regula o tratamento de dados pessoais (LGPD)." },
    { re: /l14133/i, resumo: "Regula licitações e contratos administrativos (nova Lei de Licitações)." },
  ];

  function ementaOverride(url) {
    const u = url || "";
    for (const row of EMENTA_OVERRIDES) {
      if (row.re.test(u)) return row.resumo;
    }
    return "";
  }

  function isGoodEmenta(text) {
    const t = String(text || "").trim();
    if (t.length < 30) return false;
    if (/^(?:dispõem|regulament|fixado|autoriz|Revogado|caput|inciso|§|arts?\.|o\s|a\s)/i.test(t)) return false;
    if (/Redação dada|Revogado pela|\(Redação|\(Incluído/i.test(t)) return false;
    return true;
  }

  function extractEmenta(body, url) {
    const u = url || "";
    const override = ementaOverride(url);
    if (override) return override;
    const clean = window.LexFormat ? window.LexFormat.cleanRaw(body || "") : String(body || "");
    let m = clean.match(/(?:^|\n)\s*(?:EMENTA|Ementa)\s*:?\s*([^\n]{20,320}\.)/m);
    if (m) return m[1].replace(/\s+/g, " ").trim();

    m = clean.match(
      /\b((?:Dispõe(?:,?\s+com\s+alterações)?|Institui|Altera|Regula|Define|Estabelece|Cria|Autoriza|Consolida|Revoga|Introduz|Fixa|Prorroga|Suspende)[^.\n]{8,320}\.)/i
    );
    if (m && m[1].length > 28 && isGoodEmenta(m[1])) {
      return m[1].replace(/\s+/g, " ").trim();
    }

    m = clean.match(/Art\.\s*1[º°oşŞ]?\s+((?:Esta Lei|Esta lei|O\s|A\s)[^.\n]{12,240}\.)/i);
    if (m && isGoodEmenta(m[1])) return m[1].replace(/\s+/g, " ").trim();

    if (/emc\d+/i.test(u)) {
      m = clean.match(/\bAltera[^.\n]{12,240}\./i);
      if (m) return m[0].replace(/\s+/g, " ").trim();
      return "Altera dispositivos da Constituição Federal de 1988.";
    }

    return "";
  }

  function shortenEmenta(ementa, maxLen) {
    const t = String(ementa || "").replace(/\s+/g, " ").trim();
    if (!t) return "";
    const limit = maxLen || 140;
    if (t.length <= limit) return t;
    const cut = t.slice(0, limit);
    const lastSpace = cut.lastIndexOf(" ");
    return `${(lastSpace > 40 ? cut.slice(0, lastSpace) : cut).trim()}…`;
  }

  function buildLawTitle(url, body, meta) {
    if (meta?.titulo && !/\.htm$/i.test(meta.titulo)) return meta.titulo;
    const norma = parseNormaFromUrl(url, body);
    if (!norma) return meta?.titulo || (url || "").split("/").pop() || "Legislação";
    const ref = formatNormaRef(norma);
    const rule = LEI_SECAO_RULES.find((r) => r.re.test(url || ""));
    if (rule?.titulo) return rule.titulo;
    const ementa = extractEmenta(body, url);
    if (!ementa) return ref;
    let sub = ementa
      .replace(/^(?:Dispõe(?:,?\s+com\s+alterações)?(?:\s+sobre)?|Institui|Altera(?:\s+a)?|Regula|Define|Estabelece|Cria|Autoriza)\s+/i, "")
      .replace(/\.$/, "");
    return `${ref} — ${shortenEmenta(sub, 58)}`;
  }

  function normalizeLeiReferences(text) {
    if (!text) return text;
    let t = text;
    t = t.replace(
      /Lei\s+Complementar\s+(?:n[º°.]?\s*)?([\d.]+)\s*,?\s*de\s+(?:\d+\s+de\s+\w+\s+de\s+)?(\d{4})/gi,
      (_, num, year) => `Lei Complementar ${formatLeiNumber(num.replace(/\./g, ""))}/${year}`
    );
    t = t.replace(
      /Lei\s+(?:n[º°.]?\s*)?([\d.]+)\s*,?\s*de\s+\d+\s+de\s+\w+(?:\s+de\s+)?(\d{4})/gi,
      (_, num, year) => `Lei ${formatLeiNumber(num.replace(/\./g, ""))}/${year}`
    );
    t = t.replace(
      /Lei\s+(?:n[º°.]?\s*)?([\d.]+)\s*,?\s*de\s+(\d{4})/gi,
      (_, num, year) => `Lei ${formatLeiNumber(num.replace(/\./g, ""))}/${year}`
    );
    t = t.replace(/Decreto-Lei\s+n[º°.]?\s*/gi, "Decreto-Lei ");
    t = t.replace(/Decreto\s+n[º°.]?\s*/gi, "Decreto ");
    return t;
  }

  const LEI_SECAO_RULES = [
    { re: /constituicao\.htm|constituicao\/constituicao/i, secao: "Constituição e Adm.", titulo: "Constituição Federal de 1988" },
    { re: /l1521/i, secao: "Penal e Processual", titulo: "Lei 1.521/1951 — Crimes contra a economia popular" },
    { re: /l0605|\/l605(?:cons|comp|orig|_)?\.htm/i, secao: "Constituição e Adm.", titulo: "Lei 605/1949 — Imprensa" },
    { re: /l1060/i, secao: "Constituição e Adm.", titulo: "Lei 1.060/1950 — Assistência judiciária" },
    { re: /l1079/i, secao: "Constituição e Adm.", titulo: "Lei 1.079/1950 — Impeachment" },
    { re: /l1579/i, secao: "Constituição e Adm.", titulo: "Lei 1.579/1952" },
    { re: /l4729/i, secao: "Legislação Especial", titulo: "Lei 4.729/1965 — Mercado de capitais" },
    { re: /l8112|8112cons/i, secao: "Constituição e Adm.", titulo: "Lei 8.112/1990 — Regime Jurídico dos Servidores Públicos" },
    { re: /l9784/i, secao: "Constituição e Adm.", titulo: "Lei 9.784/1999 — Processo Administrativo Federal" },
    { re: /l8429/i, secao: "Constituição e Adm.", titulo: "Lei 8.429/1992 — Improbidade Administrativa" },
    { re: /l9882/i, secao: "Constituição e Adm.", titulo: "Lei 9.882/1999 — Ações constitucionais e MP" },
    { re: /l12016/i, secao: "Constituição e Adm.", titulo: "Lei 12.016/2009 — Mandado de Segurança" },
    { re: /l13300/i, secao: "Constituição e Adm.", titulo: "Lei 13.300/2016 — Lei do Mandado de Injunção" },
    { re: /del2848|decreto-lei\/del2848|cod_pen/i, secao: "Penal e Processual", titulo: "Decreto-Lei 2.848/1940 — Código Penal" },
    { re: /del3689|decreto-lei\/del3689/i, secao: "Penal e Processual", titulo: "Decreto-Lei 3.689/1941 — Código de Processo Penal" },
    { re: /l11340/i, secao: "Penal e Processual", titulo: "Lei 11.340/2006 — Lei Maria da Penha" },
    { re: /l7210/i, secao: "Penal e Processual", titulo: "Lei 7.210/1984 — Lei de Execução Penal" },
    { re: /l11343/i, secao: "Penal e Processual", titulo: "Lei 11.343/2006 — Lei de Drogas" },
    { re: /l8072/i, secao: "Penal e Processual", titulo: "Lei 8.072/1990 — Crimes Hediondos" },
    { re: /l12830/i, secao: "Penal e Processual", titulo: "Lei 12.830/2013 — Investigação Criminal" },
    { re: /l10406|2002\/l10406/i, secao: "Civil e Trabalho", titulo: "Lei 10.406/2002 — Código Civil" },
    { re: /del5452|decreto-lei\/del5452/i, secao: "Civil e Trabalho", titulo: "Decreto-Lei 5.452/1943 — CLT" },
    { re: /l8212|8212cons/i, secao: "Civil e Trabalho", titulo: "Lei 8.212/1991 — Custeio da Previdência Social" },
    { re: /l8078/i, secao: "Civil e Trabalho", titulo: "Lei 8.078/1990 — Código de Defesa do Consumidor" },
    { re: /l9514/i, secao: "Civil e Trabalho", titulo: "Lei 9.514/1997 — Alienação fiduciária" },
    { re: /l8249/i, secao: "Legislação Especial", titulo: "Lei 8.249/1991 — Nota do Tesouro Nacional (NTN)" },
    { re: /l8666/i, secao: "Legislação Especial", titulo: "Lei 8.666/1993 — Licitações e Contratos" },
    { re: /l9307/i, secao: "Legislação Especial", titulo: "Lei 9.307/1996 — Lei de Arbitragem" },
    { re: /l6858/i, secao: "Legislação Especial", titulo: "Lei 6.858/1980 — Benefícios previdenciários" },
    { re: /l9503/i, secao: "Legislação Especial", titulo: "Lei 9.503/1997 — Código de Trânsito Brasileiro" },
    { re: /l13105/i, secao: "Civil e Trabalho", titulo: "Lei 13.105/2015 — Código de Processo Civil" },
    { re: /l11221/i, secao: "Penal e Processual", titulo: "Lei 11.221/2006 — CPP (alterações)" },
    { re: /l10741|l10\.741/i, secao: "Legislação Especial", titulo: "Lei 10.741/2003 — Estatuto do Idoso" },
    { re: /l10826|l10\.826/i, secao: "Penal e Processual", titulo: "Lei 10.826/2003 — Estatuto do Desarmamento" },
    { re: /l6015/i, secao: "Legislação Especial", titulo: "Lei 6.015/1973 — Debêntures" },
    { re: /l6404/i, secao: "Legislação Especial", titulo: "Lei 6.404/1976 — Lei das S.A." },
    { re: /l8036/i, secao: "Legislação Especial", titulo: "Lei 8.036/1990 — Sistema Financeiro Nacional" },
  ];

  function shouldPreferKnownLegisTitle(current, knownTitulo) {
    if (!knownTitulo) return false;
    if (!current || /\.htm$/i.test(current) || current.length < 8 || /^Legisla/i.test(current)) return true;
    const curYear = current.match(/\/(\d{4})\b/)?.[1];
    const knownYear = knownTitulo.match(/\/(\d{4})\b/)?.[1];
    if (curYear && knownYear && curYear !== knownYear) return true;
    if (/imprensa/i.test(current) && !/imprensa/i.test(knownTitulo)) return true;
    const curRef = current.split("—")[0]?.trim();
    const knownRef = knownTitulo.split("—")[0]?.trim();
    if (curRef && knownRef && curRef === knownRef && current !== knownTitulo) return true;
    return false;
  }

  /** Título canônico: metadados curados > regras fixas > título já bom > inferência do texto. */
  function resolveLegisTitle(url, body, currentTitle) {
    const u = url || "";
    const known = lookupKnownMeta(u);
    if (known?.titulo) return known.titulo;
    for (const rule of LEI_SECAO_RULES) {
      if (rule.re.test(u) && rule.titulo) return rule.titulo;
    }
    const current = String(currentTitle || "").trim();
    if (current && !/\.htm$/i.test(current) && current.length >= 8 && !/^Legisla/i.test(current)) {
      const curYear = current.match(/\/(\d{4})\b/)?.[1];
      const inferredYear = parseNormaFromUrl(u, body)?.ano;
      if (!curYear || !inferredYear || curYear === inferredYear) return current;
    }
    return metaFromUrl(u, body)?.titulo || current || null;
  }

  function metaFromUrl(url, body) {
    const u = url || "";
    const known = lookupKnownMeta(u);
    let secao = known?.secao || "Legislação Especial";
    let ruleTitle = known?.titulo || null;
    for (const rule of LEI_SECAO_RULES) {
      if (rule.re.test(u)) {
        secao = rule.secao;
        ruleTitle = ruleTitle || rule.titulo;
        break;
      }
    }
    const norma = parseNormaFromUrl(u, body);
    if (!norma && !ruleTitle) return null;
    const ementa = extractEmenta(body, u) || known?.resumo || "";
    const titulo = ruleTitle || buildLawTitle(u, body, null);
    return {
      titulo,
      resumo: shortenEmenta(known?.resumo || ementa, 160),
      secao_lei_seca: secao,
    };
  }

  window.LexLegisMeta = {
    metaFromUrl,
    parseNormaFromUrl,
    formatNormaRef,
    formatLeiNumber,
    normalizeLeiReferences,
    extractEmenta,
    shortenEmenta,
    buildLawTitle,
    lookupKnownMeta,
    extractLegisSlug,
    legisCanonicalKey,
    loadKnownMeta,
    setKnownMetaCache,
    shouldPreferKnownLegisTitle,
    resolveLegisTitle,
    LEI_SECAO_RULES,
  };
})();
