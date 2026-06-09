"""Extração de conhecimento jurídico (PDF/DOCX) com Ollama — FGV em Teses, Plano MP, etc."""

from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cp_iuris_extract import (
    ExtractionJobState,
    KnowledgeRecord,
    TextChunk,
    _chunk_id,
    append_jsonl,
    extract_knowledge_with_ai,
    load_ai_config,
    load_done_chunk_ids,
    load_state,
    ollama_available,
    save_state,
)
from .flashcards_from_docx import load_docx_paragraphs, load_pdf_pages, paginate_text_pages

logger = logging.getLogger(__name__)

STUDY_EXTRACT_SYSTEM = """Você extrai conhecimento jurídico brasileiro de material didático de cursinho/concurso para estudo.

IMPORTANTE: o material pode estar desatualizado (leis alteradas, súmulas superadas, redações antigas).
- Extraia o conteúdo como aparece no texto, sem “corrigir” artigos por conta própria.
- Em exam_tips, sinalize quando uma citação legal parecer desatualizada ou quando convier conferir a redação vigente no acervo NaIntegra Lex.
- Não invente número de artigo, lei ou processo.

Responda SOMENTE com JSON válido (sem markdown):
{
  "discipline": "disciplina ou eixo do material",
  "topic": "tema principal do trecho",
  "summary": "resumo objetivo em 2-5 frases",
  "concepts": [{"term": "termo", "definition": "definição curta"}],
  "legal_refs": ["Art. X da Lei Y", "Súmula N STF", "..."],
  "jurisprudence": ["RE 123456", "Tema repetitivo ..."],
  "exam_tips": ["pegadinha, distinção ou alerta de desatualização"],
  "confidence": 0.0
}

Regras: português jurídico claro; concepts 0-8; exam_tips 0-6; confidence 0-1.
"""

_DEFAULT_EXCLUDE = (
    ".ds_store",
    "__macosx",
)

_COPY_SUFFIX_RE = re.compile(r"\s*-\s*c[oó]pia\s*$", re.I)


def discipline_from_study_filename(name: str, corpus: str) -> str:
    base = _COPY_SUFFIX_RE.sub("", Path(name).stem)
    base = re.sub(r"^FGV[_\s]*EM[_\s]*TESES[_\s]*", "", base, flags=re.I)
    base = re.sub(r"^FGV[_\s]*", "", base, flags=re.I)
    base = re.sub(r"^PLANO\s+FULL\s*-\s*EXTENSIVO\s+MP\s+2024\s*-\s*DIA\s*", "MP 2024 — Dia ", base, flags=re.I)
    base = re.sub(r"DESAFIO_DE_SUMULAS__DIA_", "Desafio súmulas — Dia ", base, flags=re.I)
    base = base.replace("__", " — ").replace("_", " ").strip(" -–—")
    if corpus == "plano_mp_2024" and not base.lower().startswith("mp"):
        base = f"MP 2024 — {base}"
    if corpus == "fgv_em_teses" and not base.lower().startswith("fgv"):
        base = f"FGV — {base}"
    return base[:200] or name


def discover_study_files(
    roots: list[Path],
    *,
    extensions: tuple[str, ...] = (".pdf", ".docx"),
    exclude_names: tuple[str, ...] = _DEFAULT_EXCLUDE,
) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        root = root.expanduser().resolve()
        if not root.is_dir():
            logger.warning("Pasta inexistente: %s", root)
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in extensions:
                continue
            low = str(path).lower()
            if any(x in low for x in exclude_names):
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            found.append(path.resolve())
    return found


def build_study_chunks(
    files: list[Path],
    *,
    corpus: str,
    page_chars: int = 2400,
    min_text_chars: int = 120,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for path in files:
        hint = discipline_from_study_filename(path.name, corpus)
        page_entries: list[tuple[str, str]] = []
        if path.suffix.lower() == ".pdf":
            page_entries = load_pdf_pages(path)
        elif path.suffix.lower() == ".docx":
            paras = load_docx_paragraphs(path)
            joined = "\n\n".join(paras)
            if len(joined.strip()) >= min_text_chars:
                page_entries = [(path.name, joined)]
        for source_ref, text in paginate_text_pages(page_entries, page_chars):
            if len(text.strip()) < min_text_chars:
                continue
            page_num = 1
            m = re.search(r"p\.(\d+)", source_ref)
            if m:
                page_num = int(m.group(1))
            chunks.append(
                TextChunk(
                    chunk_id=_chunk_id(f"{corpus}|{path}", source_ref),
                    source_file=str(path),
                    source_ref=source_ref,
                    page_number=page_num,
                    discipline_hint=hint,
                    text=text,
                )
            )
    return chunks


def knowledge_to_lex_record(record: KnowledgeRecord, *, corpus: str) -> dict[str, Any]:
    row = record.to_lex_record()
    row["source_system"] = "study_material"
    row["meta"] = {
        **(row.get("meta") or {}),
        "corpus": corpus,
        "material_may_be_outdated": True,
        "lex_legislation_note": "Conferir legislação vigente no NaIntegra Lex (acervo atualizado).",
    }
    row["external_id"] = f"{corpus}::{record.chunk_id}"
    return row


def extract_study_with_ai(
    chunk: TextChunk,
    *,
    corpus: str,
    model: str,
    base_url: str,
    api_key: str | None,
    timeout: float,
    max_retries: int,
    max_input_chars: int,
) -> KnowledgeRecord | None:
    from .ai_organizer import _openai_compatible_chat
    from .cp_iuris_extract import _strip_json_fence as strip_fence

    user = (
        f"Corpus: {corpus}\n"
        f"Disciplina provável: {chunk.discipline_hint}\n"
        f"Fonte: {Path(chunk.source_file).name} · {chunk.source_ref}\n\n"
        f"--- TEXTO ---\n{chunk.text[:max_input_chars]}"
    )
    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            raw = _openai_compatible_chat(
                base_url=base_url,
                api_key=api_key,
                model=model,
                system=STUDY_EXTRACT_SYSTEM,
                user_prompt=user,
                timeout=timeout,
                temperature=0.15,
            )
            data = json.loads(strip_fence(raw))
            if not isinstance(data, dict):
                raise ValueError("JSON não é objeto")
            concepts_raw = data.get("concepts") or []
            concepts: list[dict[str, str]] = []
            if isinstance(concepts_raw, list):
                for item in concepts_raw[:8]:
                    if isinstance(item, dict):
                        term = str(item.get("term") or "").strip()
                        definition = str(item.get("definition") or "").strip()
                        if term:
                            concepts.append({"term": term, "definition": definition})

            def _str_list(key: str, limit: int) -> list[str]:
                val = data.get(key) or []
                if not isinstance(val, list):
                    return []
                return [str(x).strip() for x in val if str(x).strip()][:limit]

            try:
                confidence = float(data.get("confidence", 0.7))
            except (TypeError, ValueError):
                confidence = 0.7
            confidence = max(0.0, min(1.0, confidence))

            discipline = str(data.get("discipline") or chunk.discipline_hint).strip()
            topic = str(data.get("topic") or "Trecho").strip()
            summary = str(data.get("summary") or "").strip()
            if len(summary) < 20:
                raise ValueError("Resumo curto demais")

            return KnowledgeRecord(
                chunk_id=chunk.chunk_id,
                source_file=chunk.source_file,
                source_ref=chunk.source_ref,
                page_number=chunk.page_number,
                discipline=discipline,
                topic=topic[:300],
                summary=summary[:4000],
                concepts=concepts,
                legal_refs=_str_list("legal_refs", 20),
                jurisprudence=_str_list("jurisprudence", 15),
                exam_tips=_str_list("exam_tips", 8),
                confidence=confidence,
            )
        except Exception as exc:
            last_err = exc
            logger.warning(
                "Falha IA %s chunk %s (%s/%s): %s",
                corpus,
                chunk.chunk_id[:8],
                attempt,
                max_retries,
                exc,
            )
            if attempt < max_retries:
                time.sleep(min(1.0 * attempt, 3.0))
    if last_err:
        logger.error("Chunk %s abandonado", chunk.chunk_id[:8])
    return None


def index_study_material(
    *,
    input_roots: list[Path],
    output_dir: Path,
    corpus: str,
    page_chars: int = 2400,
) -> tuple[list[Path], list[TextChunk]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = discover_study_files(input_roots)
    chunks = build_study_chunks(files, corpus=corpus, page_chars=page_chars)
    index_path = output_dir / "chunks_index.json"
    index_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "corpus": corpus,
                "file_count": len(files),
                "chunk_count": len(chunks),
                "input_roots": [str(p) for p in input_roots],
                "files": [str(p) for p in files],
                "chunks": [asdict(c) for c in chunks],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info(
        "%s: %s arquivos → %s trechos indexados → %s",
        corpus,
        len(files),
        len(chunks),
        index_path,
    )
    return files, chunks


def run_study_extraction_batch(
    *,
    output_dir: Path,
    corpus: str,
    chunks_per_batch: int = 12,
    parallel_workers: int = 2,
    delay_seconds: float = 0.0,
) -> tuple[int, int, int, bool]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    knowledge_jsonl = output_dir / "knowledge.jsonl"
    corpus_jsonl = output_dir / "corpus.jsonl"
    state_path = output_dir / "state.json"
    index_path = output_dir / "chunks_index.json"

    if not index_path.is_file():
        logger.error("Índice ausente em %s — rode --index-only antes.", output_dir)
        return 0, 0, 0, True

    index_data = json.loads(index_path.read_text(encoding="utf-8"))
    raw_rows = [row for row in index_data.get("chunks", []) if isinstance(row, dict)]
    total = len(raw_rows)
    done = load_done_chunk_ids(knowledge_jsonl)
    pending_before = sum(1 for row in raw_rows if row.get("chunk_id") not in done)

    ai = load_ai_config()
    if not ollama_available(ai["base_url"]):
        logger.warning("Ollama indisponível em %s", ai["base_url"])
        return 0, pending_before, total, False

    if pending_before == 0:
        return 0, 0, total, True

    limit = max(1, chunks_per_batch)
    batch: list[TextChunk] = []
    for row in raw_rows:
        cid = row.get("chunk_id")
        if not cid or cid in done:
            continue
        batch.append(TextChunk(**row))
        if len(batch) >= limit:
            break
    workers = max(1, min(parallel_workers, len(batch)))
    logger.info(
        "[%s] processando lote de %s trechos (%s pendentes, %s/%s) · workers %s",
        corpus,
        len(batch),
        pending_before,
        len(done),
        total,
        workers,
    )
    knowledge_rows: list[dict[str, Any]] = []
    corpus_rows: list[dict[str, Any]] = []
    processed_now = 0
    failed_now = 0

    def _one(chunk: TextChunk) -> tuple[TextChunk, KnowledgeRecord | None]:
        logger.info("[%s] trecho %s · %s", corpus, chunk.chunk_id[:8], chunk.source_ref[:60])
        return chunk, extract_study_with_ai(
            chunk,
            corpus=corpus,
            model=ai["model"],
            base_url=ai["base_url"],
            api_key=ai["api_key"],
            timeout=ai["timeout"],
            max_retries=ai["max_retries"],
            max_input_chars=ai["max_input_chars"],
        )

    if workers == 1:
        results = [_one(c) for c in batch]
    else:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_one, c) for c in batch]
            for fut in as_completed(futures):
                results.append(fut.result())

    for _chunk, record in results:
        if record is None:
            failed_now += 1
            continue
        knowledge_rows.append(asdict(record))
        corpus_rows.append(knowledge_to_lex_record(record, corpus=corpus))
        processed_now += 1
        if delay_seconds > 0:
            time.sleep(delay_seconds)

    if knowledge_rows:
        append_jsonl(knowledge_jsonl, knowledge_rows)
    if corpus_rows:
        append_jsonl(corpus_jsonl, corpus_rows)

    processed_total = len(done) + processed_now
    state = ExtractionJobState(
        pdf_dir=str(output_dir),
        output_dir=str(output_dir),
        model=ai["model"],
        total_chunks=total,
        processed_chunks=processed_total,
        failed_chunks=failed_now,
        last_chunk_id=batch[-1].chunk_id if batch else None,
    )
    save_state(state_path, state)

    finished = processed_total >= total
    logger.info(
        "[%s] lote +%s · %s/%s · pendentes %s%s",
        corpus,
        processed_now,
        processed_total,
        total,
        max(0, total - processed_total),
        " · OK" if finished else "",
    )
    return processed_now, pending_before, total, finished
