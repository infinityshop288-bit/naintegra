-- Plano de estudos personalizado (NaIntegra Lex — sync multi-dispositivo)
CREATE TABLE IF NOT EXISTS lex.user_study_plans (
  user_id uuid NOT NULL PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
  career_id text NOT NULL,
  uf text,
  plan_payload jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS user_study_plans_updated_idx
  ON lex.user_study_plans (user_id, updated_at DESC);

ALTER TABLE lex.user_study_plans ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS user_study_plans_own ON lex.user_study_plans;
CREATE POLICY user_study_plans_own ON lex.user_study_plans
  FOR ALL TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON lex.user_study_plans TO authenticated;

CREATE OR REPLACE FUNCTION lex.touch_user_study_plans_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS user_study_plans_updated_at ON lex.user_study_plans;
CREATE TRIGGER user_study_plans_updated_at
  BEFORE UPDATE ON lex.user_study_plans
  FOR EACH ROW EXECUTE FUNCTION lex.touch_user_study_plans_updated_at();
