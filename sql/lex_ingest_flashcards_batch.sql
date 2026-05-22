-- RPC para ingestão em lote de flashcards (verbetes / scripts de automação).
-- Chamada: POST /rest/v1/rpc/ingest_flashcards_batch  (Content-Profile: lex)
-- Body: {"rows":[{"discipline":"Direito Administrativo","front":"...","back":"...","highlight":null}]}

CREATE OR REPLACE FUNCTION lex.ingest_flashcards_batch(rows jsonb)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = lex, public
AS $$
DECLARE
  item jsonb;
  deck uuid;
  next_sort int;
  inserted int := 0;
  discipline text;
BEGIN
  FOR item IN SELECT * FROM jsonb_array_elements(rows)
  LOOP
    discipline := item->>'discipline';
    SELECT id INTO deck FROM lex.flashcard_decks WHERE name = discipline;
    IF deck IS NULL THEN
      SELECT id INTO deck FROM lex.flashcard_decks WHERE name = 'Direito Administrativo';
    END IF;
    SELECT COALESCE(MAX(sort_order), 0) + 1 INTO next_sort FROM lex.flashcards WHERE deck_id = deck;
    INSERT INTO lex.flashcards (deck_id, front, back, highlight, sort_order)
    VALUES (
      deck,
      item->>'front',
      item->>'back',
      NULLIF(item->>'highlight', 'null'),
      next_sort
    );
    inserted := inserted + 1;
  END LOOP;
  RETURN inserted;
END;
$$;

GRANT EXECUTE ON FUNCTION lex.ingest_flashcards_batch(jsonb) TO anon, authenticated, service_role;
