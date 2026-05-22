-- Grifos HTML e anotações por bloco (leis, jurisprudência, flashcards)
CREATE TABLE IF NOT EXISTS lex.user_content_marks (
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  doc_type text NOT NULL CHECK (doc_type IN ('legislacao', 'jurisprudencia', 'flashcard')),
  doc_id text NOT NULL,
  block_key text NOT NULL DEFAULT '',
  highlight_html text,
  note_text text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, doc_type, doc_id, block_key)
);

ALTER TABLE lex.user_content_marks ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_content_marks_own ON lex.user_content_marks
  FOR ALL TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON lex.user_content_marks TO authenticated;

CREATE INDEX IF NOT EXISTS user_content_marks_user_updated_idx
  ON lex.user_content_marks (user_id, updated_at DESC);
