-- Extensão fila @delegadoluizcarlos — aprovação manual + metadados IA (Zamboni)

ALTER TABLE delegado.content_queue
  ADD COLUMN IF NOT EXISTS meta jsonb NOT NULL DEFAULT '{}';

COMMENT ON COLUMN delegado.content_queue.meta IS
  'gancho, roteiro_falas, slides, slot_id, ai_provider, requires_manual_publish';

-- Status sugeridos: rascunho | aguardando_aprovacao | aprovado | agendado | publicado | rejeitado
