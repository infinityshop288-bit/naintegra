-- Comentários públicos em questões (visíveis a todos; cada usuário edita o próprio)
CREATE TABLE IF NOT EXISTS lex.questao_comentarios (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  question_id text NOT NULL,
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  author_name text NOT NULL DEFAULT 'Estudante',
  body text NOT NULL CHECK (char_length(trim(body)) > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (question_id, user_id)
);

CREATE INDEX IF NOT EXISTS questao_comentarios_question_idx
  ON lex.questao_comentarios (question_id, created_at ASC);

ALTER TABLE lex.questao_comentarios ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS questao_comentarios_public_read ON lex.questao_comentarios;
CREATE POLICY questao_comentarios_public_read ON lex.questao_comentarios
  FOR SELECT TO anon, authenticated
  USING (true);

DROP POLICY IF EXISTS questao_comentarios_insert_own ON lex.questao_comentarios;
CREATE POLICY questao_comentarios_insert_own ON lex.questao_comentarios
  FOR INSERT TO authenticated
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS questao_comentarios_update_own ON lex.questao_comentarios;
CREATE POLICY questao_comentarios_update_own ON lex.questao_comentarios
  FOR UPDATE TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS questao_comentarios_delete_own ON lex.questao_comentarios;
CREATE POLICY questao_comentarios_delete_own ON lex.questao_comentarios
  FOR DELETE TO authenticated
  USING (auth.uid() = user_id);

GRANT SELECT ON lex.questao_comentarios TO anon, authenticated;
GRANT INSERT, UPDATE, DELETE ON lex.questao_comentarios TO authenticated;

CREATE OR REPLACE FUNCTION lex.touch_questao_comentarios_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS questao_comentarios_updated_at ON lex.questao_comentarios;
CREATE TRIGGER questao_comentarios_updated_at
  BEFORE UPDATE ON lex.questao_comentarios
  FOR EACH ROW EXECUTE FUNCTION lex.touch_questao_comentarios_updated_at();

-- Comentários de questão não usam marcas privadas por usuário
ALTER TABLE lex.user_content_marks DROP CONSTRAINT IF EXISTS user_content_marks_doc_type_check;
ALTER TABLE lex.user_content_marks ADD CONSTRAINT user_content_marks_doc_type_check CHECK (
  doc_type IN ('legislacao', 'jurisprudencia', 'flashcard')
);
