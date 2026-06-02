/**
 * Planos de estudo automáticos por carreira (editais típicos de concursos jurídicos).
 * Usa apenas material disponível no acervo Lex (legislação, jurisprudência, flashcards).
 */
(function () {
  const LS_KEY = "lex_study_plan_v1";
  const PLAN_VERSION = 5;
  /** limit: 0 = incluir todo o acervo compatível com o filtro (sem teto artificial). */
  const JURIS_LIMIT_ALL = 0;
  const LEGIS_DAILY_MIN = 18;
  const LEGIS_CHUNK_MAX = 8;

  /** Planos curtos exigem mais carga diária para concluir o edital no prazo. */
  function studyDaysIntensity(days) {
    const d = Math.max(1, parseInt(days, 10) || 90);
    if (d <= 14) return 1.45;
    if (d <= 21) return 1.35;
    if (d <= 30) return 1.25;
    if (d <= 45) return 1.15;
    if (d <= 60) return 1.08;
    if (d <= 90) return 1.04;
    return 1;
  }

  /**
   * Calcula meta diária para esgotar `total` em `days` (mais dias → menos por dia).
   * @param {number} total
   * @param {number} days
   * @param {{ min?: number, max?: number, preferred?: number }} opts
   */
  function dailyQuotaToFinish(total, days, opts = {}) {
    const t = Math.max(0, Number(total) || 0);
    const d = Math.max(1, parseInt(days, 10) || 1);
    if (!t) return 0;
    const { min = 0, max = Infinity, preferred = 0 } = opts;
    const base = Math.ceil(t / d);
    const boosted = Math.ceil(base * studyDaysIntensity(d));
    let q = Math.max(base, boosted);
    if (preferred > 0) q = Math.max(q, preferred);
    return Math.min(max, Math.max(min, q));
  }

  function legisChunkMaxForDays(days) {
    const d = parseInt(days, 10) || 90;
    if (d <= 21) return 14;
    if (d <= 45) return 12;
    if (d <= 90) return 10;
    return LEGIS_CHUNK_MAX;
  }

  function computeDailyTargets({
    days,
    totalLegisArticles = 0,
    totalJuris = 0,
    totalFlashCards = 0,
    questionPoolSize = 0,
    questoesPerDayPreferred = 6,
    legisMinPerDay = LEGIS_DAILY_MIN,
  }) {
    const d = Math.max(14, Math.min(365, parseInt(days, 10) || 90));
    const preferredQ = Math.max(0, Math.min(25, parseInt(questoesPerDayPreferred, 10) || 0));
    const legisPerDay = dailyQuotaToFinish(totalLegisArticles, d, {
      min: legisMinPerDay,
      max: 160,
      preferred: 0,
    });
    const jurisPerDay = dailyQuotaToFinish(totalJuris, d, { min: 2, max: 50, preferred: 0 });
    const flashPerDay = totalFlashCards
      ? dailyQuotaToFinish(totalFlashCards, d, { min: 10, max: 100, preferred: 0 })
      : 0;
    const questoesPerDay = dailyQuotaToFinish(questionPoolSize, d, {
      min: 4,
      max: 25,
      preferred: preferredQ,
    });
    const totalQuestoesPlanned = Math.min(questionPoolSize, questoesPerDay * d);
    return {
      days: d,
      intensity: studyDaysIntensity(d),
      legisPerDay,
      jurisPerDay,
      flashPerDay,
      questoesPerDay,
      legisChunkMax: legisChunkMaxForDays(d),
      totalQuestoesPlanned,
    };
  }

  const UF_PROFILES = {
    geral: { label: "Brasil (edital genérico)", bancas: [] },
    AC: { label: "Acre", bancas: ["CESPE/CEBRASPE"] },
    AL: { label: "Alagoas", bancas: ["CESPE/CEBRASPE", "FGV"] },
    AM: { label: "Amazonas", bancas: ["CESPE/CEBRASPE", "FGV"] },
    AP: { label: "Amapá", bancas: ["CESPE/CEBRASPE"] },
    BA: { label: "Bahia", bancas: ["CESPE/CEBRASPE", "FGV"] },
    CE: { label: "Ceará", bancas: ["CESPE/CEBRASPE"] },
    DF: { label: "Distrito Federal", bancas: ["CESPE/CEBRASPE", "FGV"] },
    ES: { label: "Espírito Santo", bancas: ["CESPE/CEBRASPE", "FGV"] },
    GO: { label: "Goiás", bancas: ["CESPE/CEBRASPE"] },
    MA: { label: "Maranhão", bancas: ["CESPE/CEBRASPE", "FGV"] },
    MG: { label: "Minas Gerais", bancas: ["FGV", "CESPE/CEBRASPE"] },
    MS: { label: "Mato Grosso do Sul", bancas: ["FGV", "CESPE/CEBRASPE"] },
    MT: { label: "Mato Grosso", bancas: ["CESPE/CEBRASPE", "FGV"] },
    PA: { label: "Pará", bancas: ["CESPE/CEBRASPE", "FGV"] },
    PB: { label: "Paraíba", bancas: ["CESPE/CEBRASPE"] },
    PE: { label: "Pernambuco", bancas: ["CESPE/CEBRASPE", "FGV"] },
    PI: { label: "Piauí", bancas: ["CESPE/CEBRASPE"] },
    PR: { label: "Paraná", bancas: ["FCC", "FGV"] },
    RJ: { label: "Rio de Janeiro", bancas: ["FGV", "CESPE/CEBRASPE"] },
    RN: { label: "Rio Grande do Norte", bancas: ["CESPE/CEBRASPE", "FGV"] },
    RO: { label: "Rondônia", bancas: ["CESPE/CEBRASPE"] },
    RR: { label: "Roraima", bancas: ["CESPE/CEBRASPE"] },
    RS: { label: "Rio Grande do Sul", bancas: ["FCC", "FGV"] },
    SC: { label: "Santa Catarina", bancas: ["FCC", "FGV"] },
    SE: { label: "Sergipe", bancas: ["CESPE/CEBRASPE"] },
    SP: { label: "São Paulo", bancas: ["VUNESP", "FGV"] },
    TO: { label: "Tocantins", bancas: ["CESPE/CEBRASPE"] },
  };

  /** Filtro de questões do NaIntegra Cursos por carreira-alvo. */
  const CAREER_QUESTAO = {
    magistratura_estadual: {
      carreiras: ["juiz_estadual", "juiz_federal"],
      materias: [
        "Direito Constitucional",
        "Direito Administrativo",
        "Direito Civil",
        "Direito Processual Civil",
        "Direito Penal",
        "Direito Processual Penal",
        "Direito Tributário",
        "Direito do Consumidor",
      ],
      maxPool: 700,
    },
    mp_estadual: {
      carreiras: ["procuradoria", "juiz_estadual"],
      materias: [
        "Direito Penal",
        "Direito Processual Penal",
        "Direito Constitucional",
        "Direito Administrativo",
        "Direitos Humanos",
      ],
      maxPool: 600,
    },
    defensoria_publica: {
      carreiras: ["juridica", "procuradoria", "juiz_estadual"],
      materias: [
        "Direito Penal",
        "Direito Processual Penal",
        "Direito Civil",
        "Direito Processual Civil",
        "Direito Constitucional",
        "Direitos Humanos",
      ],
      maxPool: 500,
    },
    delegado_policia: {
      carreiras: ["delegado_civil", "delegado_federal", "policial"],
      materias: [
        "Direito Penal",
        "Direito Processual Penal",
        "Direito Constitucional",
        "Direito Administrativo",
      ],
      maxPool: 650,
    },
    agente_policia: {
      carreiras: ["policial", "delegado_civil"],
      materias: ["Direito Penal", "Direito Processual Penal", "Direito Constitucional", "Direito Administrativo"],
      maxPool: 400,
    },
    agu_pgf: {
      carreiras: ["procuradoria", "agu", "juridica", "juiz_federal"],
      materias: [
        "Direito Constitucional",
        "Direito Administrativo",
        "Direito Civil",
        "Direito Processual Civil",
        "Direito Penal",
        "Direito Processual Penal",
        "Direito Tributário",
        "Direito do Consumidor",
        "Direito Ambiental",
      ],
      maxPool: 550,
    },
    agu_pgfn: {
      carreiras: ["procuradoria", "agu", "juridica"],
      materias: [
        "Direito Tributário",
        "Direito Constitucional",
        "Direito Administrativo",
        "Direito Civil",
        "Direito Processual Civil",
        "Direito Financeiro",
      ],
      maxPool: 500,
    },
    agu_advocacia: {
      carreiras: ["agu", "procuradoria", "juridica"],
      materias: [
        "Direito Constitucional",
        "Direito Administrativo",
        "Direito Civil",
        "Direito Processual Civil",
        "Direito Tributário",
        "Direito Penal",
        "Direito Processual Penal",
      ],
      maxPool: 520,
    },
  };

  /** @typedef {{ match: string[], exclude?: string[], label: string, articlesFallback?: number, priority?: number }} LegisSpec */
  /** @typedef {{ id: string, label: string, filter: (d: object) => boolean, limit: number, priority?: number }} JurisSpec */

  /** Blocos reutilizáveis — cobertura ampliada por edital e incidência em concursos. */
  const LEGIS_NUCLEO = [
    { label: "Constituição Federal (+ ADCT)", match: ["constituicao/constituicao"], exclude: ["emendas"], articlesFallback: 250 },
    { label: "Código Penal", match: ["del2848"], articlesFallback: 260 },
    { label: "Código de Processo Penal", match: ["del3689"], articlesFallback: 320 },
    { label: "LINDB", match: ["del4657"], articlesFallback: 80 },
    { label: "Código Civil", match: ["l10406"], articlesFallback: 380 },
    { label: "Código de Processo Civil", match: ["l13105"], articlesFallback: 350 },
  ];

  const LEGIS_NUCLEO_PENAL = [
    { label: "Constituição Federal (+ ADCT)", match: ["constituicao/constituicao"], exclude: ["emendas"], articlesFallback: 250 },
    { label: "Código Penal", match: ["del2848"], articlesFallback: 260 },
    { label: "Código de Processo Penal", match: ["del3689"], articlesFallback: 320 },
    { label: "LINDB", match: ["del4657"], articlesFallback: 80 },
  ];

  const LEGIS_CONST_CONTROLE = [
    { label: "Lei 9.868/1999 — ADI/ADC", match: ["l9868"], articlesFallback: 25 },
    { label: "Lei 9.882/1999 — ADPF", match: ["l9882"], articlesFallback: 20 },
    { label: "Lei 12.016/2009 — Mandado de Segurança", match: ["l12016"], articlesFallback: 20 },
    { label: "Lei 4.717/1965 — Ação Popular", match: ["l4717"], articlesFallback: 15 },
    { label: "Lei 13.300/2016 — Mandado de Injunção", match: ["l13300"], articlesFallback: 15 },
  ];

  const LEGIS_ADMIN = [
    { label: "Lei 14.133/2021 — Nova Lei de Licitações", match: ["l14133"], articlesFallback: 120 },
    { label: "Lei 9.784/1999 — Processo Administrativo", match: ["l9784"], articlesFallback: 35 },
    { label: "Lei 8.429/1992 — Improbidade", match: ["l8429"], articlesFallback: 45 },
    { label: "Lei 12.527/2011 — LAI", match: ["l12527"], articlesFallback: 45 },
    { label: "Lei 13.460/2017 — Usuário de serviços públicos", match: ["l13460"], articlesFallback: 25 },
    { label: "Dec.-Lei 3.365/1941 — Desapropriação", match: ["del3365"], articlesFallback: 35 },
    { label: "Lei 8.112/1990 — Servidores", match: ["l8112"], articlesFallback: 70 },
    { label: "Lei 9.494/1997 — Execução contra a Fazenda", match: ["l9494"], articlesFallback: 25 },
  ];

  const LEGIS_ADMIN_ESSENCIAL = [
    { label: "Lei 8.429/1992 — Improbidade", match: ["l8429"], articlesFallback: 45 },
    { label: "Lei 8.112/1990 — Servidores", match: ["l8112"], articlesFallback: 70 },
    { label: "Lei 14.133/2021 — Licitações", match: ["l14133"], articlesFallback: 90 },
    { label: "Lei 12.527/2011 — LAI", match: ["l12527"], articlesFallback: 15 },
  ];

  const LEGIS_MP_ORG = [
    { label: "Lei 8.625/1993 — LON do MP", match: ["l8625"], articlesFallback: 40 },
  ];

  const LEGIS_PENAL_ESPECIAL = [
    { label: "Lei 8.072/1990 — Crimes Hediondos", match: ["l8072"], articlesFallback: 15 },
    { label: "Lei 9.455/1997 — Tortura", match: ["l9455"], articlesFallback: 15 },
    { label: "Lei 7.716/1989 — Racismo", match: ["l7716"], articlesFallback: 12 },
    { label: "Lei 9.605/1998 — Crimes Ambientais", match: ["l9605"], articlesFallback: 25 },
    { label: "Lei 8.137/1990 — Crimes Tributários", match: ["l8137"], articlesFallback: 20 },
    { label: "Lei 7.492/1986 — Sistema Financeiro", match: ["l7492"], articlesFallback: 20 },
    { label: "Lei 9.296/1996 — Interceptação", match: ["l9296"], articlesFallback: 12 },
    { label: "Lei 9.613/1998 — Lavagem de Capitais", match: ["l9613"], articlesFallback: 25 },
    { label: "Lei 11.343/2006 — Drogas", match: ["l11343"], articlesFallback: 80 },
    { label: "Lei 12.850/2013 — Organizações Criminosas", match: ["l12850"], articlesFallback: 40 },
    { label: "Lei 13.869/2019 — Abuso de Autoridade", match: ["l13869"], articlesFallback: 25 },
    { label: "Lei 10.826/2003 — Desarmamento", match: ["l10826"], articlesFallback: 35 },
    { label: "Lei 9.503/1997 — CTB", match: ["l9503"], articlesFallback: 120 },
    { label: "Lei 11.340/2006 — Maria da Penha", match: ["l11340"], articlesFallback: 15 },
    { label: "Lei 9.099/1995 — Juizados Especiais", match: ["l9099"], articlesFallback: 15 },
    { label: "Lei 13.260/2016 — Terrorismo", match: ["l13260"], articlesFallback: 20 },
    { label: "Lei 14.811/2024 — Bullying/cyberbullying", match: ["l14811"], articlesFallback: 10 },
    { label: "Lei 14.597/2023 — Lei Geral do Esporte", match: ["l14597"], articlesFallback: 80 },
    { label: "Lei 14.344/2022 — Henry Borel", match: ["l14344"], articlesFallback: 25 },
    { label: "Lei 13.431/2017 — Depoimento Especial", match: ["l13431"], articlesFallback: 20 },
    { label: "Lei 13.964/2019 — Pacote Anticrime", match: ["l13964"], articlesFallback: 80 },
    { label: "Lei 7.210/1984 — LEP", match: ["l7210"], articlesFallback: 200 },
  ];

  const LEGIS_PENAL_ESPECIAL_CORE = [
    { label: "Lei 11.343/2006 — Drogas", match: ["l11343"], articlesFallback: 80 },
    { label: "Lei 11.340/2006 — Maria da Penha", match: ["l11340"], articlesFallback: 15 },
    { label: "Lei 8.072/1990 — Crimes Hediondos", match: ["l8072"], articlesFallback: 15 },
    { label: "Lei 12.850/2013 — Organizações Criminosas", match: ["l12850"], articlesFallback: 40 },
    { label: "Lei 13.869/2019 — Abuso de Autoridade", match: ["l13869"], articlesFallback: 25 },
    { label: "Lei 9.605/1998 — Crimes Ambientais", match: ["l9605"], articlesFallback: 25 },
    { label: "Lei 9.613/1998 — Lavagem de Capitais", match: ["l9613"], articlesFallback: 25 },
    { label: "Lei 9.099/1995 — Juizados Especiais", match: ["l9099"], articlesFallback: 15 },
    { label: "Lei 7.210/1984 — LEP", match: ["l7210"], articlesFallback: 200 },
    { label: "Lei 13.964/2019 — Pacote Anticrime", match: ["l13964"], articlesFallback: 80 },
  ];

  const LEGIS_CIVIL_EMPRESARIAL = [
    { label: "Lei 8.245/1991 — Locações", match: ["l8245"], articlesFallback: 40 },
    { label: "Lei 11.101/2005 — Recuperação e Falência", match: ["l11101"], articlesFallback: 90 },
    { label: "Lei 6.404/1976 — S.A.", match: ["l6404"], articlesFallback: 120 },
    { label: "Lei 8.934/1994 — Registro de Empresas", match: ["l8934"], articlesFallback: 40 },
    { label: "Lei 6.015/1973 — Registros Públicos", match: ["l6015"], articlesFallback: 80 },
  ];

  const LEGIS_TUTELA_COLETIVA = [
    { label: "Lei 7.347/1985 — Ação Civil Pública", match: ["l7347"], articlesFallback: 20 },
    { label: "Lei 8.078/1990 — CDC", match: ["l8078"], articlesFallback: 120 },
    { label: "Lei 8.069/1990 — ECA", match: ["l8069cons", "l8069.htm", "/leis/l8069"], exclude: ["l8069a"], articlesFallback: 170 },
    { label: "Lei 12.852/2013 — Estatuto da Juventude", match: ["l12852"], articlesFallback: 40 },
    { label: "Lei 10.741/2003 — Estatuto do Idoso", match: ["l10741"], articlesFallback: 60 },
    { label: "Lei 13.146/2015 — Estatuto da Pessoa com Deficiência", match: ["l13146"], articlesFallback: 80 },
    { label: "Lei 7.853/1989 — Apoio à PcD", match: ["l7853"], articlesFallback: 15 },
    { label: "Lei 12.288/2010 — Igualdade Racial", match: ["l12288"], articlesFallback: 25 },
    { label: "Lei 12.846/2013 — Anticorrupção", match: ["l12846"], articlesFallback: 30 },
    { label: "Lei 13.019/2014 — Marco das OSC", match: ["l13019"], articlesFallback: 50 },
  ];

  const LEGIS_SUS = [
    { label: "Lei 8.080/1990 — SUS", match: ["l8080"], articlesFallback: 60 },
    { label: "Lei 8.142/1990 — SUS (gestão)", match: ["l8142"], articlesFallback: 15 },
  ];

  const LEGIS_AMBIENTAL = [
    { label: "Lei 6.938/1981 — PNMA", match: ["l6938"], articlesFallback: 35 },
    { label: "Lei 9.985/2000 — SNUC", match: ["l9985"], articlesFallback: 40 },
    { label: "Lei 12.651/2012 — Código Florestal", match: ["l12651"], articlesFallback: 80 },
    { label: "Lei 11.445/2007 — Saneamento", match: ["l11445"], articlesFallback: 60 },
    { label: "Lei 12.305/2010 — Resíduos Sólidos", match: ["l12305"], articlesFallback: 50 },
    { label: "Lei 14.119/2021 — PSA ambiental", match: ["l14119"], articlesFallback: 25 },
    { label: "Lei 10.257/2001 — Estatuto da Cidade", match: ["l10257"], articlesFallback: 60 },
    { label: "Lei 6.766/1979 — Parcelamento do Solo", match: ["l6766"], articlesFallback: 30 },
  ];

  const LEGIS_DIREITOS_HUMANOS = [
    { label: "Dec. 678/1992 — Convenção Americana de DH", match: ["d0678"], articlesFallback: 40 },
    { label: "Dec. 5.051/2004 — Convenção 169 OIT", match: ["d5051"], articlesFallback: 40 },
    { label: "Dec. 10.932/2022 — Convenção Interamericana contra Racismo", match: ["d10932"], articlesFallback: 30 },
    { label: "Dec. 11.129/2022 — Regulamentação Anticorrupção", match: ["d11129"], articlesFallback: 40 },
  ];

  const LEGIS_ELEITORAL = [
    { label: "Lei 4.737/1965 — Código Eleitoral", match: ["l4737"], articlesFallback: 120 },
    { label: "Lei 9.504/1997 — Lei das Eleições", match: ["l9504"], articlesFallback: 80 },
    { label: "LC 64/1990 — Inelegibilidades", match: ["lcp64"], articlesFallback: 20 },
    { label: "LC 135/2010 — Ficha Limpa", match: ["lcp135"], articlesFallback: 15 },
    { label: "Lei 9.096/1995 — Partidos Políticos", match: ["l9096"], articlesFallback: 40 },
  ];

  const LEGIS_TRABALHO = [
    { label: "Decreto-Lei 5.452/1943 — CLT", match: ["del5452"], articlesFallback: 280 },
  ];

  const LEGIS_TRIBUTARIO = [
    { label: "CTN", match: ["l5172"], articlesFallback: 200 },
    { label: "Lei 6.830/1980 — Execução fiscal", match: ["l6830"], articlesFallback: 80 },
    { label: "Lei 8.137/1990 — Crimes tributários", match: ["l8137"], articlesFallback: 35 },
    { label: "EC 132/2023 — Reforma tributária", match: ["emc132"], articlesFallback: 40 },
    { label: "Lei Complementar 101/2000 — LRF", match: ["lcp101"], articlesFallback: 90 },
    { label: "Lei 12.153/2009 — Juizados da Fazenda", match: ["l12153"], articlesFallback: 20 },
  ];

  function legSpecKey(spec) {
    if (spec.corpus) return `corpus:${spec.corpus}`;
    return (spec.match?.[0] || spec.label || "").toLowerCase();
  }

  /** Une blocos de legislação sem duplicar a mesma norma. */
  function mergeLegis(...blocks) {
    const out = [];
    const seen = new Set();
    let priority = 1;
    for (const block of blocks) {
      const items = Array.isArray(block) ? block : [block];
      for (const item of items) {
        const key = legSpecKey(item);
        if (seen.has(key)) continue;
        seen.add(key);
        out.push({ ...item, priority: priority++ });
      }
    }
    return out;
  }

  const CAREERS = [
    {
      id: "magistratura_estadual",
      label: "Magistratura estadual",
      short: "Magistratura",
      description:
        "Editais de juiz de direito: Constituição, civil, penal, processos, administrativo e legislação especial frequente em provas de entrância.",
      editalFocus:
        "Direito material e processual amplo; jurisprudência constitucional (STF) e infraconstitucional (STJ) em alta incidência.",
      defaultDays: 180,
      flashcardSlugs: [
        "dir-const",
        "dir-adm",
        "dir-civil-geral",
        "dir-civil-obrig",
        "dir-proc-civil",
        "dir-penal-geral",
        "dir-penal-especial",
        "dir-proc-penal",
        "lei-improbidade",
        "licitacoes-lei-14133",
        "jurisprudencia",
      ],
      legis: mergeLegis(
        LEGIS_NUCLEO,
        LEGIS_CONST_CONTROLE,
        LEGIS_ADMIN,
        LEGIS_PENAL_ESPECIAL,
        LEGIS_CIVIL_EMPRESARIAL,
        LEGIS_TUTELA_COLETIVA,
        LEGIS_AMBIENTAL,
        LEGIS_ELEITORAL,
        LEGIS_TRABALHO,
        [{ label: "CTN", match: ["l5172"], articlesFallback: 200 }]
      ),
      juris: [
        { id: "stf_sumulas", label: "Súmulas STF", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 1 },
        { id: "stj_sumulas", label: "Súmulas STJ", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 2 },
        { id: "stf_rg", label: "Temas STF (RG)", filter: (d) => temaRg(d) && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 3 },
        { id: "stj_rep", label: "Temas STJ (repetitivos)", filter: (d) => temaRepetitivo(d) && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 4 },
      ],
      dailyMix: { legisShare: 0.65, jurisShare: 0.25, flashShare: 0.1 },
    },
    {
      id: "mp_estadual",
      label: "Ministério Público estadual",
      short: "MP estadual",
      description:
        "Promotor de Justiça: ênfase em direito penal, processual penal, constitucional, administrativo e tutela coletiva.",
      editalFocus: "Edital MPSP: núcleo penal/processual, tutela coletiva, administrativo, eleitoral e direitos humanos.",
      defaultDays: 150,
      flashcardSlugs: [
        "dir-const",
        "dir-adm",
        "dir-penal-geral",
        "dir-penal-especial",
        "dir-proc-penal",
        "tutela-coletiva",
        "lei-improbidade",
        "dir-civil-geral",
        "dir-proc-civil",
        "dir-eleitoral",
        "jurisprudencia",
      ],
      legis: mergeLegis(
        LEGIS_NUCLEO,
        LEGIS_CONST_CONTROLE,
        LEGIS_ADMIN,
        LEGIS_MP_ORG,
        LEGIS_PENAL_ESPECIAL,
        LEGIS_CIVIL_EMPRESARIAL,
        LEGIS_TUTELA_COLETIVA,
        LEGIS_SUS,
        LEGIS_AMBIENTAL,
        LEGIS_DIREITOS_HUMANOS,
        LEGIS_ELEITORAL
      ),
      juris: [
        { id: "stf_penal_const", label: "Súmulas STF", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 1 },
        { id: "stj_penal", label: "Súmulas STJ", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 2 },
        { id: "stf_rg", label: "Temas STF (RG)", filter: (d) => temaRg(d) && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 3 },
        { id: "stj_rep", label: "Temas STJ (repetitivos)", filter: (d) => temaRepetitivo(d) && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 4 },
      ],
      dailyMix: { legisShare: 0.6, jurisShare: 0.3, flashShare: 0.1 },
    },
    {
      id: "defensoria_publica",
      label: "Defensoria Pública estadual",
      short: "Defensoria",
      description:
        "Defensor público: direitos humanos, criminal, família, civil e processual com foco em vulnerabilidade e tutela.",
      editalFocus: "CF, CP, CPP, CC, CPC, ECA, violência doméstica e execução penal.",
      defaultDays: 150,
      flashcardSlugs: [
        "dir-const",
        "dir-penal-geral",
        "dir-penal-especial",
        "dir-proc-penal",
        "dir-civil-geral",
        "dir-civil-obrig",
        "dir-proc-civil",
        "tutela-coletiva",
        "dir-previdenciario",
        "jurisprudencia",
      ],
      legis: mergeLegis(
        LEGIS_NUCLEO,
        LEGIS_PENAL_ESPECIAL,
        LEGIS_TUTELA_COLETIVA,
        LEGIS_DIREITOS_HUMANOS,
        LEGIS_CONST_CONTROLE,
        [{ label: "Lei 9.784/1999 — Processo Administrativo", match: ["l9784"], articlesFallback: 35 }]
      ),
      juris: [
        { id: "stf_sumulas", label: "Súmulas STF", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 1 },
        { id: "stj_sumulas", label: "Súmulas STJ", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 2 },
        { id: "stf_rg", label: "Temas STF (RG)", filter: (d) => temaRg(d) && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 3 },
        { id: "stj_rep", label: "Temas STJ (repetitivos)", filter: (d) => temaRepetitivo(d) && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 4 },
      ],
      dailyMix: { legisShare: 0.62, jurisShare: 0.28, flashShare: 0.1 },
    },
    {
      id: "delegado_policia",
      label: "Delegado de Polícia",
      short: "Delegado",
      description:
        "Carreira policial civil de nível superior: direito penal, processual penal, constitucional e administrativo.",
      editalFocus: "CP, CPP, legislação penal especial, improbidade e jurisprudência criminal.",
      defaultDays: 120,
      flashcardSlugs: [
        "dir-const",
        "dir-adm",
        "dir-penal-geral",
        "dir-penal-especial",
        "dir-proc-penal",
        "lei-improbidade",
        "jurisprudencia",
      ],
      legis: mergeLegis(LEGIS_NUCLEO_PENAL, LEGIS_ADMIN_ESSENCIAL, LEGIS_PENAL_ESPECIAL),
      juris: [
        { id: "stf_sumulas", label: "Súmulas STF", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 1 },
        { id: "stj_sumulas", label: "Súmulas STJ", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 2 },
        { id: "stf_rg", label: "Temas STF (RG)", filter: (d) => temaRg(d) && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 3 },
        { id: "stj_rep", label: "Temas STJ (repetitivos)", filter: (d) => temaRepetitivo(d) && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 4 },
      ],
      dailyMix: { legisShare: 0.68, jurisShare: 0.27, flashShare: 0.05 },
    },
    {
      id: "agente_policia",
      label: "Agente de Polícia",
      short: "Agente",
      description:
        "Carreira policial de nível médio/superior: núcleo penal, constitucional básico e administrativo.",
      editalFocus: "CP e CPP com menor profundidade em civil; súmulas e temas penais prioritários.",
      defaultDays: 90,
      flashcardSlugs: ["dir-const", "dir-adm", "dir-penal-geral", "dir-penal-especial", "dir-proc-penal"],
      legis: mergeLegis(LEGIS_NUCLEO_PENAL, LEGIS_ADMIN_ESSENCIAL, LEGIS_PENAL_ESPECIAL_CORE),
      juris: [
        { id: "stf_sumulas", label: "Súmulas STF", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 1 },
        { id: "stj_sumulas", label: "Súmulas STJ", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 2 },
        { id: "stf_rg", label: "Temas STF (RG)", filter: (d) => temaRg(d) && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 3 },
        { id: "stj_rep", label: "Temas STJ (repetitivos)", filter: (d) => temaRepetitivo(d) && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 4 },
      ],
      dailyMix: { legisShare: 0.72, jurisShare: 0.23, flashShare: 0.05 },
    },
    {
      id: "agu_pgf",
      label: "AGU — Procuradoria-Geral Federal (PGF)",
      short: "PGF",
      description:
        "Procurador Federal: contencioso e consultoria da União — constitucional, administrativo, civil, penal e regulação do serviço público federal.",
      editalFocus:
        "Edital AGU: direito público amplo, improbidade, licitações, processo civil e penal, com jurisprudência STF/STJ.",
      defaultDays: 180,
      flashcardSlugs: [
        "dir-const",
        "dir-adm",
        "dir-civil-geral",
        "dir-civil-obrig",
        "dir-proc-civil",
        "dir-penal-geral",
        "dir-penal-especial",
        "dir-proc-penal",
        "lei-improbidade",
        "licitacoes-lei-14133",
        "dir-financeiro",
        "tutela-coletiva",
        "jurisprudencia",
      ],
      legis: mergeLegis(
        LEGIS_NUCLEO,
        LEGIS_CONST_CONTROLE,
        LEGIS_ADMIN,
        LEGIS_PENAL_ESPECIAL_CORE,
        LEGIS_TUTELA_COLETIVA,
        LEGIS_AMBIENTAL,
        [{ label: "CTN", match: ["l5172"], articlesFallback: 200 }],
        {
          label: "Normas AGU (decretos do acervo)",
          corpus: "legislacao_agu",
          maxFromCorpus: 10,
          articlesFallback: 25,
        }
      ),
      juris: [
        { id: "stf_sumulas", label: "Súmulas STF", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 1 },
        { id: "stj_sumulas", label: "Súmulas STJ", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 2 },
        { id: "stf_rg", label: "Temas STF (RG)", filter: (d) => temaRg(d) && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 3 },
        { id: "stj_rep", label: "Temas STJ (repetitivos)", filter: (d) => temaRepetitivo(d) && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 4 },
      ],
      dailyMix: { legisShare: 0.64, jurisShare: 0.28, flashShare: 0.08 },
    },
    {
      id: "agu_pgfn",
      label: "AGU — Procuradoria-Geral da Fazenda Nacional (PGFN)",
      short: "PGFN",
      description:
        "Procurador da Fazenda Nacional: contencioso tributário e consultoria fiscal da União.",
      editalFocus:
        "Ênfase em CTN, execução fiscal, crimes tributários, reforma tributária e processo; administrativo e civil de suporte.",
      defaultDays: 150,
      flashcardSlugs: [
        "dir-const",
        "dir-adm",
        "dir-financeiro",
        "dir-civil-geral",
        "dir-proc-civil",
        "lei-improbidade",
        "licitacoes-lei-14133",
        "jurisprudencia",
      ],
      legis: mergeLegis(
        LEGIS_NUCLEO,
        LEGIS_TRIBUTARIO,
        LEGIS_ADMIN,
        LEGIS_CIVIL_EMPRESARIAL,
        {
          label: "Normas AGU (consultoria fiscal)",
          corpus: "legislacao_agu",
          maxFromCorpus: 6,
          articlesFallback: 20,
        }
      ),
      juris: [
        { id: "stf_sumulas", label: "Súmulas STF", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 1 },
        { id: "stj_sumulas", label: "Súmulas STJ", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 2 },
        { id: "stf_rg", label: "Temas STF (RG)", filter: (d) => temaRg(d) && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 3 },
        { id: "stj_rep", label: "Temas STJ (repetitivos)", filter: (d) => temaRepetitivo(d) && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 4 },
      ],
      dailyMix: { legisShare: 0.62, jurisShare: 0.3, flashShare: 0.08 },
    },
    {
      id: "agu_advocacia",
      label: "AGU — Advocacia da União",
      short: "AGU",
      description:
        "Advogado da União: consultoria e contencioso judicial/extrajudicial dos órgãos federais.",
      editalFocus:
        "Núcleo constitucional e administrativo; civil e processo; licitações, improbidade e pacote normativo da AGU.",
      defaultDays: 160,
      flashcardSlugs: [
        "dir-const",
        "dir-adm",
        "dir-civil-geral",
        "dir-civil-obrig",
        "dir-proc-civil",
        "dir-penal-geral",
        "dir-proc-penal",
        "lei-improbidade",
        "licitacoes-lei-14133",
        "dir-financeiro",
        "jurisprudencia",
      ],
      legis: mergeLegis(
        LEGIS_NUCLEO,
        LEGIS_CONST_CONTROLE,
        LEGIS_ADMIN,
        LEGIS_TUTELA_COLETIVA,
        [{ label: "Lei 8.906/1994 — Estatuto da OAB", match: ["l8906"], articlesFallback: 80 }],
        LEGIS_PENAL_ESPECIAL_CORE,
        [{ label: "CTN (noções)", match: ["l5172"], articlesFallback: 200 }],
        {
          label: "Normas AGU (organização e competências)",
          corpus: "legislacao_agu",
          maxFromCorpus: 12,
          articlesFallback: 25,
        }
      ),
      juris: [
        { id: "stf_sumulas", label: "Súmulas STF", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 1 },
        { id: "stj_sumulas", label: "Súmulas STJ", filter: (d) => d.doc_type === "sumula" && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 2 },
        { id: "stf_rg", label: "Temas STF (RG)", filter: (d) => temaRg(d) && tribunalOf(d) === "STF", limit: JURIS_LIMIT_ALL, priority: 3 },
        { id: "stj_rep", label: "Temas STJ (repetitivos)", filter: (d) => temaRepetitivo(d) && tribunalOf(d) === "STJ", limit: JURIS_LIMIT_ALL, priority: 4 },
      ],
      dailyMix: { legisShare: 0.63, jurisShare: 0.27, flashShare: 0.1 },
    },
  ];

  function tribunalOf(doc) {
    const t = doc?.meta?.tribunal || doc?.organized?.tribunal || "";
    return String(t).toUpperCase();
  }

  function temaRg(doc) {
    if (doc?.doc_type !== "jurisprudencia" && doc?.catalog_kind !== "tema") return false;
    return Boolean(
      doc?.meta?.is_repercussao ||
        doc?.meta?.tema_categoria === "repercussao_geral" ||
        doc?.is_repercussao === true
    );
  }

  function temaRepetitivo(doc) {
    if (doc?.doc_type !== "jurisprudencia" && doc?.catalog_kind !== "tema") return false;
    return Boolean(
      doc?.meta?.is_repetitivo ||
        doc?.meta?.tema_categoria === "recurso_repetitivo" ||
        doc?.is_repetitivo === true
    );
  }

  function temaNumero(doc) {
    const n = parseInt(doc?.meta?.tema_numero || doc?.title?.match(/\d+/)?.[0] || "0", 10);
    return Number.isFinite(n) ? n : 0;
  }

  function docOrg(doc) {
    return { ...(doc.organized || {}), ...(doc.meta || {}) };
  }

  function bancaScore(banca, preferred) {
    if (!preferred?.length || !banca) return 0;
    const b = String(banca).toUpperCase();
    for (let i = 0; i < preferred.length; i++) {
      if (b.includes(preferred[i].toUpperCase())) return preferred.length - i;
    }
    return 0;
  }

  function materiaMatches(materia, list) {
    if (!list?.length) return true;
    const m = String(materia || "").toLowerCase();
    return list.some((tag) => m.includes(tag.toLowerCase().slice(0, 14)));
  }

  function filterQuestions(documents, careerId, uf) {
    const cfg = CAREER_QUESTAO[careerId];
    if (!cfg) return [];
    const ufProfile = UF_PROFILES[uf] || UF_PROFILES.geral;
    const pool = documents
      .filter((d) => d.doc_type === "questoes_objetivas" || d.doc_type === "questoes_subjetivas")
      .filter((d) => {
        const o = docOrg(d);
        const carreira = String(o.carreira || "").toLowerCase();
        if (cfg.carreiras?.length && !cfg.carreiras.some((c) => carreira.includes(c))) return false;
        if (!materiaMatches(o.materia || o.disciplina, cfg.materias)) return false;
        return true;
      });

    pool.sort((a, b) => {
      const oa = docOrg(a);
      const ob = docOrg(b);
      const sa = bancaScore(oa.banca, ufProfile.bancas);
      const sb = bancaScore(ob.banca, ufProfile.bancas);
      if (sb !== sa) return sb - sa;
      return (parseInt(ob.ano, 10) || 0) - (parseInt(oa.ano, 10) || 0);
    });
    return pool.slice(0, cfg.maxPool || 500);
  }

  /** Intercala questões por disciplina (matéria) em cada dia. */
  function distributeQuestionTasks(questions, days, perDay) {
    const schedule = Array.from({ length: days }, () => []);
    if (!questions.length || perDay <= 0) return schedule;

    const pools = [];
    const byMateria = new Map();
    for (const q of questions) {
      const o = docOrg(q);
      const m = o.materia || "Geral";
      if (!byMateria.has(m)) byMateria.set(m, []);
      byMateria.get(m).push(q);
    }
    for (const pool of byMateria.values()) pools.push(pool);

    const mapQ = (q) => {
      const o = docOrg(q);
      return {
        docId: q.external_id || q.lex_route_id,
        title: [o.banca, o.ano, o.materia].filter(Boolean).join(" — ") || q.title || "Questão",
        materia: o.materia,
        banca: o.banca,
        tipo: q.doc_type === "questoes_subjetivas" ? "subjetiva" : "objetiva",
      };
    };

    let day = 0;
    let guard = 0;
    const maxGuard = questions.length * pools.length + days * 2;

    while (pools.some((p) => p.length) && guard++ < maxGuard) {
      for (const pool of pools) {
        if (!pool.length) continue;
        while (day < days && schedule[day].length >= perDay) day += 1;
        if (day >= days) {
          day = days - 1;
          break;
        }
        schedule[day].push(mapQ(pool.shift()));
      }
      if (day < days - 1 && schedule[day].length >= perDay) day += 1;
    }

    for (const pool of pools) {
      while (pool.length) {
        let d = days - 1;
        while (d >= 0 && schedule[d].length >= perDay) d -= 1;
        if (d < 0) d = days - 1;
        schedule[d].push(mapQ(pool.shift()));
      }
    }

    return schedule;
  }

  function docHaystack(doc) {
    return `${doc.doc_key || ""} ${doc.url || ""} ${doc.lex_route_id || ""}`.toLowerCase();
  }

  function docCorpus(doc) {
    return doc?.meta?.corpus || doc?.organized?.corpus || "";
  }

  function matchesLegisSpec(doc, spec) {
    if (doc.doc_type !== "legislacao") return false;
    const hay = docHaystack(doc);
    if (spec.corpus) {
      if (docCorpus(doc) !== spec.corpus) return false;
      if (spec.exclude?.some((e) => hay.includes(e.toLowerCase()))) return false;
      return true;
    }
    if (spec.exclude?.some((e) => hay.includes(e.toLowerCase()))) return false;
    if (!spec.match?.length) return false;
    return spec.match.some((m) => hay.includes(m.toLowerCase()));
  }

  function countLegisArtigoBlocks(doc) {
    const blocks = doc?.formatted?.blocks;
    if (!Array.isArray(blocks) || !blocks.length) return 0;
    return blocks.filter((b) => b.type === "artigo").length;
  }

  /** Unidades de estudo = artigos (não blocos estruturais do Planalto). */
  function articleCount(doc, fallback) {
    const fb = fallback || 40;
    const artigos = countLegisArtigoBlocks(doc);
    if (artigos > 0) return Math.min(artigos, 1200);

    const chunks = doc.chunk_count;
    if (typeof chunks === "number" && chunks > 0) {
      const capped = Math.min(chunks, 800);
      if (capped < fb * 0.35) return Math.round(fb * 0.6);
      return capped;
    }
    return fb;
  }

  function resolveLegis(documents, career) {
    const used = new Set();
    const resolved = [];
    const specs = [...career.legis].sort((a, b) => (a.priority || 99) - (b.priority || 99));

    for (const spec of specs) {
      const candidates = documents
        .filter((d) => matchesLegisSpec(d, spec) && !used.has(d.external_id))
        .sort(
          (a, b) =>
            (b.chunk_count || 0) - (a.chunk_count || 0) ||
            (a.title || "").localeCompare(b.title || "", "pt-BR")
        );

      if (!candidates.length) continue;

      const batch = spec.corpus ? candidates.slice(0, spec.maxFromCorpus || 10) : [candidates[0]];

      for (const doc of batch) {
        used.add(doc.external_id);
        if (doc.body && typeof window !== "undefined" && window.LexFormat?.ensureFormatted) {
          window.LexFormat.ensureFormatted(doc);
        }
        const articles = articleCount(doc, spec.articlesFallback);
        const title = doc.title || spec.label;
        resolved.push({
          specKey: legSpecKey(spec),
          specLabel: spec.corpus ? `${spec.label}: ${title}` : spec.label,
          docId: doc.lex_route_id || doc.external_id,
          title,
          articles,
          available: true,
        });
      }
    }
    return resolved;
  }

  function resolveJuris(documents, career) {
    const items = [];
    const seen = new Set();
    const specs = [...career.juris].sort((a, b) => (a.priority || 99) - (b.priority || 99));

    for (const spec of specs) {
      const pool = documents
        .filter((d) => (d.doc_type === "sumula" || d.doc_type === "jurisprudencia") && spec.filter(d))
        .filter((d) => {
          const id = d.lex_route_id || d.external_id;
          if (seen.has(id)) return false;
          seen.add(id);
          return true;
        })
        .sort((a, b) => temaNumero(a) - temaNumero(b) || (a.title || "").localeCompare(b.title || ""));
      const cap = spec.limit > 0 ? spec.limit : pool.length;
      const slice = pool.slice(0, cap);
      for (const doc of slice) {
        items.push({
          group: spec.label,
          docId: doc.lex_route_id || doc.external_id,
          title: doc.title || spec.label,
        });
      }
    }
    return items;
  }

  function resolveFlashcardDecks(allDecks, career) {
    const slugs = career.flashcardSlugs || [];
    return slugs
      .map((slug) => allDecks.find((d) => d.slug === slug))
      .filter(Boolean)
      .map((d) => ({
        slug: d.slug,
        name: d.name,
        cardCount: window.LexData?.deckCardCount?.(d) ?? d.cardCount ?? d.cards?.length ?? 0,
      }));
  }

  function addDays(isoDate, n) {
    const d = new Date(isoDate + "T12:00:00");
    d.setDate(d.getDate() + n);
    return d.toISOString().slice(0, 10);
  }

  /**
   * Cronograma por norma (padrão de planos de lei seca): esgota cada lei antes da próxima,
   * na ordem do edital (prioridade das specs).
   */
  function distributeLegisSequential(queue, days, perDay, chunkMax = LEGIS_CHUNK_MAX) {
    const schedule = Array.from({ length: days }, () => []);
    if (!queue.length || perDay <= 0) return schedule;

    let dayIdx = 0;
    let usedToday = 0;

    const pushChunk = (st, take) => {
      schedule[dayIdx].push({
        ...st.item,
        units: take,
        offset: st.offset,
        count: take,
      });
      st.offset += take;
      st.remaining -= take;
      usedToday += take;
    };

    for (const item of queue) {
      const st = { item, remaining: item.units, offset: 0 };
      while (st.remaining > 0) {
        if (dayIdx >= days) dayIdx = days - 1;
        if (usedToday >= perDay) {
          dayIdx += 1;
          usedToday = 0;
          if (dayIdx >= days) dayIdx = days - 1;
        }
        const slot = perDay - usedToday;
        const take = Math.max(1, Math.min(st.remaining, chunkMax, slot > 0 ? slot : chunkMax));
        pushChunk(st, take);
        if (usedToday >= perDay) {
          dayIdx += 1;
          usedToday = 0;
        }
      }
    }

    return schedule;
  }

  /** Distribui em rodízio entre itens da fila (intercala disciplinas ao longo do dia). */
  function distributeQueueInterleaved(queue, days, perDay, chunkMax = LEGIS_CHUNK_MAX) {
    const schedule = Array.from({ length: days }, () => []);
    if (!queue.length || perDay <= 0) return schedule;

    const states = queue.map((item) => ({
      item,
      remaining: item.units,
      offset: 0,
    }));

    const pushChunk = (dayIndex, st, take) => {
      schedule[dayIndex].push({
        ...st.item,
        units: take,
        offset: st.offset,
        count: take,
      });
      st.offset += take;
      st.remaining -= take;
    };

    const activeStates = () => states.filter((s) => s.remaining > 0);

    for (let d = 0; d < days; d++) {
      let used = 0;
      while (used < perDay && activeStates().length > 0) {
        const active = activeStates();
        const bite = Math.max(1, Math.min(chunkMax, Math.ceil((perDay - used) / active.length)));
        for (const st of active) {
          if (used >= perDay) break;
          const take = Math.min(st.remaining, bite, perDay - used);
          if (take > 0) {
            pushChunk(d, st, take);
            used += take;
          }
        }
      }
    }

    for (const st of states) {
      if (st.remaining <= 0) continue;
      let d = days - 1;
      while (st.remaining > 0 && d >= 0) {
        const used = schedule[d].reduce((s, x) => s + x.units, 0);
        const slot = perDay - used;
        if (slot <= 0) {
          d -= 1;
          continue;
        }
        pushChunk(d, st, Math.min(st.remaining, slot));
      }
      if (st.remaining > 0) pushChunk(days - 1, st, st.remaining);
    }

    return schedule;
  }

  /** Intercala grupos (ex.: súmulas STF / STJ / temas) ao distribuir jurisprudência. */
  function distributeJurisInterleaved(jurisQueue, days, perDay) {
    const schedule = Array.from({ length: days }, () => []);
    if (!jurisQueue.length || perDay <= 0) return schedule;

    const pools = [];
    const byGroup = new Map();
    for (const j of jurisQueue) {
      const g = j.group || "Jurisprudência";
      if (!byGroup.has(g)) byGroup.set(g, []);
      byGroup.get(g).push(j);
    }
    for (const pool of byGroup.values()) pools.push(pool);

    let day = 0;
    let guard = 0;
    const maxGuard = jurisQueue.length * pools.length + days * 2;

    while (pools.some((p) => p.length) && guard++ < maxGuard) {
      for (const pool of pools) {
        if (!pool.length) continue;
        while (day < days && schedule[day].length >= perDay) day += 1;
        if (day >= days) {
          day = days - 1;
          break;
        }
        const item = pool.shift();
        schedule[day].push({ ...item, units: 1, offset: 0, count: 1 });
      }
      if (day < days - 1 && schedule[day].length >= perDay) day += 1;
    }

    for (const pool of pools) {
      while (pool.length) {
        let d = days - 1;
        while (d >= 0 && schedule[d].length >= perDay) d -= 1;
        if (d < 0) d = days - 1;
        const item = pool.shift();
        schedule[d].push({ ...item, units: 1, offset: 0, count: 1 });
      }
    }

    return schedule;
  }

  function buildLegisQueue(legisResolved) {
    const queue = [];
    for (const law of legisResolved) {
      queue.push({
        kind: "legis",
        lawId: law.docId,
        title: law.title,
        specLabel: law.specLabel,
        units: law.articles,
        totalArticles: law.articles,
      });
    }
    return queue;
  }

  function buildJurisQueue(jurisResolved) {
    return jurisResolved.map((j) => ({
      kind: "juris",
      docId: j.docId,
      title: j.title,
      group: j.group,
      units: 1,
    }));
  }

  function generatePlan({
    careerId,
    totalDays,
    startDate,
    documents,
    decks,
    uf = "geral",
    questoesPerDay = 6,
  }) {
    const career = CAREERS.find((c) => c.id === careerId);
    if (!career) throw new Error("Carreira não encontrada");

    const days = Math.max(14, Math.min(365, parseInt(totalDays, 10) || career.defaultDays));
    const start = startDate || new Date().toISOString().slice(0, 10);
    const ufKey = UF_PROFILES[uf] ? uf : "geral";
    const ufProfile = UF_PROFILES[ufKey];

    const legisResolved = resolveLegis(documents, career);
    const jurisResolved = resolveJuris(documents, career);
    const flashDecks = resolveFlashcardDecks(decks, career);
    const questionPool = filterQuestions(documents, careerId, ufKey);
    const totalLegisArticles = legisResolved.reduce((s, l) => s + l.articles, 0);
    const totalJuris = jurisResolved.length;
    const totalFlashCards = flashDecks.reduce((s, d) => s + d.cardCount, 0);

    const legisMinPerDay = career.legisMinPerDay ?? LEGIS_DAILY_MIN;
    const daily = computeDailyTargets({
      days,
      totalLegisArticles,
      totalJuris,
      totalFlashCards,
      questionPoolSize: questionPool.length,
      questoesPerDayPreferred: questoesPerDay,
      legisMinPerDay,
    });
    const legisPerDay = daily.legisPerDay;
    const jurisPerDay = daily.jurisPerDay;
    const flashPerDay = daily.flashPerDay;
    const qPerDay = daily.questoesPerDay;
    const legisChunkMax = career.legisChunkMax ?? daily.legisChunkMax;
    const totalQuestoes = daily.totalQuestoesPlanned;

    const legisQueue = buildLegisQueue(legisResolved);
    const jurisQueue = buildJurisQueue(jurisResolved);

    const legisSchedule = distributeLegisSequential(legisQueue, days, legisPerDay, legisChunkMax);
    const jurisSchedule = distributeJurisInterleaved(jurisQueue, days, jurisPerDay);
    const questoesSchedule = qPerDay
      ? distributeQuestionTasks(questionPool.slice(0, totalQuestoes), days, qPerDay)
      : Array.from({ length: days }, () => []);

    const flashSchedule = Array.from({ length: days }, () => []);
    if (flashDecks.length && flashPerDay > 0) {
      const deckState = flashDecks.map((d) => ({
        slug: d.slug,
        name: d.name,
        remaining: d.cardCount,
      }));
      let issued = 0;
      for (let d = 0; d < days && issued < totalFlashCards; d++) {
        let used = 0;
        while (used < flashPerDay && issued < totalFlashCards) {
          const active = deckState.filter((x) => x.remaining > 0);
          if (!active.length) break;
          const bite = Math.max(5, Math.ceil((flashPerDay - used) / active.length));
          for (const deck of active) {
            if (used >= flashPerDay || issued >= totalFlashCards) break;
            const take = Math.min(deck.remaining, bite, flashPerDay - used, totalFlashCards - issued);
            if (take <= 0) continue;
            const existing = flashSchedule[d].find((x) => x.slug === deck.slug);
            if (existing) existing.count += take;
            else flashSchedule[d].push({ slug: deck.slug, name: deck.name, count: take });
            deck.remaining -= take;
            used += take;
            issued += take;
          }
        }
      }
    }

    const trail = [];
    for (let i = 0; i < days; i++) {
      const legisTasks = (legisSchedule[i] || []).map((t) => ({
        type: "legis",
        docId: t.lawId,
        title: t.title,
        specLabel: t.specLabel,
        articleFrom: t.offset + 1,
        articleTo: t.offset + t.count,
        articleCount: t.count,
        taskId: `legis:${t.lawId}:${t.offset}`,
      }));
      const jurisTasks = (jurisSchedule[i] || []).map((t) => ({
        type: "juris",
        docId: t.docId,
        title: t.title,
        group: t.group,
        taskId: `juris:${t.docId}`,
      }));
      const flashTasks = (flashSchedule[i] || []).map((t, fi) => ({
        type: "flashcards",
        slug: t.slug,
        name: t.name,
        count: t.count,
        taskId: `flash:${t.slug}:${i}:${fi}`,
      }));
      const questoesTasks = (questoesSchedule[i] || []).map((t, qi) => ({
        type: "questoes",
        docId: t.docId,
        title: t.title,
        materia: t.materia,
        banca: t.banca,
        questaoTipo: t.tipo,
        taskId: `questao:${t.docId}:${i}:${qi}`,
      }));

      trail.push({
        day: i + 1,
        date: addDays(start, i),
        legisTasks,
        jurisTasks,
        flashTasks,
        questoesTasks,
        articlesTarget: legisTasks.reduce((s, t) => s + t.articleCount, 0),
        jurisTarget: jurisTasks.length,
        flashTarget: flashTasks.reduce((s, t) => s + t.count, 0),
        questoesTarget: questoesTasks.length,
        completedTasks: [],
      });
    }

    const missingLegis = career.legis
      .filter((spec) => !legisResolved.some((r) => r.specKey === legSpecKey(spec)))
      .map((s) => s.label);

    return {
      id: `plan-${careerId}-${Date.now()}`,
      version: PLAN_VERSION,
      careerId,
      careerLabel: career.label,
      careerDescription: career.description,
      editalFocus: career.editalFocus,
      uf: ufKey,
      ufLabel: ufProfile.label,
      ufBancas: ufProfile.bancas,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      startDate: start,
      totalDays: days,
      targets: {
        articlesPerDay: legisPerDay,
        jurisPerDay,
        flashcardsPerDay: flashPerDay,
        questoesPerDay: qPerDay,
        intensity: daily.intensity,
        totalLegisArticles,
        totalJurisItems: totalJuris,
        totalFlashcards: totalFlashCards,
        totalQuestoes,
        questionPoolSize: questionPool.length,
      },
      legisCatalog: legisResolved,
      jurisCount: totalJuris,
      flashDecks,
      missingLegis,
      trail,
    };
  }

  function loadSavedPlan() {
    if (window.LexStore?.loadStudyPlan) return window.LexStore.loadStudyPlan();
    try {
      const raw = localStorage.getItem(LS_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function savePlan(plan) {
    plan.updatedAt = new Date().toISOString();
    if (window.LexStore?.saveStudyPlan) {
      window.LexStore.saveStudyPlan(plan);
      return;
    }
    localStorage.setItem(LS_KEY, JSON.stringify(plan));
  }

  function clearPlan() {
    if (window.LexStore?.clearStudyPlan) {
      window.LexStore.clearStudyPlan();
      return;
    }
    localStorage.removeItem(LS_KEY);
  }

  function toggleTask(plan, dayIndex, taskId) {
    const day = plan.trail[dayIndex];
    if (!day) return plan;
    const set = new Set(day.completedTasks || []);
    if (set.has(taskId)) set.delete(taskId);
    else set.add(taskId);
    day.completedTasks = [...set];
    savePlan(plan);
    return plan;
  }

  function dayTasks(day) {
    return [
      ...(day.legisTasks || []),
      ...(day.jurisTasks || []),
      ...(day.flashTasks || []),
      ...(day.questoesTasks || []),
    ];
  }

  /** Agrupa legis + juris + questões na mesma etapa (intercaladas); flashcards ao final. */
  function buildDayStudyBlocks(day) {
    const legis = (day.legisTasks || []).map((t) => ({ ...t, kind: "legis" }));
    const juris = (day.jurisTasks || []).map((t) => ({ ...t, kind: "juris" }));
    const questoes = (day.questoesTasks || []).map((t) => ({ ...t, kind: "questoes" }));
    const flash = (day.flashTasks || []).map((t) => ({ ...t, kind: "flashcards" }));

    const blocks = [];
    const maxCore = Math.max(legis.length, juris.length, questoes.length, 0);

    for (let i = 0; i < maxCore; i++) {
      const items = [];
      if (legis[i]) items.push(legis[i]);
      if (juris[i]) items.push(juris[i]);
      if (questoes[i]) items.push(questoes[i]);
      if (!items.length) continue;
      const kinds = [...new Set(items.map((t) => t.kind))];
      blocks.push({
        blockId: `core:${i}`,
        label: `Etapa ${blocks.length + 1}`,
        kinds,
        items,
        taskIds: items.map((t) => t.taskId),
      });
    }

    if (flash.length) {
      blocks.push({
        blockId: "flash",
        label: "Flashcards",
        kinds: ["flashcards"],
        items: flash,
        taskIds: flash.map((t) => t.taskId),
      });
    }

    return blocks;
  }

  /** Lista plana (retrocompatível com checkboxes individuais). */
  function orderedDayTasks(day) {
    return buildDayStudyBlocks(day).flatMap((b) => b.items);
  }

  function blockIsDone(block, doneSet) {
    return block.taskIds.every((id) => doneSet.has(id));
  }

  function dayBlockProgress(day) {
    const blocks = buildDayStudyBlocks(day);
    const doneSet = new Set(day.completedTasks || []);
    const done = blocks.filter((b) => blockIsDone(b, doneSet)).length;
    return { blocks, done, total: blocks.length, doneSet };
  }

  function dayTaskProgress(day) {
    const tasks = orderedDayTasks(day);
    const doneSet = new Set(day.completedTasks || []);
    const done = tasks.filter((t) => doneSet.has(t.taskId)).length;
    return { tasks, done, total: tasks.length, doneSet };
  }

  function firstIncompleteBlock(day) {
    const { blocks, doneSet } = dayBlockProgress(day);
    const idx = blocks.findIndex((b) => !blockIsDone(b, doneSet));
    return idx >= 0 ? idx : Math.max(0, blocks.length - 1);
  }

  function firstIncompleteStep(day) {
    return firstIncompleteBlock(day);
  }

  function markBlockTasks(plan, dayIndex, taskIds) {
    const day = plan.trail[dayIndex];
    if (!day) return plan;
    const set = new Set(day.completedTasks || []);
    for (const id of taskIds) set.add(id);
    day.completedTasks = [...set];
    savePlan(plan);
    return plan;
  }

  const TASK_KIND_LABELS = {
    legis: "Legislação",
    juris: "Jurisprudência",
    questoes: "Questões",
    flashcards: "Flashcards",
  };

  function planProgress(plan) {
    let done = 0;
    let total = 0;
    for (const day of plan.trail) {
      const tasks = dayTasks(day);
      total += tasks.length;
      done += (day.completedTasks || []).length;
    }
    return { done, total, pct: total ? Math.round((done / total) * 100) : 0 };
  }

  function todayIndex(plan) {
    const today = new Date().toISOString().slice(0, 10);
    const idx = plan.trail.findIndex((d) => d.date === today);
    if (idx >= 0) return idx;
    const future = plan.trail.findIndex((d) => d.date > today);
    return future >= 0 ? future : plan.trail.length - 1;
  }

  window.LexStudyPlans = {
    PLAN_VERSION,
    CAREERS,
    UF_PROFILES,
    CAREER_QUESTAO,
    getCareer: (id) => CAREERS.find((c) => c.id === id),
    getUfProfile: (uf) => UF_PROFILES[uf] || UF_PROFILES.geral,
    resolveLegis,
    resolveJuris,
    resolveFlashcardDecks,
    filterQuestions,
    generatePlan,
    computeDailyTargets,
    studyDaysIntensity,
    loadSavedPlan,
    savePlan,
    clearPlan,
    toggleTask,
    planProgress,
    todayIndex,
    dayTasks,
    buildDayStudyBlocks,
    orderedDayTasks,
    dayBlockProgress,
    dayTaskProgress,
    firstIncompleteBlock,
    firstIncompleteStep,
    markBlockTasks,
    blockIsDone,
    TASK_KIND_LABELS,
  };
})();
