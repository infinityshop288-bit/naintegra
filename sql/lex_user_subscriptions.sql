-- Assinaturas NaIntegra Lex (mensal R$ 19,90 / anual R$ 199,90)

CREATE TABLE IF NOT EXISTS lex.user_subscriptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  plan_id text NOT NULL REFERENCES lex.subscription_plans (id),
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'active', 'expired', 'cancelled')),
  provider text CHECK (provider IN ('mercadopago', 'stripe')),
  payment_id text,
  amount_cents integer NOT NULL,
  starts_at timestamptz,
  expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lex_user_subscriptions_user
  ON lex.user_subscriptions (user_id, status);

CREATE UNIQUE INDEX IF NOT EXISTS idx_lex_user_subscriptions_payment
  ON lex.user_subscriptions (payment_id)
  WHERE payment_id IS NOT NULL;

ALTER TABLE lex.user_subscriptions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS lex_user_subscriptions_select_own ON lex.user_subscriptions;
CREATE POLICY lex_user_subscriptions_select_own
  ON lex.user_subscriptions FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS lex_user_subscriptions_service_all ON lex.user_subscriptions;
CREATE POLICY lex_user_subscriptions_service_all
  ON lex.user_subscriptions FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Planos Lex (preços solicitados)
INSERT INTO lex.subscription_plans (id, name, price_cents, features, active)
VALUES
  (
    'lex-mensal',
    'Lex Mensal',
    1990,
    '["Legislação completa","Jurisprudência","Flashcards","Questões","Sync multi-device"]'::jsonb,
    true
  ),
  (
    'lex-anual',
    'Lex Anual',
    19990,
    '["Tudo do mensal","2 meses grátis","Suporte prioritário"]'::jsonb,
    true
  )
ON CONFLICT (id) DO UPDATE SET
  name = EXCLUDED.name,
  price_cents = EXCLUDED.price_cents,
  features = EXCLUDED.features,
  active = EXCLUDED.active;

-- Metadados públicos de atualização do acervo
CREATE TABLE IF NOT EXISTS lex.content_metadata (
  key text PRIMARY KEY,
  value timestamptz NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO lex.content_metadata (key, value)
VALUES ('last_content_update', now())
ON CONFLICT (key) DO NOTHING;

ALTER TABLE lex.content_metadata ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS lex_content_metadata_anon_read ON lex.content_metadata;
CREATE POLICY lex_content_metadata_anon_read
  ON lex.content_metadata FOR SELECT
  TO anon, authenticated
  USING (true);

GRANT SELECT ON lex.content_metadata TO anon, authenticated;
GRANT SELECT ON lex.subscription_plans TO anon, authenticated;
