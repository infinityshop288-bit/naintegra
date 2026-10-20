-- Catálogo enriquecido das provas jurídicas (juiz, promotor, defensor, procurador).
-- Leitura anônima, como o restante do acervo Lex.

CREATE TABLE IF NOT EXISTS public.provas_juridicas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id text,
  doc_type text NOT NULL CHECK (doc_type IN ('questoes_objetivas', 'questoes_subjetivas')),
  carreiras_prova text[] NOT NULL,
  carreira_origem text,
  banca text,
  ano int,
  disciplina text,
  enunciado text NOT NULL,
  alternativas jsonb,
  gabarito_banca text,
  resposta_banca text,
  resposta_ia text,
  dispositivos jsonb NOT NULL DEFAULT '[]'::jsonb,
  jurisprudencia jsonb NOT NULL DEFAULT '[]'::jsonb,
  elaboracao text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS provas_juridicas_ano_idx ON public.provas_juridicas (ano);
CREATE INDEX IF NOT EXISTS provas_juridicas_carreiras_idx ON public.provas_juridicas USING gin (carreiras_prova);

ALTER TABLE public.provas_juridicas ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Anon can read provas_juridicas" ON public.provas_juridicas;
CREATE POLICY "Anon can read provas_juridicas"
ON public.provas_juridicas
FOR SELECT
TO anon, authenticated
USING (true);
