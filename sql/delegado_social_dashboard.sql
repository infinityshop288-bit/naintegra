-- Dashboard @delegadoluizcarlos — schema delegado (Supabase)
-- Acesso restrito: infinity.shop288@gmail.com (configurável via DELEGADO_ALLOWED_EMAILS)

CREATE SCHEMA IF NOT EXISTS delegado;

GRANT USAGE ON SCHEMA delegado TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA delegado TO anon, authenticated, service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA delegado TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA delegado
  GRANT ALL ON TABLES TO anon, authenticated, service_role;

CREATE OR REPLACE FUNCTION delegado.is_allowed_dashboard_user()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = delegado, public, auth
AS $$
  SELECT lower(coalesce(auth.jwt() ->> 'email', '')) IN (
    'infinity.shop288@gmail.com'
  );
$$;

CREATE TABLE IF NOT EXISTS delegado.content_queue (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  titulo text NOT NULL,
  formato text NOT NULL DEFAULT 'carrossel',
  legenda text NOT NULL DEFAULT '',
  hashtags text[] NOT NULL DEFAULT '{}',
  media_url text,
  scheduled_at timestamptz,
  status text NOT NULL DEFAULT 'rascunho',
  created_by uuid REFERENCES auth.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS delegado.automations (
  id text PRIMARY KEY,
  nome text NOT NULL,
  categoria text NOT NULL DEFAULT 'conteudo',
  status text NOT NULL DEFAULT 'pausado',
  config jsonb NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS delegado.insight_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  seguidores integer,
  alcance numeric,
  engajamento numeric,
  views numeric,
  raw jsonb NOT NULL DEFAULT '{}',
  captured_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS delegado.comment_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  media_id text,
  comment_id text,
  username text,
  text text,
  replied boolean NOT NULL DEFAULT false,
  captured_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE delegado.content_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE delegado.automations ENABLE ROW LEVEL SECURITY;
ALTER TABLE delegado.insight_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE delegado.comment_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY content_queue_select ON delegado.content_queue
  FOR SELECT TO authenticated USING (delegado.is_allowed_dashboard_user());
CREATE POLICY content_queue_insert ON delegado.content_queue
  FOR INSERT TO authenticated WITH CHECK (delegado.is_allowed_dashboard_user());
CREATE POLICY content_queue_update ON delegado.content_queue
  FOR UPDATE TO authenticated USING (delegado.is_allowed_dashboard_user());
CREATE POLICY content_queue_delete ON delegado.content_queue
  FOR DELETE TO authenticated USING (delegado.is_allowed_dashboard_user());

CREATE POLICY automations_select ON delegado.automations
  FOR SELECT TO authenticated USING (delegado.is_allowed_dashboard_user());
CREATE POLICY automations_insert ON delegado.automations
  FOR INSERT TO authenticated WITH CHECK (delegado.is_allowed_dashboard_user());
CREATE POLICY automations_update ON delegado.automations
  FOR UPDATE TO authenticated USING (delegado.is_allowed_dashboard_user());

CREATE POLICY insight_snapshots_all ON delegado.insight_snapshots
  FOR ALL TO authenticated USING (delegado.is_allowed_dashboard_user());

CREATE POLICY comment_events_all ON delegado.comment_events
  FOR ALL TO authenticated USING (delegado.is_allowed_dashboard_user());

-- Seed automações (hipóteses vencedoras)
INSERT INTO delegado.automations (id, nome, categoria, status) VALUES
  ('caso-pratico-semanal', 'Carrossel Caso Prático Semanal', 'conteudo', 'ativo'),
  ('reels-erro-prova', 'Reels — Erro Comum em Prova', 'conteudo', 'ativo'),
  ('story-quiz', 'Story Quiz Interativo', 'engajamento', 'ativo'),
  ('lead-magnet-dm', 'Lead Magnet via DM/Comentário', 'conversao', 'ativo'),
  ('retargeting-cursos', 'Retargeting Meta Ads — Visitantes Lex', 'ads', 'pausado'),
  ('gap-concorrentes', 'Gap de Conteúdo vs Concorrentes', 'inteligencia', 'ativo'),
  ('horario-otimo', 'Agendamento no Horário Ótimo', 'publicacao', 'ativo'),
  ('faq-comentarios', 'Resposta FAQ em Comentários', 'monitoramento', 'ativo'),
  ('noticia-juridica-rapida', 'Resposta Rápida a Notícia Jurídica', 'conteudo', 'pausado'),
  ('depoimento-aluno', 'Republicação Depoimento Aprovado', 'social_proof', 'pausado'),
  ('whatsapp-broadcast-semanal', 'Broadcast WhatsApp — Resumo da Semana', 'conversao', 'pausado'),
  ('youtube-shorts-crosspost', 'Crosspost YouTube Shorts → Reels', 'distribuicao', 'pausado')
ON CONFLICT (id) DO NOTHING;

-- Expor schema delegado na API REST (Supabase Dashboard → Settings → API → Exposed schemas)
COMMENT ON SCHEMA delegado IS 'Dashboard Meta @delegadoluizcarlos — acesso restrito';
