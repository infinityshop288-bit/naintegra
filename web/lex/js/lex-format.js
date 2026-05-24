/**
 * Normalização e formatação jurídica do conteúdo bruto (markdown de crawl).
 * Remove artefatos de navegação e estrutura ementa · tese · julgado.
 */
(function () {
  const FORMAT_VERSION = 36;
  const NOISE_PATTERNS = [
    /<!--[\s\S]*?-->/g,
    /!\[[^\]]*\]\([^)]+\)/g,
    /\[[^\]]+\]\([^)]+\)/g,
    /https?:\/\/[^\s)]+/g,
    /©[^\n]+/gi,
  ];

  /** Rodapé/UI do crawl Trilhante — não aplicar em texto Planalto (ex.: CP art. 152, “conversação”). */
  const TRILHANTE_FOOTER_PATTERNS = [
    /Encontrou um erro\?[^\n]*/gi,
    /Não Estudado|Não Favoritado|Imprimir em PDF/gi,
    /bat\.bing\.com[^\n]*/gi,
    /#{1,6}\s*Reporte um Erro[\s\S]*$/gi,
    /Reporte um Erro[\s\S]*?(?=Conversação|$)/gi,
    /(?:^|\n)Conversação\d*[\s\S]*$/gi,
    /Alguma pergunta sobre Trilhante\?[\s\S]*$/gi,
    /Enviar Mensagem![\s\S]*$/gi,
    /Seu Nome|Seu Email|Sua Mensagem/gi,
  ];

  const LEGIS_BODY_START_RE =
    /(?:^|\n)\s*(?:TÍTULO\s+I\b|Art\.?\s*1(?!\d|\.)(?:[º°o]?(?:\s*[-–]|\.\s|\s+(?=[A-Za-zÁÉÍÓÚáéíóú]))))/m;

  const ADCT_SPLIT_RE =
    /\n(?=(?:Ato das Disposi[cç][õo]es Constitucionais Transit[oó]rias|DISPOSI[CÇ][ÕO]ES CONSTITUCIONAIS TRANSIT[OÓ]RIAS)\b)/i;

  /** Cabeçalho autônomo da seção ADCT (não referência dentro de artigo). */
  const CF_ADCT_SECTION_LINE_RE =
    /(?:^|\n)\s*(?:Ato das Disposi[cç][õo]es Constitucionais Transit[oó]rias|DISPOSI[CÇ][ÕO]ES CONSTITUCIONAIS TRANSIT[OÓ]RIAS)\s*(?=\n|$)/gi;

  const CF_ADCT_GLUE_HEAD_RE =
    /(?:^|[.\n])\s*((?:ATO DAS DISPOSIÇÕES CONSTITUCIONAIS TRANSITÓRIAS|Ato das Disposi[cç][õo]es Constitucionais Transit[oó]rias))\s*(?=\s*\(Vide|\n+\s*Art\.\s*1(?:[º°o]|\b)|Art\.\s*1(?:[º°o]|\b)\.)/gi;

  function isTrilhanteCrawl(text) {
    return /Trilhante|Reporte um Erro|Encontrou um erro\?|Alguma pergunta sobre Trilhante/i.test(
      text || ""
    );
  }

  const SKIP_PATH_RE =
    /\/(buscador|login|register|assine|newsletter|home|aprenda|leis)(\?|$|\/)/i;

  function normalizePlanaltoEncoding(text) {
    return String(text || "")
      .replace(/(\d)[şŞ](?=[.\s\-–])/g, "$1º")
      .replace(/\bn[şŞ](?=\s*[\d.])/gi, "nº")
      .replace(/\bn\s+[º°oşŞ.]/gi, "nº")
      .replace(/§\s*(\d+)ş/gi, "§ $1º");
  }

  function cleanRaw(text) {
    if (!text) return "";
    let t = normalizePlanaltoEncoding(text).replace(/\r/g, "").replace(/\t/g, " ");
    for (const re of NOISE_PATTERNS) t = t.replace(re, " ");
    if (isTrilhanteCrawl(t)) {
      for (const re of TRILHANTE_FOOTER_PATTERNS) t = t.replace(re, " ");
    }
    t = t.replace(/^#+\s*Norma\s*$/gim, "");
    t = t.replace(/^Fonte:\s*`[^`]+`\s*$/gim, "");
    t = t.replace(/^---+$/gm, "");
    t = t.replace(/^(Presidência|Casa Civil|Subchefia|Texto\s+compilado|Vigência|Mensagem de veto|Regulamento)[^\n]*\n/gim, "");
    t = t.replace(/<s[^>]*>[\s\S]*?<\/s>/gi, (m) => {
      const inner = m.replace(/<[^>]+>/g, " ").trim();
      return inner ? ` ~~${inner}~~ ` : " ";
    });
    t = t.replace(/<del[^>]*>[\s\S]*?<\/del>/gi, (m) => {
      const inner = m.replace(/<[^>]+>/g, " ").trim();
      return inner ? ` ~~${inner}~~ ` : " ";
    });
    t = t.replace(/<[^>]+>/g, " ");
    t = t.replace(/\(Vide(?!\s+(?:ADI|ADPF|ADC|ADIO)\b)[^\n]+\)\n/gi, "");
    t = t.replace(/\(Vigência\)\n/gi, "");
    t = t.replace(/#{1,6}\s*/g, "");
    t = t.replace(/\*\*/g, "");
    t = t.replace(/\\n/g, "\n");
    t = t.replace(/[ \t]+\n/g, "\n");
    t = t.replace(/\n{3,}/g, "\n\n");
    t = t.replace(/[ \t]{2,}/g, " ");
    return t.trim();
  }

  function escHtml(s) {
    const el = document.createElement("span");
    el.textContent = s ?? "";
    return el.innerHTML;
  }

  function pathOnly(url) {
    try {
      const u = new URL(url);
      return u.pathname.replace(/\/+$/, "") || "/";
    } catch {
      return (url || "").split("?")[0];
    }
  }

  function classifyDoc(doc) {
    const rawUrl = doc.url || doc.doc_key || "";
    if (/urn:lex:/i.test(rawUrl)) return "skip";
    const p = pathOnly(rawUrl).toLowerCase();
    const isLegis =
      doc.doc_type === "legislacao" ||
      doc.source_system === "planalto" ||
      doc.source_system === "rideel_vademecum";
    if (SKIP_PATH_RE.test(p) && !(isLegis && /\.(htm|html|php)(\?|$)/i.test(p))) return "skip";
    if (/\/tema(?:-repetitivo)?-\d+/i.test(p)) return "tema";
    if (/\/sumula-vinculante-\d+/i.test(p) && /\/sumulas\//.test(p)) return "sumula_individual";
    if (/\/sumulas\/[^/]+\/(?:sumula-\d+|stj-sumula-\d+)/i.test(p) && !/\/aprenda\//i.test(p)) return "sumula_individual";
    if (/\/sumula-\d+/i.test(p) && /\/sumulas\//.test(p) && !/\/aprenda\//i.test(p)) return "sumula_individual";
    if (/\/sumulas\/stf-vinculante\/?(\?|$)/.test(p)) return "sumulas_vinculantes";
    if (/\/sumulas\/(stf|stj|tst|tse)(\/|$|\?)/.test(p) && !/\/sumula-/i.test(p)) return "sumulas_colecao";
    if (/\/principais-julgados\/[^/]+\/[^/]+/.test(p)) return "julgado";
    if (p.endsWith("/principais-julgados") || p.includes("/todos-os-principais")) return "julgados_colecao";
    if (/\/temas-(stf|stj|tst)(\?|$)/.test(p)) return "temas_colecao";
    if (/\/jurisprudencia-em-teses/.test(p)) return "teses_colecao";
    if (p === "/" || p.split("/").filter(Boolean).length <= 1) {
      if (isLegis) return "outro";
      return "skip";
    }
    return "outro";
  }

  function friendlyTitle(doc) {
    const kind = classifyDoc(doc);
    const p = pathOnly(doc.url || "");
    const tribunal = doc.organized?.tribunal || tribunalFromPath(p);

    if (kind === "tema") {
      const repMatch = p.match(/tema-repetitivo-(\d+)/i);
      if (repMatch) return `Tema Repetitivo ${repMatch[1]} — ${tribunal}`;
      const n = p.match(/tema-(\d+)/i);
      return n ? `Tema ${n[1]} — ${tribunal}` : `Tema — ${tribunal}`;
    }
    if (kind === "sumula_individual") {
      const svMatch = p.match(/sumula-vinculante-(\d+)/i);
      if (svMatch) return `SV ${svMatch[1]} — STF`;
      const n = p.match(/sumula-(\d+)/i);
      const isVinculante = p.includes("vinculante");
      return n
        ? isVinculante
          ? `SV ${n[1]} — STF`
          : `Súmula ${n[1]} — ${tribunal}`
        : `Súmula — ${tribunal}`;
    }
    if (kind === "julgado") {
      const slug = p.split("/").pop() || "";
      const proc = slug.replace(/-/g, " ").toUpperCase();
      return `${tribunal} — ${proc}`;
    }
    if (kind === "sumulas_vinculantes") return "Súmulas Vinculantes — STF";
    if (kind === "sumulas_colecao") {
      const m = p.match(/sumulas\/(\w+)/);
      const t = (m?.[1] || tribunal).toUpperCase();
      return t === "STF" ? "Súmulas — STF" : `Súmulas — ${t}`;
    }
    if (kind === "julgados_colecao") return "Principais Julgados";
    if (kind === "temas_colecao") return `Repercussão Geral — ${tribunal}`;
    if (kind === "teses_colecao") return `Jurisprudência em Teses — ${tribunal}`;

    const law = p.match(/\/l(\d+)(?:cons|comp|orig|_)?\.htm/i);
    if (window.LexLegisMeta) {
      const resolved = window.LexLegisMeta.resolveLegisTitle?.(
        doc.url || doc.doc_key || p,
        doc.body,
        doc.title
      );
      if (resolved) return resolved;
      const meta = window.LexLegisMeta.metaFromUrl(doc.url || doc.doc_key || p, doc.body);
      if (meta?.titulo) return meta.titulo;
      const norma = window.LexLegisMeta.parseNormaFromUrl(doc.url || doc.doc_key || p, doc.body);
      if (norma?.ano) return window.LexLegisMeta.formatNormaRef(norma);
    }
    if (law) {
      const n = law[1];
      if (window.LexLegisMeta) {
        const norma = window.LexLegisMeta.parseNormaFromUrl(doc.url || doc.doc_key || p, doc.body);
        if (norma?.ano) return window.LexLegisMeta.formatNormaRef(norma);
        return `${norma?.tipo || "Lei"} ${window.LexLegisMeta.formatLeiNumber(n)}`;
      }
    }
    if (doc.source_system === "planalto" || doc.doc_type === "legislacao") {
      if (doc.title && !/\.htm$/i.test(doc.title) && doc.title.length > 8 && !/^Legisla/i.test(doc.title)) {
        return doc.title.replace(/^Lei n[º°.]?\s*/, "Lei ");
      }
      if (window.LexLegisMeta) {
        const built = window.LexLegisMeta.buildLawTitle(doc.url || doc.doc_key || p, doc.body || "", doc.meta);
        if (built && !/^Legisla/i.test(built)) return built;
      }
      return doc.title?.replace(/^Lei n[º°.]?\s*/, "Lei ") || "Legislação";
    }
    return doc.title || "Documento";
  }

  function tribunalFromPath(p) {
    const u = p.toLowerCase();
    if (u.includes("stf-vinculante") || u.includes("stf")) return "STF";
    if (u.includes("stj")) return "STJ";
    if (u.includes("tst")) return "TST";
    if (u.includes("tse")) return "TSE";
    return "STF";
  }

  function parseSumulaPage(text, url) {
    const clean = cleanRaw(text);
    const num = clean.match(/S[úu]mula\s+Vinculante\s+(\d+)/i)?.[1] || clean.match(/S[úu]mula\s+(\d+)/i)?.[1];
    const julgamento = clean.match(/Julgamento:\s*([^\n]+)/i)?.[1]?.trim();
    const publicacao = clean.match(/Publica[cç][aã]o:\s*([^\n]+)/i)?.[1]?.trim();
    const tribunal = (url || "").toLowerCase().includes("stj")
      ? "STJ"
      : (url || "").toLowerCase().includes("tst")
        ? "TST"
        : (url || "").toLowerCase().includes("tse")
          ? "TSE"
          : "STF";
    const vinc = /vinculante/i.test(url || "") || /S[úu]mula\s+Vinculante/i.test(clean);

    let enunciado = "";
    const afterDates = clean.split(/Publica[cç][aã]o:[^\n]+\n/i).pop() || clean;
    const lines = afterDates
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.length > 40 && !/^(STF|STJ|TST|TSE|Súmula|Julgamento|Publicação|Conversação|Olá)/i.test(l));
    enunciado = lines[0] || "";

    if (!enunciado) {
      const m = clean.match(/S[úu]mula(?:\s+Vinculante)?\s+\d+\s+(?:\d{2}\/\d{4}\s+)?(.{40,}?)(?:\n|$)/i);
      enunciado = m?.[1]?.trim() || "";
    }

    const rotulo = vinc ? `SV ${num}` : `Súmula ${num}`;
    return {
      id: `sumula-${num}`,
      tipo: vinc ? "sumula_vinculante" : "sumula",
      tribunal,
      numero: rotulo,
      julgamento: julgamento || publicacao,
      ementa: `${tribunal} — ${rotulo}${julgamento ? ` · ${julgamento}` : ""}`,
      tese: enunciado,
      julgado: enunciado
        ? `Enunciado ${vinc ? "vinculante " : ""}nº ${num} — ${tribunal}.${publicacao ? ` Publicação: ${publicacao}.` : ""}`
        : "",
    };
  }

  function parseTema(text) {
    const clean = cleanRaw(text);
    const num = clean.match(/Tema\s+(\d+)/i)?.[1];
    const relator = clean.match(/Relator:\s*([^\n]+)/i)?.[1]?.trim();
    const julgamento = clean.match(/Julgamento:\s*([^\n]+)/i)?.[1]?.trim();
    const tribunal = clean.match(/\b(STF|STJ|TST|TSE)\b/)?.[1] || "STF";

    const skipLine = (l) =>
      !l ||
      l.length < 20 ||
      /^Temas e Súmulas$|^Temas$|^Súmulas$|^Mais$|^Tema \d+$|^Repercussão Geral$/i.test(l) ||
      /^(STF|STJ|TST|TSE)$/i.test(l) ||
      /^Relator:|^Julgamento:/i.test(l) ||
      /^(Não Estudado|Não Favoritado|Imprimir|Reporte|Encontrou|\*|×)/i.test(l);

    const lines = clean
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    const jIdx = lines.findIndex((l) => /^Julgamento:/i.test(l));
    const contentLines = (jIdx >= 0 ? lines.slice(jIdx + 1) : lines).filter((l) => !skipLine(l));

    let ementa = contentLines[0] || "";
    let tese = contentLines[1] || "";
    let julgado = contentLines.slice(2).join("\n\n") || "";

    if (!tese && ementa.includes(". ")) {
      const sentences = ementa.split(/(?<=\.)\s+/);
      if (sentences.length >= 2) {
        ementa = sentences[0];
        tese = sentences[1];
        julgado = sentences.slice(2).join(" ");
      }
    }
    if (!julgado && tese && /^Recurso (extraordinário|repetitivo|ordinário)/i.test(tese)) {
      julgado = tese;
      tese = ementa;
    } else if (!julgado && contentLines.length === 2 && contentLines[1].length > 120) {
      julgado = contentLines[1];
      tese = contentLines[1];
    }

    return {
      id: num ? `tema-${num}` : "tema",
      tipo: "tema",
      tribunal,
      numero: num ? `Tema ${num}` : "Tema",
      relator,
      julgamento,
      ementa: ementa.trim(),
      tese: tese.trim(),
      julgado: julgado.trim(),
    };
  }

  function parseSumulaEntry(raw, tribunal) {
    const t = raw.replace(/\s+/g, " ").trim();
    const sv = t.match(/S[úu]mula\s+Vinculante\s+(\d+)\s*(?:[•·]\s*)?(\d{2}\/\d{4})?\s*(.+)/i);
    if (sv) {
      const enunciado = sv[3].trim();
      return {
        tipo: "sumula_vinculante",
        tribunal: "STF",
        numero: `SV ${sv[1]}`,
        data: sv[2] || "",
        ementa: `STF — Súmula Vinculante nº ${sv[1]}${sv[2] ? ` (${sv[2]})` : ""}`,
        tese: enunciado,
        julgado: `Enunciado de observância obrigatória (CF, art. 103-A). ${enunciado}`,
      };
    }
    const sm = t.match(
      /(?:STF|STJ|TST|TSE)\s+S[úu]mula\s+(\d+)\s+(\d{2}\/\d{4})?\s+(.+)/i
    );
    if (sm) {
      const tr = t.match(/^(STF|STJ|TST|TSE)/i)?.[1]?.toUpperCase() || tribunal;
      const enunciado = sm[3].trim();
      return {
        tipo: "sumula",
        tribunal: tr,
        numero: `Súmula ${sm[1]}`,
        data: sm[2] || "",
        ementa: `${tr} — Súmula nº ${sm[1]}${sm[2] ? ` · ${sm[2]}` : ""}`,
        tese: enunciado,
        julgado: `Enunciado sumulado pelo ${tr}.${sm[2] ? ` Publicação: ${sm[2]}.` : ""}`,
      };
    }
    return null;
  }

  function parseSumulasColecao(text, tribunal) {
    const clean = cleanRaw(text);
    const items = [];
    const re =
      /S[úu]mula\s+Vinculante\s+\d+[^[\n]{10,}|(?:STF|STJ|TST|TSE)\s+S[úu]mula\s+\d+\s+\d{2}\/\d{4}[^[\n]{10,}/gi;
    let m;
    while ((m = re.exec(clean))) {
      const item = parseSumulaEntry(m[0], tribunal);
      if (item?.ementa && item.ementa.length > 15) {
        item.id = `${item.tribunal}-${item.numero}`.replace(/\s+/g, "-").toLowerCase();
        items.push(item);
      }
    }
    return items;
  }

  function parseJulgadoEntry(block, tribunal) {
    const t = block.replace(/\s+/g, " ").trim();
    const head = t.match(
      /(STF|STJ|TST|TSE)\s+(?:Paradigma\s+)?((?:RE|REsp|AgInt|HC|MS|RMS|ADI|ADPF|ARE)[^\sⓘ]+)\s*(?:ⓘ\s*)?(\d{2}\/\d{4})?/i
    );
    if (!head) return null;
    const tr = head[1].toUpperCase();
    const proc = head[2].trim();
    const data = head[3] || "";
    let body = t.slice(head.index + head[0].length).trim();
    body = body.replace(/^(Informativo|Direito)[^.]+\.\s*/gi, "");
    const sentences = body.split(/(?<=\.)\s+/).filter((s) => s.length > 20);
    const ementa = sentences[0] || body.slice(0, 400);
    const tese = sentences[1] || "";
    const julgado = sentences.slice(2).join(" ") || (sentences.length <= 1 ? "" : sentences[sentences.length - 1]);

    return {
      id: proc.replace(/\s+/g, "-").toLowerCase(),
      tipo: "julgado",
      tribunal: tr,
      numero: proc,
      data,
      ementa: ementa.trim(),
      tese: tese.trim(),
      julgado: julgado.trim() || ementa.trim(),
    };
  }

  function parseJulgadosColecao(text) {
    const clean = cleanRaw(text);
    const items = [];
    const re =
      /(?:STF|STJ|TST|TSE)\s+(?:Paradigma\s+)?(?:RE|REsp|AgInt|HC|MS|RMS|ADI|ADPF|ARE)[^\[]{20,}/gi;
    let m;
    while ((m = re.exec(clean))) {
      const item = parseJulgadoEntry(m[0], "STF");
      if (item?.ementa && item.ementa.length > 30) items.push(item);
    }
    return items;
  }

  /** Número de artigo Planalto: 42, 999 ou 1.026 (milhar com ponto). */
  const ARTICLE_NUM = String.raw`\d{1,3}(?:\.\d{3})+|\d+`;
  const ARTICLE_HEAD_PREFIX = String.raw`Art\.?\s*`;
  /** Evita tratar referências internas ("art. 1º desta Lei") como cabeçalho de artigo. */
  const ARTICLE_HEAD_TAIL = String.raw`(?:\s*[-–]\s*[A-Z](?:\.|\s|$)|\.\s|\s+(?=[A-ZÁÉÍÓÚÂÊÔÇ])|$)`;

  function normalizePlanaltoArticleRefs(text) {
    return String(text || "").replace(
      new RegExp(`${ARTICLE_HEAD_PREFIX}(\\d{1,3}(?:\\.\\d{3})+)(?!\\d)`, "gi"),
      (_, num) => `Art. ${num.replace(/\./g, "")}`
    );
  }

  function parseArticleNumberFromHead(labelOrHead) {
    const m = String(labelOrHead || "").match(
      new RegExp(`^${ARTICLE_HEAD_PREFIX}(${ARTICLE_NUM})(?!\\d)`, "i")
    );
    return m ? m[1].replace(/\./g, "") : null;
  }

  const ARTICLE_HEAD_LINE = new RegExp(
    `^${ARTICLE_HEAD_PREFIX}(${ARTICLE_NUM})(?!\\d)[º°o]?${ARTICLE_HEAD_TAIL}`
  );

  const ARTICLE_EPIGRAPH_LINE = /^[-–]\s*(.+?)\s*[-–]$/;

  function isArticleEpigraphLine(line) {
    const t = String(line || "").trim();
    const m = t.match(ARTICLE_EPIGRAPH_LINE);
    if (!m) return false;
    const inner = m[1].replace(/\s+/g, " ").trim();
    if (inner.length < 3 || inner.length > 120) return false;
    if (/^[IVXLC]{1,7}$/.test(inner)) return false;
    if (/^[a-z]\)/.test(inner)) return false;
    return true;
  }

  function parseArticleEpigraph(line) {
    const t = String(line || "").trim();
    if (!isArticleEpigraphLine(t)) return null;
    return t.replace(/^[-–]\s*/, "").replace(/\s*[-–]$/, "").replace(/\s+/g, " ").trim();
  }

  function appendEpigraphToLabel(label, epigraph) {
    if (!epigraph) return label;
    const base = String(label || "").trim();
    if (base.toLowerCase().includes(epigraph.toLowerCase())) return base;
    return `${base} — ${epigraph}`;
  }

  function extractLeadingEpigraph(text) {
    let rest = String(text || "").trim();
    let epigraph = null;
    const lines = rest.split(/\n+/);
    while (lines.length && isArticleEpigraphLine(lines[0])) {
      epigraph = parseArticleEpigraph(lines.shift());
      rest = lines.join("\n").trim();
    }
    return { text: rest, epigraph };
  }

  function extractTrailingEpigraph(text) {
    const t = String(text || "").trim();
    const m = t.match(/\n\s*([-–][^\n]+[-–])\s*$/);
    if (!m || !isArticleEpigraphLine(m[1])) return { text: t, epigraph: null };
    return {
      text: t.slice(0, m.index).trim(),
      epigraph: parseArticleEpigraph(m[1]),
    };
  }

  function ensureArticleEpigraphBreaks(text) {
    return String(text || "").replace(
      /(\S)\s+([-–]\s+[A-ZÁÉÍÓÚÀ-Ü][^.\n]{2,100}?\s*[-–])\s+(?=Art\.?\s*(?:\d{1,3}(?:\.\d{3})+|\d+)(?!\d))/gi,
      "$1\n\n$2\n\n"
    );
  }

  function relocateArticleEpigraphs(blocks) {
    let pending = null;
    const out = [];
    for (const block of blocks) {
      const b = { ...block };
      if (pending && (b.type === "artigo" || b.type === "capitulo" || b.type === "titulo")) {
        const head = b.type === "artigo" ? b.label : String(b.label || b.text || "").split("\n")[0].trim();
        const merged = appendEpigraphToLabel(head, pending);
        if (b.type === "artigo") b.label = merged;
        else if (b.label) b.label = merged;
        pending = null;
      }
      if (b.text) {
        const trailing = extractTrailingEpigraph(b.text);
        b.text = trailing.text;
        if (trailing.epigraph) pending = trailing.epigraph;
      }
      out.push(b);
    }
    return out;
  }

  function normalizeArticleKey(labelOrHead) {
    const num = parseArticleNumberFromHead(labelOrHead);
    if (!num) return null;
    const al = String(labelOrHead || "").match(/^Art\.\s*[\d.]+(?:[º°o])?\s*[-–]\s*([A-Z])(?:\.|\s|$)/i);
    return num + (al ? `-${al[1].toUpperCase()}` : "");
  }

  function articleRevisionScore(segment, order) {
    let score = order;
    const bodyStart = segment.replace(/^Art\.[^\n]+\n?/m, "").trim().slice(0, 24);
    if (/^ão há|^ã|^o há crime|Consti tui/i.test(bodyStart)) score -= 3000;
    const years = segment.match(
      /(?:Reda[cç][ãa]o|Inclus[aã]o) dada pela Lei\s+n[º°.]?\s*[\d./]+\s*,?\s*de\s+(\d{4})/gi
    );
    if (years) {
      for (const y of years) {
        const yr = y.match(/de\s+(\d{4})/i);
        if (yr) score += parseInt(yr[1], 10) * 10;
      }
      score += 500;
    }
    if (/Consti\s*\n\s*tui|Consti\s+tui/i.test(segment)) score -= 300;
    if (/\(Revogad[oa]\b/i.test(segment)) score -= 5000;
    if (/dolosa ou culposa/i.test(segment) && !/efetiva e comprovadamente/i.test(segment)) {
      score -= 80;
    }
    return score;
  }

  function findArticleHeads(text) {
    const heads = [];
    const re = new RegExp(
      `^${ARTICLE_HEAD_PREFIX}(${ARTICLE_NUM})(?!\\d)[º°o]?${ARTICLE_HEAD_TAIL}`,
      "gm"
    );
    let m;
    while ((m = re.exec(text)) !== null) {
      const head = m[0];
      const num = m[1].replace(/\./g, "");
      const al = head.match(/[-–]\s*([A-Z])(?:\.|\s|$)/);
      heads.push({
        index: m.index,
        key: num + (al ? `-${al[1].toUpperCase()}` : ""),
      });
    }
    return heads;
  }

  /** Remove versões antigas repetidas; mantém o trecho com alteração mais recente. */
  function stripSupersededArticleSections(text) {
    const heads = findArticleHeads(text);
    if (heads.length < 2) return text;

    const segments = heads.map((h, i) => ({
      ...h,
      end: i + 1 < heads.length ? heads[i + 1].index : text.length,
      order: i,
    }));

    const byKey = new Map();
    for (const seg of segments) {
      if (!byKey.has(seg.key)) byKey.set(seg.key, []);
      byKey.get(seg.key).push(seg);
    }

    const removeRanges = [];
    for (const list of byKey.values()) {
      if (list.length < 2) continue;
      const scored = list.map((seg) => ({
        ...seg,
        score: articleRevisionScore(text.slice(seg.index, seg.end), seg.order),
      }));
      scored.sort((a, b) => a.score - b.score || a.order - b.order);
      const keep = scored[scored.length - 1];
      for (const seg of list) {
        if (seg.index !== keep.index) {
          removeRanges.push({ start: seg.index, end: seg.end });
        }
      }
    }

    removeRanges.sort((a, b) => b.start - a.start);
    let out = text;
    for (const r of removeRanges) {
      out = out.slice(0, r.start) + out.slice(r.end);
    }
    return out.replace(/\n{3,}/g, "\n\n");
  }

  const SYLLABLE_NO_MERGE = new Set([
    "de", "da", "do", "dos", "das", "em", "no", "na", "nos", "nas", "ao", "aos",
    "ou", "se", "um", "uma", "uns", "umas", "e", "a", "o", "as", "os", "que",
    "por", "para", "com", "sem", "sobre", "entre", "pelo", "pela", "pelos", "pelas",
    "como", "contra", "ante", "após", "desde", "até", "seu", "sua", "seus", "suas",
    "art", "arts",
  ]);

  const REVOGADO_TAIL_RE = /\(\s*Revogad[oa](?:\s+(?:pela|pelo|por)\s+[^)]*)?\)\.?\s*$/i;
  const REVOGADO_ONLY_RE = /^\(?\s*Revogad[oa](?:\s+(?:pela|pelo|por)\s+[^)]*)?\)?\.?\s*$/i;

  function hasRevokedTail(text) {
    const stripped = stripLegisRevisionNotes(String(text || "").trim());
    if (!stripped) return false;
    if (REVOGADO_ONLY_RE.test(stripped)) return true;
    if (REVOGADO_TAIL_RE.test(stripped)) return true;
    return false;
  }

  function stripLegisRevisionNotes(text) {
    return String(text || "")
      .replace(
        /\s*\((?:Reda[cç][ãa]o dada|Inclus[aã]o|Inclu[ií]do|Altera[cç][ãa]o dada|Alterado|Produção de efeito)[^)]*\)\s*/gi,
        " "
      )
      .replace(/\s*\(Vide(?!\s+(?:ADI|ADPF|ADC|ADIO)\b)[^)]*\)\s*/gi, " ")
      .replace(/[ \t]{2,}/g, " ")
      .trim();
  }

  function isRevogatoryClause(text) {
    return /^Ficam revogad|^Revogam-se|^Derrogam-se|^Ficam rescindidas/i.test(
      String(text || "").trim()
    );
  }

  function isArticleWhollyRevoked(text) {
    const t = String(text || "").trim();
    if (!t || isRevogatoryClause(t)) return false;
    const head = stripLegisRevisionNotes(t.split(/\n\n+/)[0] || t);
    if (/^Revogad[oa]\s+(?:pela|pelo|por)\s+/i.test(head)) return true;
    if (hasRevokedTail(t) && !/(?:^|\n\n)\s*§\s*\d/i.test(t)) return true;
    return false;
  }

  /** Remove incisos/alíneas com (Revogado) após o texto do dispositivo. */
  function stripRevokedListItems(text) {
    return String(text || "")
      .replace(
        /(?:^|\n|[;:]\s*)([IVXLC]{1,7})\s*[-–]\s+[^\n]*?\(\s*[Rr]evogad[oa][^)]*\)\s*[;.]?\s*/gm,
        (m) => (m.startsWith("\n") ? "\n" : " ")
      )
      .replace(
        /(?:^|\n|[;:]\s*)([a-z](?:[-–][a-z])?\))\s+[^\n]*?\(\s*[Rr]evogad[oa][^)]*\)\s*[;.]?\s*/gm,
        (m) => (m.startsWith("\n") ? "\n" : " ")
      )
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  /** @deprecated alias */
  function stripRevokedIncisos(text) {
    return stripRevokedListItems(text);
  }

  function splitInlineStructuralUnits(text) {
    return String(text || "")
      .replace(/([.;)]\s*)(§\s*\d+[º°oşŞ]?(?:-[A-Z0-9]+)?[.\s])/g, "$1\n\n$2")
      .replace(/([.;)]\s*)(Par[aá]grafo\s+[uú]nico[.\s])/gi, "$1\n\n$2");
  }

  function ensureStructuralBreaks(text) {
    return String(text || "").replace(/\n(§\s*\d+[º°o]?(?:-[A-Z0-9]+)?[.\s])/g, "\n\n$1");
  }

  function isRevokedProvision(chunk) {
    const raw = String(chunk || "").trim();
    if (!raw) return true;

    const labelBody = raw.match(
      /^(§\s*\d+[º°oşŞ]?(?:-[A-Z0-9]+)?|Par[aá]grafo\s+[uú]nico\.?)\s*(.*)/is
    );
    const body = (labelBody ? labelBody[2] : raw).trim();
    const withoutNotes = stripLegisRevisionNotes(body);

    if (!withoutNotes) return true;
    if (REVOGADO_ONLY_RE.test(withoutNotes)) return true;
    if (/^Revogad[oa]\s+(?:pela|pelo|por)\s+(?:Lei|Decreto|Decreto-Lei|Medida\sProvisória|MP|Portaria)/i.test(withoutNotes)) {
      return true;
    }
    if (/^(?:§\s*\d+[º°oşŞ]?(?:-[A-Z0-9]+)?|Par[aá]grafo\s+[uú]nico\.?)\s*\(?Revogad[oa]/i.test(raw)) {
      return true;
    }
    if (hasRevokedTail(body)) return true;
    if (hasRevokedTail(withoutNotes)) return true;

    return false;
  }

  function pruneRevokedProvisions(text) {
    const chunks = String(text || "")
      .split(/\n\n+/)
      .map((c) => c.trim())
      .filter(Boolean)
      .map((chunk) => stripRevokedListItems(chunk))
      .filter((chunk) => chunk.trim())
      .filter((chunk) => !isRevokedProvision(chunk));
    return chunks.join("\n\n").trim();
  }

  const ACAO_CONSTITUCIONAL_RE =
    /\(\s*Vide\s+(ADI|ADPF|ADC|ADIO)\b(?:\s*(?:n|N)\s*[º°oşŞ.]?\s*)?[-\s]*\d[\d.]*\s*\)|\b(ADI|ADPF|ADC|ADIO)\b(?:\s*(?:n|N)\s*[º°oşŞ.]?\s*)?[-\s]*\d[\d.]*/gi;

  const REVISAO_NOTA_RE =
    /\((?:Reda[cç][ãa]o dada|Inclus[aã]o|Inclu[ií]do|Altera[cç][ãa]o dada|Alterado|Produção de efeito)[^)]*\)/gi;

  function formatLeiHtml(text) {
    const plain = normalizePlanaltoEncoding(String(text || ""));
    if (!plain) return "";
    const parts = [];
    let last = 0;
    const re = /~~([^~]+?)~~/g;
    let m;
    while ((m = re.exec(plain)) !== null) {
      if (m.index > last) {
        parts.push(formatLeiPlainSegment(plain.slice(last, m.index)));
      }
      parts.push(`<span class="lei-revogado">${escHtml(m[1])}</span>`);
      last = m.index + m[0].length;
    }
    if (last < plain.length) {
      parts.push(formatLeiPlainSegment(plain.slice(last)));
    }
    return parts.join("");
  }

  function formatLeiPlainSegment(segment) {
    if (!segment) return "";
    let html = escHtml(segment);
    html = html.replace(REVISAO_NOTA_RE, (match) => `<span class="lei-nota-revisao">${match}</span>`);
    html = html.replace(ACAO_CONSTITUCIONAL_RE, (match) => `<mark class="lei-acao-const">${match}</mark>`);
    return html;
  }

  /** Planalto HTML: ordinal (º) ou número do artigo quebrados em linhas (Art. 1\\no, Art.\\n20). */
  function normalizePlanaltoDegrees(text) {
    return String(text || "")
      .replace(/Art\.?\s*(\d{1,3}(?:\.\d{3})+|\d+)\s*°/gi, (_, n) => `Art. ${n.replace(/\./g, "")}º`)
      .replace(/§\s*(\d+)\s*°/gi, (_, n) => `§ ${n}º`);
  }

  function classifyPlanaltoBlock(oneLine, rawBlock) {
    const b = oneLine.trim();
    if (!b) return "empty";
    if (/^CÓDIGO PENAL$/i.test(b)) return "skip";
    if (/^Parte\s+(Geral|Especial)/i.test(b)) return "parte";
    if (/^TÍTULO\s+[IVXLC\d]+/i.test(b)) return "titulo";
    if (/^CAPÍTULO\s+[IVXLC\d]+/i.test(b)) return "capitulo";
    if (/^SEÇÃO\s+[IVXLC\d]+/i.test(b)) return "secao";
    if (/^Art\.?\s*\d/i.test(b)) return "artigo";
    if (/^(§\s*\d|Par[aá]grafo\s+[uú]nico)/i.test(b)) return "paragrafo";
    if (/^[IVXLC]{1,7}\s*[-–]/.test(b)) return "inciso";
    if (/^[a-z]\)/.test(b)) return "alinea";
    if (/^(Da|Do|Dos|Das|De)\s+/i.test(b) && b.length <= 90) return "capitulo_label";
    if (b.length <= 90 && /^[A-ZÁÉÍÓÚÀ-Ü]/.test(b) && !/^(Art\.|§|Par[aá]grafo)/i.test(b)) {
      const words = b.split(/\s+/).length;
      if (words <= 12 && !/\.\s+[A-ZÁÉÍÓÚ]/.test(b)) return "epigraph";
    }
    if (rawBlock && /^(§\s*\d|Par[aá]grafo)/im.test(rawBlock.trim())) return "paragrafo";
    return "text";
  }

  function emitPlanaltoBlock(raw) {
    let block = String(raw || "").replace(/\r/g, "").trim();
    if (!block) return "";
    block = normalizePlanaltoDegrees(block);
    const oneLine = block.replace(/\s+/g, " ").trim();
    const kind = classifyPlanaltoBlock(oneLine, block);
    switch (kind) {
      case "skip":
      case "empty":
        return "";
      case "parte":
        return `\n\n${oneLine.toUpperCase()}\n\n`;
      case "titulo":
      case "capitulo":
      case "secao":
        return `\n\n${oneLine}\n\n`;
      case "capitulo_label":
        return `\n\nCAPÍTULO — ${oneLine}\n\n`;
      case "epigraph":
        return `\n\n- ${oneLine} -\n\n`;
      case "artigo":
        return `\n\n${block.trim()}\n\n`;
      case "paragrafo":
      case "inciso":
      case "alinea":
      case "text":
      default:
        return `${block.trim()}\n\n`;
    }
  }

  /** Converte blocos ~~…~~ do crawl Planalto em texto legislativo estruturado. */
  function normalizePlanaltoBlockMarkers(text) {
    const t = String(text || "");
    if (!/~~/.test(t)) return t;
    const matches = [...t.matchAll(/~~\s*([\s\S]*?)\s*~~/g)];
    if (matches.length < 8) return t;
    let outside = t;
    for (const m of matches) outside = outside.replace(m[0], "\n");
    const artOutside = (outside.match(/Art\.?\s*\d/gi) || []).length;
    if (artOutside >= 10) {
      return t
        .replace(/~~\s*([\s\S]*?)\s*~~/g, (_, inner) => {
          const s = String(inner || "").replace(/\s+/g, " ").trim();
          return s ? ` ~~${s}~~ ` : " ";
        })
        .replace(/\s{2,}/g, " ")
        .replace(/ \n/g, "\n");
    }
    return matches
      .map((m) => emitPlanaltoBlock(m[1]))
      .join("")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function normalizePlanaltoOrdinals(text) {
    let t = String(text || "");
    t = t.replace(
      /(^|[\n\r]|[^\S\n\r])(Art\.?\s*(\d{1,3}(?:\.\d{3})+|\d+)(?!\d))\s*[\n\r]+\s*o\b/gim,
      (_, bol, _full, num) => `${bol}Art. ${num.replace(/\./g, "")}º`
    );
    t = t.replace(
      /(^|[\n\r]|[^\S\n\r])(§\s*(\d+)(?!\d))\s*[\n\r]+\s*o\b/gim,
      (_, bol, _full, num) => `${bol}§ ${num}º`
    );
    t = t.replace(
      /(^|[\n\r])Art\.?\s*[\n\r]+\s*(\d{1,3}(?:\.\d{3})+|\d+)(?!\d)\b/gim,
      (_, bol, num) => `${bol}Art. ${num.replace(/\./g, "")}`
    );
    t = t.replace(
      /Art\.?\s*(\d{1,3}(?:\.\d{3})+|\d+)(?!\d)\s+o\b/gi,
      (_, num) => `Art. ${num.replace(/\./g, "")}º`
    );
    return t;
  }

  /** Normaliza quebras do crawl: linha curta = sílaba; demais = espaço. */
  function repairLegisText(text) {
    let t = normalizePlanaltoEncoding(text).replace(/\r/g, "").replace(/Consti\s*\n+\s*tui/gi, "Constitui");
    t = normalizePlanaltoOrdinals(t);

    t = t.replace(/(^|\n)([A-Za-zÁÉÍÓÚáéíóúÃÕÇãõç]{1,4})\s*\n+\s*([a-záéíóúãõç])/gm, (full, bol, head, tail) => {
      if (SYLLABLE_NO_MERGE.has(head.toLowerCase())) return `${bol}${head} ${tail}`;
      return `${bol}${head}${tail}`;
    });

    t = t.replace(/\n+\s*(§\s*\d+[º°o]?(?:-[A-Z0-9]+)?)\s+(?=[A-ZÁÉÍÓÚ])/g, "\n\n$1 ");
    t = t.replace(/\n+\s*(Par[aá]grafo\s+[uú]nico[.\s])/gi, "\n\n$1");

    return t
      .replace(
        /\n+(?!\s*(?:§\s*\d|Art\.?\s*(?:\d{1,3}(?:\.\d{3})+|\d+)(?!\d)|Par[aá]grafo\s+[uú]nico|TÍTULO|CAPÍTULO|SEÇÃO|Subseção|[IVXLC]{1,7}\s*[-–(]))/gi,
        " "
      )
      .replace(/[ \t]{2,}/g, " ");
  }

  function ensureLegisStructureBreaks(text) {
    const artHead = new RegExp(
      `${ARTICLE_HEAD_PREFIX}(?:${ARTICLE_NUM})(?!\\d)[º°o]?(?:\\s*[-–]\\s*[A-Z])?[.\\s-]`
    );
    return ensureArticleEpigraphBreaks(String(text || ""))
      .replace(
        new RegExp(
          `([^\\n])\\s+(?=(?:${ARTICLE_HEAD_PREFIX}(?:${ARTICLE_NUM})(?!\\d)[º°o]?${ARTICLE_HEAD_TAIL}|TÍTULO\\s|CAPÍTULO\\s|SEÇÃO\\s|Subseção\\s|Ato das Disposi[cç][õo]es Constitucionais Transit[oó]rias|DISPOSI[CÇ][ÕO]ES CONSTITUCIONAIS TRANSIT[OÓ]RIAS))`,
          "g"
        ),
        "$1\n\n"
      )
      .replace(/\n{3,}/g, "\n\n");
  }

  function isConstituicaoUrl(doc) {
    return /constituicao\/constituicao/i.test(doc?.url || doc?.doc_key || "");
  }

  function findLegisBodyStart(clean, doc) {
    if (isConstituicaoUrl(doc)) {
      const textoCompilado = clean.search(/(?:^|\n)\s*Texto compilado\b/mi);
      if (textoCompilado >= 0) return textoCompilado;
    }
    const tituloI = clean.search(/(?:^|\n)\s*TÍTULO\s+I\b/mi);
    if (tituloI >= 0) return tituloI;
    const m = clean.match(LEGIS_BODY_START_RE);
    return m ? m.index : -1;
  }

  function normalizeCfAdctSectionHeader(body) {
    return String(body || "").replace(
      new RegExp(CF_ADCT_SECTION_LINE_RE.source, CF_ADCT_SECTION_LINE_RE.flags),
      (match) => {
        const line = match.replace(/^\n+/, "").trim();
        if (!line || /^Art\./i.test(line)) return match;
        return `\n\n${line}\n\n`;
      }
    );
  }

  /** Separa cabeçalho ADCT colado ao fim do último artigo da CF (crawl Planalto). */
  function isolateCfAdctSectionHeader(body) {
    return String(body || "")
      .replace(
        /([.;])\s*(Ato das Disposi[cç][õo]es Constitucionais Transit[oó]rias|DISPOSI[CÇ][ÕO]ES CONSTITUCIONAIS TRANSIT[OÓ]RIAS)\s*(?=\s*\(Vide|\n+\s*Art\.\s*1(?:[º°o]|\b)|Art\.\s*1(?:[º°o]|\b)\.|\n|Art\.|$)/gi,
        "$1\n\n$2\n\n"
      )
      .replace(
        /\s+(Ato das Disposi[cç][õo]es Constitucionais Transit[oó]rias|DISPOSI[CÇ][ÕO]ES CONSTITUCIONAIS TRANSIT[OÓ]RIAS)\s+(?=Art\.)/gi,
        "\n\n$1\n\n"
      );
  }

  function isInlineCfAdctReference(text, index) {
    const before = String(text || "").slice(Math.max(0, index - 24), index);
    return /(?:\bdo|\bde|\bno|\bna|\bpelo|\bpela|\bdeste|\bdessa|\bdessas|\bdesta)\s*$/i.test(before);
  }

  function findCfAdctSplitIndex(body) {
    const text = String(body || "");
    const candidates = [];

    const lineRe = new RegExp(CF_ADCT_SECTION_LINE_RE.source, CF_ADCT_SECTION_LINE_RE.flags);
    let m;
    while ((m = lineRe.exec(text)) !== null) {
      const start = m.index + (m[0].startsWith("\n") ? 1 : 0);
      candidates.push(start);
    }

    const gluedRe = new RegExp(CF_ADCT_GLUE_HEAD_RE.source, CF_ADCT_GLUE_HEAD_RE.flags);
    while ((m = gluedRe.exec(text)) !== null) {
      const start = m.index + m[0].indexOf(m[1]);
      candidates.push(start);
    }

    const filtered = [...new Set(candidates)].filter((index) => !isInlineCfAdctReference(text, index));
    if (!filtered.length) return -1;

    const after200 = text.search(/\nArt\.\s*200(?:[º°o]|\b)/i);
    const minPos = after200 >= 0 ? after200 : Math.floor(text.length * 0.55);
    const late = filtered.filter((index) => index >= minPos);
    if (late.length) return late[late.length - 1];
    return filtered[filtered.length - 1];
  }

  function splitLegisAdct(body, doc) {
    if (!isConstituicaoUrl(doc)) return { main: body, adct: "" };
    let idx = findCfAdctSplitIndex(body);
    if (idx < 0) return { main: body, adct: "" };

    // Evita cortar cedo demais quando há citação ao ADCT no meio da CF.
    if (body.length > 8000 && idx < body.length * 0.45) {
      const after200 = body.search(/\nArt\.\s*200(?:[º°o]|\b)/i);
      if (after200 >= 0) {
        const late = findCfAdctSplitIndex(body.slice(after200));
        if (late >= 0) idx = after200 + late;
      }
    }

    return { main: body.slice(0, idx).trim(), adct: body.slice(idx).trim() };
  }

  /** Separa palavras coladas por chunks ou artefatos do crawl. */
  function splitStuckWords(text) {
    let t = text;
    const gluedSecond = [
      "público", "pública", "públicos", "públicas", "privado", "privada",
      "dolosamente", "culposamente", "administrativa", "administrativo",
      "administrativos", "constitucionais", "jurídica", "jurídico",
      "dolosa", "doloso", "efetivamente", "comprovadamente",
    ];
    for (const w of gluedSecond.sort((a, b) => b.length - a.length)) {
      t = t.replace(
        new RegExp(`([a-záéíóúãõç]{3,})(${w})(?=\\s|[.,;:)\\]\\-]|$)`, "gi"),
        "$1 $2"
      );
    }
    const gluedAfter = [
      "nos", "nas", "num", "numa", "pelo", "pela", "pelos", "pelas", "que", "por",
      "como", "para", "sem", "sobre", "entre", "contra", "mediante", "conforme",
      "durante", "desde",
    ];
    for (const w of gluedAfter.sort((a, b) => b.length - a.length)) {
      t = t.replace(
        new RegExp(`([a-záéíóúãõç]{3,})(${w})(?=\\s|[.,;:)\\]\\-]|$)`, "gi"),
        "$1 $2"
      );
    }
    t = t.replace(/([a-záéíóúãõç])([A-ZÁÉÍÓÚÃÕÇ])/g, "$1 $2");
    return t.replace(/[ \t]{2,}/g, " ");
  }

  function isParagraphReference(chunk) {
    const trimmed = String(chunk || "").trim();
    if (/^(§\s*\d+[º°o]?(?:-[A-Z0-9]+)?|Par[aá]grafo\s+[uú]nico)/i.test(trimmed)) {
      return false;
    }
    return /\b(?:do|da|dos|das|no|na|nos|nas|pelo|pela|conforme|previsto\s+(?:no|na)|caput\s+(?:do|deste))\s+§/i.test(
      trimmed.slice(0, 80)
    );
  }

  function isStructuralParagraph(chunk) {
    return /^(§\s*\d+[º°o]?(?:-[A-Z0-9]+)?|Par[aá]grafo\s+[uú]nico)/i.test(String(chunk || "").trim());
  }

  function fixCrawlPunctuation(text) {
    return text
      .replace(/\b((?:nesta|desta|esta)\s+Lei)\s+(os|as)\b/gi, "$1, $2")
      .replace(/\badministração\s+pública\s+(convênio|contrato)\b/gi, "administração pública, $1");
  }

  function markArticleParagraphs(t) {
    let out = t.replace(/\s*\n+\s*(Par[aá]grafo\s+[uú]nico[.\s])/gi, "\n\n$1");
    out = out.replace(/([.;)]\s*)(Par[aá]grafo\s+[uú]nico[.\s])/gi, "$1\n\n$2");

    const markStructuralSection = (match, beforeChar, para, offset, str) => {
      const ctx = str.slice(Math.max(0, offset - 55), offset);
      if (/\b(?:do|da|dos|das|no|na|nos|nas|pelo|pela|conforme|previsto\s+no|caput\s+do|deste)\s*$/i.test(ctx)) {
        return `${beforeChar} ${para} `;
      }
      return `${beforeChar}\n\n${para} `;
    };

    out = out.replace(
      /(\S)\s+(§\s*\d+[º°o]?(?:-[A-Z0-9]+)?)\s+(?=[A-ZÁÉÍÓÚ])/g,
      markStructuralSection
    );
    out = out.replace(/\s*\n+\s*(§\s*\d+[º°o]?(?:-[A-Z0-9]+)?)\s+(?=[A-ZÁÉÍÓÚ])/g, (match, para, offset, str) => {
      const ctx = str.slice(Math.max(0, offset - 55), offset);
      if (/\b(?:do|da|dos|das|no|na|nos|nas|pelo|pela|conforme|previsto\s+no|caput\s+do|deste)\s*$/i.test(ctx)) {
        return match.replace(/^\s*\n+\s*/, " ");
      }
      return match.replace(/^\s*\n+\s*/, "\n\n");
    });
    return out;
  }

  function formatArtigoBody(text, label) {
    let t = repairLegisText(text);
    if (label) {
      const esc = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      t = t.replace(new RegExp(`^${esc}\\.?\\s*`), "");
    }
    t = t.replace(/^[-–]\s*/, "");
    t = splitStuckWords(t);
    t = fixCrawlPunctuation(t);
    t = markArticleParagraphs(t);
    t = splitInlineStructuralUnits(t);
    t = ensureStructuralBreaks(t);
    t = t.replace(/([.;:])\s+([IVXLC]{1,7}\s*[-–(])/g, "$1\n$2");
    t = stripRevokedListItems(t);
    t = t.replace(/[ \t]{2,}/g, " ");
    if (window.LexLegisMeta) t = window.LexLegisMeta.normalizeLeiReferences(t);
    t = pruneRevokedProvisions(t);
    if (!t.trim()) {
      let raw = repairLegisText(text);
      if (label) {
        const escLabel = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        raw = raw.replace(new RegExp(`^${escLabel}\\.?\\s*`), "");
      }
      raw = raw.replace(/^[-–]\s*/, "");
      raw = splitStuckWords(fixCrawlPunctuation(markArticleParagraphs(raw)));
      if (window.LexLegisMeta) raw = window.LexLegisMeta.normalizeLeiReferences(raw);
      t = raw.trim();
    }
    return t.trim();
  }

  function mergeParagraphsIntoArticles(blocks) {
    const out = [];
    let pendingPara = null;

    for (const block of blocks) {
      if (block.type === "paragrafo") {
        const prev = out[out.length - 1];
        if (prev?.type === "artigo") {
          attachParagraph(prev, block);
          continue;
        }
        pendingPara = block;
        continue;
      }
      if (pendingPara && block.type === "artigo") {
        attachParagraph(block, pendingPara, true);
        pendingPara = null;
      }
      out.push(block);
    }
    return out;
  }

  function attachParagraph(artigo, para, prepend) {
    if (!artigo.paragraphs) artigo.paragraphs = [];
    const plabel = (para.label || "§").trim();
    const entry = { label: plabel, text: para.text };
    if (prepend) {
      artigo.paragraphs.unshift(entry);
      artigo.text = `${plabel} ${para.text}\n\n${artigo.text || ""}`.trim();
    } else {
      artigo.paragraphs.push(entry);
      artigo.text = `${artigo.text || ""}\n\n${plabel} ${para.text}`.trim();
    }
  }

  function renderArtigoContent(text) {
    const chunks = String(text || "")
      .split(/\n\n+/)
      .map((c) => c.trim())
      .filter(Boolean)
      .filter((c) => !isRevokedProvision(c));
    if (!chunks.length) {
      return "";
    }

    return chunks
      .map((chunk, i) => {
        if (i > 0 && isStructuralParagraph(chunk)) {
          const paraMatch = chunk.match(
            /^(§\s*\d+[º°o]?(?:-[A-Z0-9]+)?|Par[aá]grafo\s+[uú]nico\.?)\s*(.*)/is
          );
          if (paraMatch) {
            const plabel = paraMatch[1].trim();
            const body = paraMatch[2].trim();
            return `<p class="lei-paragrafo"><span class="lei-p-label">${escHtml(plabel)}</span>${body ? ` <span class="lei-p-text lei-text article-text">${formatLeiHtml(body)}</span>` : ""}</p>`;
          }
        }
        return `<p class="lei-caput lei-text article-text">${formatLeiHtml(chunk)}</p>`;
      })
      .join("");
  }

  function dedupeArticleBlocks(blocks, { adctSection = false } = {}) {
    const out = [];
    const indexByKey = new Map();

    blocks.forEach((block, order) => {
      if (block.type !== "artigo") {
        out.push(block);
        return;
      }
      const base = normalizeArticleKey(block.label);
      const key = base ? (adctSection ? `adct:${base}` : base) : null;
      if (!key) {
        out.push(block);
        return;
      }
      const score = articleRevisionScore(block.text, order);
      const prev = indexByKey.get(key);
      if (!prev) {
        indexByKey.set(key, { score, outIdx: out.length });
        out.push(block);
        return;
      }
      if (score >= prev.score) {
        out[prev.outIdx] = block;
        indexByKey.set(key, { score, outIdx: prev.outIdx });
      }
    });
    return out;
  }

  const ADCT_HEAD_RE =
    /^(?:Ato das Disposi[cç][õo]es Constitucionais Transit[oó]rias|ADCT|DISPOSI[CÇ][ÕO]ES CONSTITUCIONAIS TRANSIT[OÓ]RIAS)/i;

  function parseLegislacao(text, doc) {
    const cleanMeta = normalizePlanaltoBlockMarkers(cleanRaw(text));
    const clean = normalizePlanaltoArticleRefs(repairLegisText(cleanMeta));
    const blocks = [];
    let epigrafe = "";
    let ementa = "";

    if (window.LexLegisMeta && doc) {
      const norma = window.LexLegisMeta.parseNormaFromUrl(doc.url || doc.doc_key || "", clean);
      if (norma?.ano) epigrafe = window.LexLegisMeta.formatNormaRef(norma);
    }
    if (!epigrafe) {
      const leiMatch = clean.match(/LEI\s+N[º°\.o]?\s*([\d.]+)[,\s]+DE\s+[^\n]+DE\s+(\d{4})/i);
      if (leiMatch && window.LexLegisMeta) {
        epigrafe = `Lei ${window.LexLegisMeta.formatLeiNumber(leiMatch[1].replace(/\./g, ""))}/${leiMatch[2]}`;
      }
    }

    if (window.LexLegisMeta && doc) {
      const extracted = window.LexLegisMeta.extractEmenta(clean, doc.url || doc.doc_key || "");
      if (extracted) ementa = extracted;
    }
    if (!ementa) {
      const ementaMatch = clean.match(
        /(?:Dispõe|Institui|Altera|Regula|Define)[^\n]{10,200}\./i
      );
      if (ementaMatch) ementa = ementaMatch[0].trim();
    }

    // CF/ADCT: separar antes de repairLegisText, que colapsa quebras de linha e
    // impede localizar o cabeçalho autônomo do ADCT no fim da Constituição.
    const skipUntil = findLegisBodyStart(cleanMeta, doc);
    let body = skipUntil >= 0 ? cleanMeta.slice(skipUntil) : cleanMeta;

    const splitRe = new RegExp(
      `\\n(?=(?:Ato das Disposi[cç][õo]es Constitucionais Transit[oó]rias|DISPOSI[CÇ][ÕO]ES CONSTITUCIONAIS TRANSIT[OÓ]RIAS|Parte\\s+(?:Geral|Especial)|TÍTULO|CAPÍTULO|SEÇÃO|Seção|Subseção)\\s|${ARTICLE_HEAD_PREFIX}(?:${ARTICLE_NUM})(?!\\d)[º°o]?${ARTICLE_HEAD_TAIL})`
    );

    function buildBlocksFromSection(sectionBody, { adctSection = false } = {}) {
      if (!sectionBody) return [];
      const local = [];
      let work = stripSupersededArticleSections(sectionBody);
      work = ensureLegisStructureBreaks(repairLegisText(work));
      const parts = work.split(splitRe);

      if (adctSection) {
        local.push({
          type: "titulo",
          label: "Disposições Constitucionais Transitórias (ADCT)",
          text: "",
        });
      }

      let pendingEpigraph = null;

      for (const part of parts) {
        let p = part.trim();
        if (!p || p.length < 4) continue;
        if (!adctSection && ADCT_HEAD_RE.test(p)) continue;
        if (adctSection && ADCT_HEAD_RE.test(p)) continue;
        if (isArticleEpigraphLine(p) && !ARTICLE_HEAD_LINE.test(p) && !/^TÍTULO|^CAPÍTULO|^SEÇÃO/i.test(p)) {
          pendingEpigraph = parseArticleEpigraph(p);
          continue;
        }
        if (/^TÍTULO\s+[IVXLC\d]+/i.test(p)) {
          local.push({ type: "titulo", label: p.split("\n")[0].trim(), text: p });
        } else if (/^Parte\s+(Geral|Especial)/i.test(p)) {
          local.push({ type: "titulo", label: p.split("\n")[0].trim(), text: p });
        } else if (/^CAPÍTULO\s+[IVXLC\d]+/i.test(p) || /^CAPÍTULO\s*[—–-]/i.test(p.split("\n")[0])) {
          local.push({ type: "capitulo", label: p.split("\n")[0].trim(), text: p });
        } else if (/^SEÇÃO\s+[IVXLC\d]+/i.test(p)) {
          local.push({ type: "capitulo", label: p.split("\n")[0].trim(), text: p });
        } else if (ARTICLE_HEAD_LINE.test(p)) {
          let raw = p;
          const trailing = extractTrailingEpigraph(raw);
          raw = trailing.text;
          const leading = extractLeadingEpigraph(raw);
          raw = leading.text;
          let label =
            raw.match(
              new RegExp(`^(${ARTICLE_HEAD_PREFIX}(?:${ARTICLE_NUM})(?!\\d)[º°o]?(?:\\s*[-–]\\s*[A-Z](?:\\.|\\s|$))?)`)
            )?.[1] || "Artigo";
          const epigraph = pendingEpigraph || leading.epigraph;
          pendingEpigraph = trailing.epigraph || null;
          if (epigraph) label = appendEpigraphToLabel(label, epigraph);
          const artText = formatArtigoBody(raw, label);
          if (artText) {
            local.push({
              type: "artigo",
              label: adctSection ? `${label} (ADCT)` : label,
              text: artText,
            });
          }
        }
      }
      return relocateArticleEpigraphs(
        dedupeArticleBlocks(mergeParagraphsIntoArticles(local), { adctSection })
      );
    }

    if (isConstituicaoUrl(doc)) {
      body = isolateCfAdctSectionHeader(body);
      body = normalizeCfAdctSectionHeader(body);
    }

    const { main, adct } = splitLegisAdct(body, doc);
    blocks.push(...buildBlocksFromSection(main));
    blocks.push(...buildBlocksFromSection(adct, { adctSection: true }));

    if (!blocks.length) {
      body.split(/\n\n+/).forEach((chunk, i) => {
        if (chunk.trim().length > 10) {
          blocks.push({ type: "trecho", label: `§ ${i + 1}`, text: chunk.trim() });
        }
      });
    }

    return { epigrafe, ementa, blocks };
  }

  function renderJurisItem(item, idx) {
    const id = item.id || `juris-${idx}`;
    const meta = [item.relator && `Relator: ${item.relator}`, item.julgamento && `Julgamento: ${item.julgamento}`, item.data && item.data]
      .filter(Boolean)
      .join(" · ");

    const section = (title, content, part) =>
      content
        ? `<section class="juris-section"><h4 class="juris-section-title">${title}</h4><p class="juris-section-text article-text" data-hl-part="${part}">${escHtml(content)}</p></section>`
        : "";

    const ementa =
      item.ementa && !/^Relator:/i.test(item.ementa) ? item.ementa : "";
    let tese = item.tese || "";
    if (!tese && ementa && !/^(STF|STJ|TST|TSE)\s*—\s*S[úu]mula/i.test(ementa)) {
      tese = ementa;
    }
    const julgado = item.julgado || "";

    return `
      <article class="juris-item" id="${escHtml(id)}">
        <header class="juris-item-head">
          <span class="juris-tribunal-badge">${escHtml(item.tribunal || "")}</span>
          <h3 class="juris-item-title">${escHtml(item.numero || item.tipo || "Precedente")}</h3>
          ${meta ? `<p class="juris-item-meta">${escHtml(meta)}</p>` : ""}
        </header>
        ${section("Ementa", ementa, "ementa")}
        ${section("Tese", tese, "tese")}
        ${section("Julgado", julgado, "julgado")}
        ${!ementa && !tese && !julgado ? `<p class="juris-section-text article-text empty-inline" data-hl-part="texto">Conteúdo indisponível para este precedente.</p>` : ""}
      </article>`;
  }

  function renderLegisBlock(block, idx) {
    const cls =
      block.type === "titulo"
        ? "lei-titulo"
        : block.type === "capitulo"
          ? "lei-capitulo"
          : block.type === "artigo"
            ? "lei-artigo"
            : "lei-trecho";
    const bodyHtml =
      block.type === "artigo"
        ? renderArtigoContent(block.text)
        : (() => {
            const lines = block.text.split("\n");
            const bodyText =
              lines[0]?.trim() === block.label.trim()
                ? lines.slice(1).join("\n").trim()
                : block.text.replace(block.label, "").trim() || block.text;
            return `<div class="lei-text">${formatLeiHtml(bodyText)}</div>`;
          })();
    return `
      <article class="${cls}" id="art-${idx}" data-art-id="${idx}">
        <div class="lei-label">${escHtml(block.label)}</div>
        ${bodyHtml}
      </article>`;
  }

  function formatDocument(doc) {
    const body = doc.body || "";
    const kind = classifyDoc(doc);

    if (doc.doc_type === "legislacao" || doc.source_system === "planalto" || doc.source_system === "rideel_vademecum") {
      const parsed = parseLegislacao(body, doc);
      return {
        mode: "legislacao",
        epigrafe: parsed.epigrafe,
        ementa: parsed.ementa,
        blocks: parsed.blocks,
        articles: parsed.blocks
          .filter((b) => b.type === "artigo")
          .map((b, i) => ({ id: i, label: b.label, text: b.text })),
      };
    }

    if (kind === "tema") {
      const item = parseTema(body);
      return { mode: "juris", items: [item], articles: [{ id: 0, label: item.numero, text: item.ementa }] };
    }

    if (kind === "sumula_individual") {
      const item = parseSumulaPage(body, doc.url || doc.doc_key);
      if (item.tese) {
        return { mode: "juris", items: [item], articles: [{ id: 0, label: item.numero, text: item.tese }] };
      }
    }

    if (kind === "julgado") {
      const item = parseJulgadoEntry(cleanRaw(body), doc.organized?.tribunal);
      if (item) return { mode: "juris", items: [item], articles: [{ id: 0, label: item.numero, text: item.ementa }] };
    }

    if (kind === "sumulas_colecao" || kind === "sumulas_vinculantes") {
      const tribunal = doc.organized?.tribunal || tribunalFromPath(pathOnly(doc.url || ""));
      const items = parseSumulasColecao(body, tribunal);
      return {
        mode: "juris",
        items,
        articles: items.map((it, i) => ({ id: i, label: it.numero, text: it.ementa })),
      };
    }

    if (kind === "julgados_colecao") {
      const items = parseJulgadosColecao(body);
      return {
        mode: "juris",
        items,
        articles: items.map((it, i) => ({ id: i, label: it.numero, text: it.ementa })),
      };
    }

    const tema = parseTema(body);
    if (tema.ementa) {
      return { mode: "juris", items: [tema], articles: [{ id: 0, label: tema.numero, text: tema.ementa }] };
    }

    const clean = cleanRaw(body);
    return {
      mode: "juris",
      items: [{ tipo: "precedente", tribunal: doc.organized?.tribunal || "STF", numero: friendlyTitle(doc), ementa: clean.slice(0, 500), tese: "", julgado: clean.slice(500, 1500) }],
      articles: [{ id: 0, label: "Texto", text: clean }],
    };
  }

  function buildLexRouteId(doc) {
    const url = (doc.url || doc.doc_key || "").toLowerCase();
    const tribunal = (doc.organized?.tribunal || tribunalFromPath(pathOnly(url)) || "stf").toLowerCase();

    let m = url.match(/sumula-vinculante-(\d+)/);
    if (m) return `sumula-stf-sv-${m[1]}`;

    m = url.match(/sumula-(\d+)/);
    if (m) return `sumula-${tribunal}-${m[1]}`;

    m = url.match(/tema-repetitivo-(\d+)/);
    if (m) return `tema-${tribunal}-rep-${m[1]}`;

    m = url.match(/tema-(\d+)/);
    if (m) return `tema-${tribunal}-${m[1]}`;

    m = url.match(/principais-julgados\/[^/]+\/([^/?#]+)/);
    if (m) return `julgado-${m[1].replace(/[^a-z0-9-]+/gi, "-").slice(0, 48)}`;

    if (doc.doc_type === "legislacao" || doc.source_system === "planalto") {
      m = url.match(/l(\d+)(?:comp|cons|orig|_)?\.htm/i);
      if (m) return `lei-${m[1]}`;
    }

    const key = doc.doc_key || doc.url || doc.external_id || doc.title || "";
    let hash = 2166136261;
    for (let i = 0; i < key.length; i++) {
      hash ^= key.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return `doc-${(hash >>> 0).toString(36)}`;
  }

  function legisSourceRank(doc) {
    if (doc.source_system === "planalto") return 0;
    if (doc.source_system === "rideel_vademecum") return 1;
    return 2;
  }

  function legisSortRank(doc) {
    const u = pathOnly(doc.url || doc.doc_key || "").toLowerCase();
    if (/constituicao\.htm|constituicao\/constituicao/.test(u)) return 0;
    if (/l10406|2002\/l10406/.test(u)) return 1;
    if (/del2848|cod_pen/.test(u)) return 2;
    if (/l13105/.test(u)) return 3;
    return 100;
  }

  function legisListTitle(doc) {
    return doc.title || friendlyTitle(doc);
  }

  function prepareCatalog(docs) {
    const seen = new Set();
    const routeIds = new Set();
    const byUrl = new Map();
    const out = [];
    const keepKinds = new Set([
      "tema",
      "julgado",
      "sumula_individual",
      "sumulas_colecao",
      "sumulas_vinculantes",
      "julgados_colecao",
      "temas_colecao",
      "teses_colecao",
    ]);
    for (const doc of docs) {
      const kind = classifyDoc(doc);
      if (kind === "skip") continue;
      if (kind === "sumulas_colecao" || kind === "sumulas_vinculantes" || kind === "temas_colecao" || kind === "teses_colecao") {
        continue;
      }
      if (kind === "julgados_colecao") {
        const p = pathOnly(doc.url || doc.doc_key || "");
        if (!/\/principais-julgados\/[^/]+\/[^/]+/.test(p)) continue;
      }
      if (doc.doc_type !== "legislacao" && doc.doc_type !== "sumula" && !keepKinds.has(kind)) continue;
      if (doc.doc_type === "sumula" && kind === "outro") {
        doc.catalog_kind = doc.catalog_kind || "sumula_individual";
      }
      const key = `${doc.source_system}::${pathOnly(doc.url || doc.doc_key)}`;
      if (seen.has(key)) continue;
      seen.add(key);
      doc.catalog_kind = kind;
      doc.title = friendlyTitle(doc);
      if (!doc.organized) doc.organized = {};
      doc.organized.tribunal = doc.organized.tribunal || tribunalFromPath(pathOnly(doc.url || ""));
      let routeId = buildLexRouteId(doc);
      if (routeIds.has(routeId)) {
        routeId = `${routeId}-${(seen.size + 1).toString(36)}`;
      }
      routeIds.add(routeId);
      doc.lex_route_id = routeId;

      const urlKey = (() => {
        if (doc.doc_type === "legislacao") {
          const canon = window.LexLegisMeta?.legisCanonicalKey?.(doc.url || doc.doc_key || "");
          if (canon) return canon;
        }
        return pathOnly(doc.url || doc.doc_key || "").toLowerCase();
      })();
      if (doc.doc_type === "legislacao" && urlKey) {
        const prev = byUrl.get(urlKey);
        if (prev) {
          const prevScore = legisSourceRank(prev) * 100000 - (prev.chunk_count || 0);
          const nextScore = legisSourceRank(doc) * 100000 - (doc.chunk_count || 0);
          if (nextScore >= prevScore) continue;
          const idx = out.indexOf(prev);
          if (idx >= 0) out.splice(idx, 1);
        }
        byUrl.set(urlKey, doc);
      }

      out.push(doc);
    }
    const order = {
      tema: 0,
      julgado: 1,
      sumula_individual: 2,
      sumulas_vinculantes: 3,
      sumulas_colecao: 4,
      julgados_colecao: 5,
      temas_colecao: 6,
      teses_colecao: 7,
    };
    out.sort((a, b) => {
      const ka = a.catalog_kind ?? "outro";
      const kb = b.catalog_kind ?? "outro";
      const ca = order[ka] ?? 9;
      const cb = order[kb] ?? 9;
      if (ca !== cb) return ca - cb;
      if (a.doc_type === "legislacao" && b.doc_type === "legislacao") {
        const lr = legisSortRank(a) - legisSortRank(b);
        if (lr) return lr;
        return String(a.title || "").localeCompare(String(b.title || ""), "pt");
      }
      return 0;
    });
    return out;
  }

  function jurisCardPreview(doc) {
    if (doc.juris_card_preview) return doc.juris_card_preview;

    const kind = doc.catalog_kind || classifyDoc(doc);
    const text = doc.body || doc.resumo || "";

    if (kind === "tema") {
      if (doc.resumo?.trim()) return shortenJurisSnippet(doc.resumo, 280);
      if (text) {
        const item = parseTema(text);
        const snippet = (item.tese || item.ementa || item.julgado || cleanRaw(text)).trim();
        if (snippet) return shortenJurisSnippet(snippet, 280);
      }
      return "";
    }

    if (kind === "sumula_individual" || doc.doc_type === "sumula") {
      if (doc.resumo?.trim()) return shortenJurisSnippet(doc.resumo, 280);
      if (text) {
        const item = parseSumulaPage(text, doc.url || doc.doc_key);
        const snippet = (item.tese || item.julgado || cleanRaw(text)).trim();
        if (snippet) return shortenJurisSnippet(snippet, 280);
      }
      return "";
    }

    if (kind === "julgado") {
      if (text) {
        const item = parseJulgadoEntry(cleanRaw(text), doc.organized?.tribunal);
        const snippet = (item?.tese || item?.julgado || "").trim();
        if (snippet) return shortenJurisSnippet(snippet, 280);
      }
      return "";
    }

    return jurisPreview(doc);
  }

  function shortenJurisSnippet(text, maxLen) {
    const t = String(text || "").replace(/\s+/g, " ").trim();
    if (!t) return "";
    if (t.length <= (maxLen || 280)) return t;
    const cut = t.slice(0, maxLen || 280);
    const last = cut.lastIndexOf(" ");
    return `${(last > 80 ? cut.slice(0, last) : cut).trim()}…`;
  }

  function jurisPreview(doc) {
    if (doc.catalog_kind === "tema") {
      const plain = doc.resumo || (doc.body ? cleanRaw(doc.body).slice(0, 220) : "");
      if (plain) return plain;
      const n = (doc.url || "").match(/tema(?:-repetitivo)?-(\d+)/i);
      const cat = doc.meta?.tema_categoria;
      if (cat === "recurso_repetitivo") {
        return n ? `Recurso repetitivo · Tema ${n[1]}` : "Recurso repetitivo";
      }
      return n ? `Repercussão Geral · Tema ${n[1]}` : "Repercussão Geral";
    }
    if (doc.catalog_kind === "julgado") return "Julgado";
    if (doc.catalog_kind === "sumula_individual" || doc.doc_type === "sumula") {
      const plain = doc.resumo || (doc.body ? cleanRaw(doc.body).slice(0, 220) : "");
      return plain || "Súmula";
    }
    if (doc.catalog_kind === "sumulas_vinculantes") return "Súmulas Vinculantes";
    if (doc.catalog_kind === "sumulas_colecao") return "Compilado de súmulas";
    if (doc.catalog_kind === "julgados_colecao") return "Seleção de precedentes";
    return doc.organized?.tribunal || "";
  }

  function ensureFormatted(doc) {
    if (!doc?.body) return doc?.formatted || null;
    if (!doc.formatted || doc.formattedVersion !== FORMAT_VERSION) {
      doc.formatted = formatDocument(doc);
      doc.formattedVersion = FORMAT_VERSION;
    }
    return doc.formatted;
  }

  window.LexFormat = {
    FORMAT_VERSION,
    cleanRaw,
    classifyDoc,
    friendlyTitle,
    buildLexRouteId,
    formatDocument,
    ensureFormatted,
    formatLeiHtml,
    normalizePlanaltoEncoding,
    prepareCatalog,
    legisSortRank,
    legisListTitle,
    renderJurisItem,
    renderLegisBlock,
    jurisPreview,
    jurisCardPreview,
    parseJulgadoEntry,
    escHtml,
    isArticleWhollyRevoked,
    hasRevokedTail,
    stripRevokedListItems,
    stripRevokedIncisos,
    pruneRevokedProvisions,
  };
})();
