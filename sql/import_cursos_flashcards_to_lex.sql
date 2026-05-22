-- Sincroniza flashcards do NaIntegra Cursos (public.flashcards) → schema lex (Lex web).
-- Reaplicável: apaga decks/cards lex e reimporta por disciplina.

BEGIN;

DELETE FROM lex.flashcards;
DELETE FROM lex.flashcard_decks;

INSERT INTO lex.flashcard_decks (slug, name, category, sort_order) VALUES
  ('dir-const', 'Direito Constitucional', 'Direito Público', 1),
  ('dir-proc-civil', 'Direito Processual Civil', 'Processo', 2),
  ('dir-adm', 'Direito Administrativo', 'Direito Público', 3),
  ('dir-penal-geral', 'Direito Penal - Parte Geral', 'Direito Público', 4),
  ('dir-civil-obrig', 'Direito Civil - Obrigações e Contratos', 'Direito Privado', 5),
  ('dir-eleitoral', 'Direito Eleitoral', 'Direito Público', 6),
  ('jurisprudencia', 'Jurisprudência', 'Jurisprudência', 7),
  ('dir-civil-geral', 'Direito Civil - Parte Geral', 'Direito Privado', 8),
  ('dir-penal-especial', 'Direito Penal - Parte Especial', 'Direito Público', 9),
  ('dir-financeiro', 'Direito Financeiro', 'Direito Público', 10),
  ('tutela-coletiva', 'Tutela Coletiva e Direito Processual Coletivo', 'Processo', 11),
  ('lei-improbidade', 'Lei de Improbidade Administrativa', 'Direito Público', 12),
  ('dir-economico', 'Direito Econômico', 'Direito Público', 13),
  ('dir-previdenciario', 'Direito Previdenciário', 'Direito Privado', 14);

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
