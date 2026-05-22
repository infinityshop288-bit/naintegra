-- Permite leitura anônima do banco de questões (NaIntegra Cursos → NaIntegra Lex web).
-- A política "Anyone can read questoes_banco" existente aplica-se só ao role authenticated.

CREATE POLICY IF NOT EXISTS "Anon can read questoes_banco"
ON public.questoes_banco
FOR SELECT
TO anon
USING (true);
