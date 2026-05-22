-- Padronização public.norma_chunks para NaIntegra Lex.
-- Aplica: normalize_norma_url, catálogo com doc_key estável, upsert em lote, refresh da MV.

-- ---------------------------------------------------------------------------
-- URL / doc_key canônicos
-- ---------------------------------------------------------------------------

create or replace function public.normalize_norma_url(p_url text)
returns text
language plpgsql
immutable
as $$
declare
  u text;
begin
  if p_url is null or btrim(p_url) = '' then
    return coalesce(p_url, '');
  end if;
  u := btrim(p_url);
  u := regexp_replace(u, '^http://', 'https://', 'i');
  u := lower(u);
  u := regexp_replace(u, '#.*$', '');
  u := regexp_replace(u, '/+$', '');
  return u;
end;
$$;

create or replace function public.normalize_norma_doc_key(p_url text, p_source_file text)
returns text
language sql
immutable
as $$
  select coalesce(
    nullif(btrim(public.normalize_norma_url(p_url)), ''),
    nullif(btrim(p_source_file), '')
  );
$$;

-- ---------------------------------------------------------------------------
-- Catálogo (view + MV) com doc_key normalizado
-- ---------------------------------------------------------------------------

create or replace view public.norma_document_catalog as
select
  source,
  public.normalize_norma_doc_key(url, source_file) as doc_key,
  max(public.normalize_norma_url(url)) as url,
  max(source_file) as source_file,
  count(*)::integer as chunk_count,
  (array_agg(metadata order by chunk_index))[1] as metadata
from public.norma_chunks
group by source, public.normalize_norma_doc_key(url, source_file);

grant select on public.norma_document_catalog to anon, authenticated;

drop materialized view if exists public.norma_document_catalog_mv;

create materialized view public.norma_document_catalog_mv as
select
  source,
  public.normalize_norma_doc_key(url, source_file) as doc_key,
  max(public.normalize_norma_url(url)) as url,
  max(source_file) as source_file,
  count(*)::integer as chunk_count,
  (array_agg(metadata order by chunk_index))[1] as metadata
from public.norma_chunks
group by source, public.normalize_norma_doc_key(url, source_file);

create unique index norma_document_catalog_mv_source_doc_key
  on public.norma_document_catalog_mv (source, doc_key);

grant select on public.norma_document_catalog_mv to anon, authenticated;

-- ---------------------------------------------------------------------------
-- RPCs de leitura
-- ---------------------------------------------------------------------------

create or replace function public.list_norma_document_catalog(
  p_source text default null,
  p_limit integer default 200,
  p_offset integer default 0
)
returns table(
  source text,
  doc_key text,
  url text,
  source_file text,
  chunk_count integer,
  metadata jsonb
)
language sql
stable
security invoker
as $$
  select c.source, c.doc_key, c.url, c.source_file, c.chunk_count, c.metadata
  from public.norma_document_catalog_mv c
  where p_source is null or c.source = p_source
  order by c.source, c.doc_key
  limit least(greatest(p_limit, 1), 500)
  offset greatest(p_offset, 0);
$$;

grant execute on function public.list_norma_document_catalog(text, integer, integer)
  to anon, authenticated;

create or replace function public.get_norma_document_text(
  p_source text,
  p_doc_key text
)
returns text
language sql
stable
security invoker
as $$
  select string_agg(n.text, E'\n\n' order by n.chunk_index)
  from public.norma_chunks n
  where n.source = p_source
    and public.normalize_norma_doc_key(n.url, n.source_file)
      = public.normalize_norma_doc_key(p_doc_key, p_doc_key);
$$;

grant execute on function public.get_norma_document_text(text, text) to anon, authenticated;

create or replace function public.get_norma_document_chunks(
  p_source text,
  p_url text
)
returns text
language plpgsql
stable
security invoker
as $$
declare
  candidates text[];
  u text;
  result text;
begin
  candidates := array(
    select distinct v from unnest(array[
      nullif(btrim(p_url), ''),
      nullif(btrim(public.normalize_norma_url(p_url)), ''),
      nullif(split_part(public.normalize_norma_url(p_url), '?', 1), '')
    ]) as v
    where v is not null and v <> ''
  );

  foreach u in array candidates loop
    select string_agg(n.text, E'\n\n' order by n.chunk_index)
      into result
    from public.norma_chunks n
    where n.source = p_source
      and n.url = u;

    if result is not null and btrim(result) <> '' then
      return result;
    end if;
  end loop;

  return '';
end;
$$;

grant execute on function public.get_norma_document_chunks(text, text) to anon, authenticated;

-- Índice para leitura por URL exata (Lex front / normas.py).
create index if not exists norma_chunks_source_url_idx
  on public.norma_chunks (source, url);

-- ---------------------------------------------------------------------------
-- Upsert em lote (normaliza url + metadata mínima)
-- ---------------------------------------------------------------------------

create or replace function public.upsert_norma_chunks_batch(payload jsonb)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  n integer;
begin
  with prepared as (
    select
      x->>'id' as id,
      x->>'source' as source,
      x->>'source_file' as source_file,
      public.normalize_norma_url(x->>'url') as url,
      (x->>'chunk_index')::integer as chunk_index,
      x->>'text' as text,
      coalesce(x->'metadata', '{}'::jsonb) as metadata
    from jsonb_array_elements(payload) as x
  ),
  ups as (
    insert into public.norma_chunks (id, source, source_file, url, chunk_index, text, metadata)
    select
      p.id,
      p.source,
      p.source_file,
      p.url,
      p.chunk_index,
      p.text,
      p.metadata
        || jsonb_build_object(
          'doc_key', public.normalize_norma_doc_key(p.url, p.source_file),
          'norma_schema_version', 1
        )
    from prepared p
    on conflict (id) do update set
      source = excluded.source,
      source_file = excluded.source_file,
      url = excluded.url,
      chunk_index = excluded.chunk_index,
      text = excluded.text,
      metadata = excluded.metadata
    returning 1
  )
  select count(*)::integer into n from ups;
  return n;
end;
$$;

grant execute on function public.upsert_norma_chunks_batch(jsonb) to anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Refresh da MV (chamar após ingestão)
-- ---------------------------------------------------------------------------

create or replace function public.refresh_norma_document_catalog_mv()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  refresh materialized view concurrently public.norma_document_catalog_mv;
end;
$$;

grant execute on function public.refresh_norma_document_catalog_mv() to anon, authenticated, service_role;

-- ---------------------------------------------------------------------------
-- Limpeza one-shot: URLs normalizadas + dedupe por (source, url, chunk_index)
-- ---------------------------------------------------------------------------

create or replace function public.normalize_norma_chunks_corpus()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  updated_urls integer;
  deleted_dupes integer;
begin
  update public.norma_chunks
  set url = public.normalize_norma_url(url)
  where url is distinct from public.normalize_norma_url(url);
  get diagnostics updated_urls = row_count;

  with ranked as (
    select
      id,
      row_number() over (
        partition by source, public.normalize_norma_url(url), chunk_index
        order by created_at nulls last, id
      ) as rn
    from public.norma_chunks
  )
  delete from public.norma_chunks n
  using ranked r
  where n.id = r.id and r.rn > 1;
  get diagnostics deleted_dupes = row_count;

  refresh materialized view concurrently public.norma_document_catalog_mv;

  return jsonb_build_object(
    'updated_urls', updated_urls,
    'deleted_duplicate_chunks', deleted_dupes
  );
end;
$$;

grant execute on function public.normalize_norma_chunks_corpus() to anon, authenticated, service_role;

-- Metadados mínimos derivados de source/url (titulo continua via LexLegisMeta no front).
create or replace function public.enrich_norma_chunks_metadata()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  n integer;
begin
  update public.norma_chunks c
  set metadata = c.metadata
    || jsonb_strip_nulls(jsonb_build_object(
      'norma_schema_version', 1,
      'doc_key', public.normalize_norma_doc_key(c.url, c.source_file),
      'doc_type', case
        when c.source in ('planalto', 'rideel_vademecum') then 'legislacao'
        when lower(coalesce(c.url, '')) like '%sumula%' then 'sumula'
        else 'jurisprudencia'
      end,
      'tribunal', case
        when lower(coalesce(c.url, '')) ~ '(stf-vinculante|/stf|temas-stf)' then 'STF'
        when lower(coalesce(c.url, '')) ~ '(/stj|temas-stj)' then 'STJ'
        when lower(coalesce(c.url, '')) ~ '(/tst|temas-tst)' then 'TST'
        when lower(coalesce(c.url, '')) like '%/tse%' then 'TSE'
        else null
      end
    ))
  where c.metadata->>'norma_schema_version' is null
     or c.metadata->>'doc_key' is null
     or c.metadata->>'doc_type' is null;
  get diagnostics n = row_count;
  refresh materialized view concurrently public.norma_document_catalog_mv;
  return n;
end;
$$;

grant execute on function public.enrich_norma_chunks_metadata() to anon, authenticated, service_role;

-- Atualiza metadata só no primeiro chunk de cada documento (catálogo Lex).
create or replace function public.enrich_norma_catalog_chunks(p_source text default null)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  n integer;
begin
  with first_chunk as (
    select distinct on (c.source, public.normalize_norma_doc_key(c.url, c.source_file))
      c.id,
      c.source,
      c.url,
      c.source_file,
      c.metadata
    from public.norma_chunks c
    where p_source is null or c.source = p_source
    order by
      c.source,
      public.normalize_norma_doc_key(c.url, c.source_file),
      c.chunk_index,
      c.id
  ),
  upd as (
    update public.norma_chunks c
    set metadata = fc.metadata
      || jsonb_strip_nulls(jsonb_build_object(
        'norma_schema_version', 1,
        'doc_key', public.normalize_norma_doc_key(fc.url, fc.source_file),
        'doc_type', case
          when fc.source in ('planalto', 'rideel_vademecum') then 'legislacao'
          when lower(coalesce(fc.url, '')) like '%sumula%' then 'sumula'
          else 'jurisprudencia'
        end,
        'tribunal', case
          when lower(coalesce(fc.url, '')) ~ '(stf-vinculante|/stf|temas-stf)' then 'STF'
          when lower(coalesce(fc.url, '')) ~ '(/stj|temas-stj)' then 'STJ'
          when lower(coalesce(fc.url, '')) ~ '(/tst|temas-tst)' then 'TST'
          when lower(coalesce(fc.url, '')) like '%/tse%' then 'TSE'
          else null
        end
      ))
    from first_chunk fc
    where c.id = fc.id
    returning 1
  )
  select count(*)::integer into n from upd;

  refresh materialized view concurrently public.norma_document_catalog_mv;
  return n;
end;
$$;

grant execute on function public.enrich_norma_catalog_chunks(text) to anon, authenticated, service_role;
