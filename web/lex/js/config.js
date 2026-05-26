/** Configuração pública do NaIntegra Lex (anon key — segura no browser). */
window.LEX_CONFIG = {
  /** Origem canônica do Lex (OAuth PKCE — deve estar em Supabase → Redirect URLs). */
  siteOrigin: "https://www.naintegracursos.com.br",
  lexPublicPath: "/lex/",
  oauthCallbackUrl: "https://www.naintegracursos.com.br/lex/auth-callback.html",
  supabaseUrl: "https://voybsggeedpwcfdadnzt.supabase.co",
  supabaseAnonKey:
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZveWJzZ2dlZWRwd2NmZGFkbnp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNzU2MTQsImV4cCI6MjA4ODc1MTYxNH0.dy5AgSd1VWdP4WLGXy5V89pA4jgHijngHJjScApOo70",
  /** Flashcards continuam no schema lex. Conteúdo normativo vem de public.norma_chunks (normas.py). */
  lexSchema: "lex",
  normaSources: {
    legislacao: ["planalto", "rideel_vademecum"],
    jurisprudencia: ["trilhante_informativo"],
  },
  corpusFallback: "./data/corpus.json",
  legisCatalogFallback: "./data/legis_catalog.json",
  legisBodiesFallback: "./data/legis_bodies.json",
  legisSummariesFallback: "./data/legis_summaries.json",
  legisKnownMetaFallback: "./data/legis_known_meta.json",
  flashcardsFallback: "./data/flashcards.json",
  flashcardsPageSize: 1000,
  jurisBodiesFallback: "./data/juris_bodies.json",
  sumulasCatalogFallback: "./data/sumulas_catalog.json",
  temasCatalogFallback: "./data/temas_catalog.json",
  /** Banco de questões do NaIntegra Cursos (public.questoes_banco). */
  questionsTable: "questoes_banco",
  questionsPageSize: 1000,
  questoesCatalogFallback: "./data/questoes_catalog.json",
  contactEmail: "contato@naintegracursos.com.br",
  accountDeletionUrl: "https://www.naintegracursos.com.br/lex/#/excluir-conta",
  /** Fallback se content_metadata não estiver disponível. */
  lastContentUpdate: "2026-05-19T00:00:00Z",
  /** Rotas acessíveis sem assinatura ativa. */
  publicRoutes: ["assinatura", "contato", "excluir-conta", "auth"],
  subscriptionPlans: {
    "lex-mensal": { label: "Mensal", price: 19.9 },
    "lex-anual": { label: "Anual", price: 199.9 },
  },
};
