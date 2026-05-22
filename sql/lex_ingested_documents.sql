-- Tabela de ingestão unificada para o agente NaIntegra Lex.
-- Execute no projeto Supabase do NaIntegra, schema `lex`.
-- Ajuste políticas RLS conforme seu modelo de auth (service role do agente costuma bypassar RLS).

create schema if not exists lex;

create table if not exists lex.ingested_documents (
  id uuid primary key default gen_random_uuid(),
  external_id text not null,
  doc_type text not null check (doc_type in ('legislacao', 'jurisprudencia', 'sumula', 'questoes_objetivas', 'questoes_subjetivas')),
  source_system text,
  title text,
  body text,
  meta jsonb not null default '{}'::jsonb,
  organized jsonb not null default '{}'::jsonb,
  crawl_batch_id text,
  content_hash text,
  ingested_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (external_id)
);

create index if not exists ingested_documents_doc_type_idx
  on lex.ingested_documents (doc_type);

create index if not exists ingested_documents_source_idx
  on lex.ingested_documents (source_system);

create index if not exists ingested_documents_ingested_at_idx
  on lex.ingested_documents (ingested_at desc);

-- Full-text em português (opcional; exige extensão unaccent no projeto)
-- create extension if not exists unaccent;
-- alter table lex.ingested_documents
--   add column if not exists search_vector tsvector generated always as (
--     setweight(to_tsvector('portuguese', coalesce(title, '')), 'A')
--     || setweight(to_tsvector('portuguese', coalesce(body, '')), 'B')
--   ) stored;
-- create index if not exists ingested_documents_search_idx on lex.ingested_documents using gin (search_vector);

create or replace function lex.touch_ingested_documents_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists ingested_documents_updated_at on lex.ingested_documents;
create trigger ingested_documents_updated_at
  before update on lex.ingested_documents
  for each row execute function lex.touch_ingested_documents_updated_at();
