-- Sincroniza flashcards do NaIntegra Cursos (public.flashcards) → schema lex (Lex web).
-- Reaplicável: apaga decks/cards lex e reimporta por disciplina.

BEGIN;

DELETE FROM lex.flashcards;
DELETE FROM lex.flashcard_decks;

INSERT INTO lex.flashcard_decks (slug, name, category, sort_order) VALUES
  ('dir-const', 'Direito Constitucional', 'Direito Público', 1),
  ('dir-proc-civil', 'Direito Processual Civil', 'Processo', 2),
  ('dir-proc-penal', 'Direito Processual Penal', 'Processo', 3),
  ('dir-adm', 'Direito Administrativo', 'Direito Público', 4),
  ('dir-penal-geral', 'Direito Penal - Parte Geral', 'Direito Público', 5),
  ('dir-civil-obrig', 'Direito Civil - Obrigações e Contratos', 'Direito Privado', 6),
  ('dir-eleitoral', 'Direito Eleitoral', 'Direito Público', 7),
  ('jurisprudencia', 'Jurisprudência', 'Jurisprudência', 8),
  ('dir-civil-geral', 'Direito Civil - Parte Geral', 'Direito Privado', 9),
  ('dir-penal-especial', 'Direito Penal - Parte Especial', 'Direito Público', 10),
  ('dir-financeiro', 'Direito Financeiro', 'Direito Público', 11),
  ('tutela-coletiva', 'Tutela Coletiva e Direito Processual Coletivo', 'Processo', 12),
  ('lei-improbidade', 'Lei de Improbidade Administrativa', 'Direito Público', 13),
  ('dir-economico', 'Direito Econômico', 'Direito Público', 14),
  ('dir-previdenciario', 'Direito Previdenciário', 'Direito Privado', 15),
  ('licitacoes-lei-14133', 'Licitações — Lei 14.133/2021', 'Direito Administrativo', 16);

INSERT INTO lex.flashcards (deck_id, front, back, highlight, sort_order)
SELECT
  d.id,
  f.front,
  f.back,
  NULLIF(substring(f.back FROM '<mark>([^<]+)</mark>'), ''),
  row_number() OVER (PARTITION BY d.id ORDER BY f.created_at, f.id)
FROM public.flashcards f
JOIN lex.flashcard_decks d ON d.name = f.discipline;

COMMIT;
