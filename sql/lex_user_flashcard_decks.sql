-- Decks de flashcards criados pelo usuário (NaIntegra Lex — sync multi-dispositivo)
CREATE TABLE IF NOT EXISTS lex.user_flashcard_decks (
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  slug text NOT NULL,
  name text NOT NULL,
  category text NOT NULL DEFAULT 'Meus decks',
  cards jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, slug),
  CONSTRAINT user_flashcard_decks_slug_check CHECK (slug ~ '^u-[a-z0-9-]+$'),
  CONSTRAINT user_flashcard_decks_cards_array CHECK (jsonb_typeof(cards) = 'array')
);

CREATE INDEX IF NOT EXISTS user_flashcard_decks_user_updated_idx
  ON lex.user_flashcard_decks (user_id, updated_at DESC);

ALTER TABLE lex.user_flashcard_decks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_flashcard_decks_own ON lex.user_flashcard_decks;
CREATE POLICY user_flashcard_decks_own ON lex.user_flashcard_decks
  FOR ALL TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON lex.user_flashcard_decks TO authenticated;

CREATE OR REPLACE FUNCTION lex.touch_user_flashcard_decks_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS user_flashcard_decks_updated_at ON lex.user_flashcard_decks;
CREATE TRIGGER user_flashcard_decks_updated_at
  BEFORE UPDATE ON lex.user_flashcard_decks
  FOR EACH ROW EXECUTE FUNCTION lex.touch_user_flashcard_decks_updated_at();
