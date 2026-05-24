-- Deck Direito Processual Penal + reclassificação de cards CPP já publicados no Lex.

INSERT INTO lex.flashcard_decks (slug, name, category, sort_order)
VALUES ('dir-proc-penal', 'Direito Processual Penal', 'Processo', 3)
ON CONFLICT (slug) DO UPDATE
SET name = EXCLUDED.name,
    category = EXCLUDED.category,
    sort_order = EXCLUDED.sort_order;

UPDATE lex.flashcard_decks
SET sort_order = sort_order + 1
WHERE slug <> 'dir-proc-penal'
  AND sort_order >= 3;

WITH target AS (
  SELECT id FROM lex.flashcard_decks WHERE slug = 'dir-proc-penal'
),
candidates AS (
  SELECT f.id
  FROM lex.flashcards f
  WHERE f.deck_id <> (SELECT id FROM target)
    AND (
      f.front ILIKE '%cpp%'
      OR f.front ILIKE '%processo penal%'
      OR f.front ILIKE '%processual penal%'
      OR f.back ILIKE '%cpp:%'
      OR f.back ILIKE '%código de processo penal%'
      OR f.back ILIKE '%codigo de processo penal%'
      OR f.back ILIKE '%processual penal%'
      OR f.back ~* '\mCPP\M[|:]'
    )
),
numbered AS (
  SELECT
    c.id,
    row_number() OVER (ORDER BY c.id) AS new_sort
  FROM candidates c
)
UPDATE lex.flashcards f
SET
  deck_id = (SELECT id FROM target),
  sort_order = n.new_sort
FROM numbered n
WHERE f.id = n.id;
