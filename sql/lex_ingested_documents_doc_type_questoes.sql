-- Amplia doc_type para questões de banca (objetivas / discursivas).
-- Execute no mesmo projeto Supabase onde já existe lex.ingested_documents.

alter table lex.ingested_documents drop constraint if exists ingested_documents_doc_type_check;

alter table lex.ingested_documents add constraint ingested_documents_doc_type_check check (
  doc_type in (
    'legislacao',
    'jurisprudencia',
    'sumula',
    'questoes_objetivas',
    'questoes_subjetivas',
    'doutrina'
  )
);
