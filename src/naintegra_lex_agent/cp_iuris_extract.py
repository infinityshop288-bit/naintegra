"""Extrai conhecimento jurídico dos e-books CP IURIS 2025 (PDF) com Ollama local."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .ai_organizer import OLLAMA_DEFAULT_OPENAI_API_BASE, _openai_compatible_chat, default_ai_model
from .flashcards_from_docx import load_pdf_pages, paginate_text_pages

logger = logging.getLogger(__name__)

EXTRACT_SYSTEM = """Você extrai conhecimento jurídico brasileiro de material didático (CP IURIS) para estudo de concursos.

Responda SOMENTE com JSON válido (sem markdown), neste formato:
{
  "discipline": "nome da disciplina",
  "topic": "tema principal do trecho",
  "summary": "resumo objetivo em 2-5 frases",
  "concepts": [{"term": "termo", "definition": "definição curta"}],
  "legal_refs": ["Art. X da Lei Y", "Súmula N STF", "..."],
  "jurisprudence": ["RE 123456", "Tema repetitivo ..."],
  "exam_tips": ["pegadinha ou distinção relevante para prova"],
  "confidence": 0.0
}

Regras:
- Use português jurídico claro e objetivo.
- Não invente número de artigo, lei ou processo: inclua em legal_refs/jurisprudence só o que estiver no texto.
- concepts: 0 a 8 itens; exam_tips: 0 a 6 itens.
- confidence entre 0 e 1 (quão completo está o trecho para extração).
"""

_IURIS_2025_RE = re.compile(r"(?:IURIS|CP\s*Iuris).*2025", re.I)
_COPY_SUFFIX_RE = re.compile(r"\s*-\s*c[oó]pia\s*$", re.I)


@dataclass
class TextChunk:
    chunk_id: str
    source_file: str
    source_ref: str
    page_number: int
    discipline_hint: str
    text: str


@dataclass
class KnowledgeRecord:
    chunk_id: str
    source_file: str
    source_ref: str
    page_number: int
    discipline: str
    topic: str
    summary: str
    concepts: list[dict[str, str]]
    legal_refs: list[str]
    jurisprudence: list[str]
    exam_tips: list[str]
    confidence: float
    extracted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_lex_record(self) -> dict[str, Any]:
        body_parts = [
            f"## {self.topic}",
            "",
            self.summary,
            "",
        ]
        if self.concepts:
            body_parts.append("### Conceitos")
            for c in self.concepts:
                term = c.get("term") or ""
                definition = c.get("definition") or ""
                if term:
                    body_parts.append(f"- **{term}**: {definition}")
            body_parts.append("")
        if self.legal_refs:
            body_parts.append("### Referências legais")
            body_parts.extend(f"- {r}" for r in self.legal_refs)
            body_parts.append("")
        if self.jurisprudence:
            body_parts.append("### Jurisprudência")
            body_parts.extend(f"- {j}" for j in self.jurisprudence)
            body_parts.append("")
        if self.exam_tips:
            body_parts.append("### Dicas de prova")
            body_parts.extend(f"- {t}" for t in self.exam_tips)

        return {
            "external_id": f"cpiuris2025::{self.chunk_id}",
            "source_system": "cp_iuris",
            "doc_type": "doutrina",
            "doc_key": self.chunk_id,
            "title": f"{self.discipline} — {self.topic}",
            "body": "\n".join(body_parts).strip(),
            "url": f"file://{self.source_file}#page={self.page_number}",
            "meta": {
                "corpus": "cp_iuris_2025",
                "source_file": self.source_file,
                "source_ref": self.source_ref,
                "page_number": self.page_number,
                "discipline": self.discipline,
                "legal_refs": self.legal_refs,
                "jurisprudence": self.jurisprudence,
                "confidence": self.confidence,
                "extracted_at": self.extracted_at,
            },
        }


@dataclass
class ExtractionJobState:
    pdf_dir: str
    output_dir: str
    model: str
    total_chunks: int = 0
    processed_chunks: int = 0
    failed_chunks: int = 0
    last_chunk_id: str | None = None
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _chunk_id(source_file: str, source_ref: str) -> str:
    raw = f"{source_file}|{source_ref}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def discipline_from_filename(name: str) -> str:
    base = _COPY_SUFFIX_RE.sub("", Path(name).stem)
    base = re.sub(r"^IURIS\s*-\s*", "", base, flags=re.I)
    base = re.sub(r"^CP\s*Iuris\s*-\s*", "", base, flags=re.I)
    base = re.sub(r"\s*-\s*Vol\.\s*\d+\s*-\s*2025\s*$", "", base, flags=re.I)
    base = re.sub(r"\s*-\s*2025\s*$", "", base, flags=re.I)
    base = re.sub(r"\s*2025\s*$", "", base, flags=re.I)
    return base.strip(" -–—") or name


def is_iuris_2025_pdf(path: Path) -> bool:
    if path.suffix.lower() != ".pdf":
        return False
    name = path.name
    if _COPY_SUFFIX_RE.search(path.stem):
        return False
    return bool(_IURIS_2025_RE.search(name))


def discover_iuris_2025_pdfs(search_dirs: list[Path]) -> list[Path]:
    seen_stems: set[str] = set()
    found: list[Path] = []
    for directory in search_dirs:
        if not directory.is_dir():
            continue
        for pdf in sorted(directory.glob("*.pdf")):
            if not is_iuris_2025_pdf(pdf):
                continue
            stem_key = re.sub(r"\s*\(\d+\)$", "", pdf.stem.lower())
            stem_key = _COPY_SUFFIX_RE.sub("", stem_key).strip()
            if stem_key in seen_stems:
                continue
            seen_stems.add(stem_key)
            found.append(pdf.resolve())
    return found


def build_text_chunks(
    pdfs: list[Path],
    *,
    page_chars: int = 2400,
    min_text_chars: int = 120,
) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for pdf in pdfs:
        hint = discipline_from_filename(pdf.name)
        raw_pages = load_pdf_pages(pdf)
        page_entries = paginate_text_pages(raw_pages, page_chars)
        for source_ref, text in page_entries:
            if len(text.strip()) < min_text_chars:
                continue
            page_num = 1
            m = re.search(r"p\.(\d+)", source_ref)
            if m:
                page_num = int(m.group(1))
            chunks.append(
                TextChunk(
                    chunk_id=_chunk_id(str(pdf), source_ref),
                    source_file=str(pdf),
                    source_ref=source_ref,
                    page_number=page_num,
                    discipline_hint=hint,
                    text=text,
                )
            )
    return chunks


def load_ai_config() -> dict[str, Any]:
    provider = os.environ.get("CP_IURIS_AI_PROVIDER", "ollama").strip() or "ollama"
    model = os.environ.get("CP_IURIS_AI_MODEL", "").strip() or os.environ.get(
        "LEX_AGENT_AI_MODEL", ""
    ).strip() or default_ai_model(provider)
    return {
        "provider": provider,
        "model": model,
        "base_url": os.environ.get("CP_IURIS_OLLAMA_BASE_URL", "").strip()
        or os.environ.get("LEX_AGENT_OPENAI_COMPATIBLE_BASE_URL", "").strip()
        or OLLAMA_DEFAULT_OPENAI_API_BASE,
        "api_key": os.environ.get("LEX_AGENT_OPENAI_COMPATIBLE_API_KEY", "").strip() or None,
        "timeout": float(os.environ.get("CP_IURIS_AI_TIMEOUT_SECONDS", "300")),
        "max_retries": int(os.environ.get("CP_IURIS_AI_RETRIES", "3")),
        "max_input_chars": int(os.environ.get("CP_IURIS_MAX_INPUT_CHARS", "6000")),
        "parallel_workers": max(1, int(os.environ.get("CP_IURIS_PARALLEL_WORKERS", "3"))),
    }


def ollama_available(base_url: str) -> bool:
    root = base_url.rstrip("/").removesuffix("/v1")
    try:
        import httpx

        r = httpx.get(f"{root}/api/tags", timeout=3.0)
        return r.is_success
    except Exception:
        return False


def extract_knowledge_with_ai(
    chunk: TextChunk,
    *,
    model: str,
    base_url: str,
    api_key: str | None,
    timeout: float,
    max_retries: int,
    max_input_chars: int,
) -> KnowledgeRecord | None:
    user = (
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
                system=EXTRACT_SYSTEM,
                user_prompt=user,
                timeout=timeout,
                temperature=0.15,
            )
            data = json.loads(_strip_json_fence(raw))
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
                "Falha IA chunk %s (tentativa %s/%s): %s",
                chunk.chunk_id[:8],
                attempt,
                max_retries,
                exc,
            )
            if attempt < max_retries:
                time.sleep(min(1.0 * attempt, 3.0))
    if last_err:
        logger.error("Chunk %s abandonado após %s tentativas", chunk.chunk_id[:8], max_retries)
    return None


def load_done_chunk_ids(knowledge_jsonl: Path) -> set[str]:
    if not knowledge_jsonl.is_file():
        return set()
    done: set[str] = set()
    with knowledge_jsonl.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = row.get("chunk_id")
            if cid:
                done.add(str(cid))
    return done


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def save_state(path: Path, state: ExtractionJobState) -> None:
    state.updated_at = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")


def load_state(path: Path) -> ExtractionJobState | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ExtractionJobState(**data)
    except (json.JSONDecodeError, OSError, TypeError):
        return None


def run_extraction_batch(
    *,
    pdf_dirs: list[Path],
    output_dir: Path,
    chunks_per_batch: int = 16,
    parallel_workers: int = 3,
    page_chars: int = 2400,
    delay_seconds: float = 0.0,
) -> tuple[int, int, int, bool]:
    """Processa até ``chunks_per_batch`` trechos pendentes (paralelo quando workers > 1).

    Retorna (processados_neste_lote, total_pendentes_antes, total_chunks, concluido).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    knowledge_jsonl = output_dir / "knowledge.jsonl"
    corpus_jsonl = output_dir / "corpus.jsonl"
    state_path = output_dir / "state.json"
    index_path = output_dir / "chunks_index.json"

    pdfs = discover_iuris_2025_pdfs(pdf_dirs)
    if not pdfs:
        logger.error("Nenhum PDF CP IURIS 2025 encontrado em: %s", pdf_dirs)
        return 0, 0, 0, True

    if index_path.is_file():
        try:
            index_data = json.loads(index_path.read_text(encoding="utf-8"))
            all_chunks = [
                TextChunk(**row)
                for row in index_data.get("chunks", [])
                if isinstance(row, dict)
            ]
        except (json.JSONDecodeError, OSError, TypeError):
            all_chunks = build_text_chunks(pdfs, page_chars=page_chars)
    else:
        all_chunks = build_text_chunks(pdfs, page_chars=page_chars)
        index_path.write_text(
            json.dumps(
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "pdf_count": len(pdfs),
                    "chunk_count": len(all_chunks),
                    "pdfs": [str(p) for p in pdfs],
                    "chunks": [asdict(c) for c in all_chunks],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    done = load_done_chunk_ids(knowledge_jsonl)
    pending = [c for c in all_chunks if c.chunk_id not in done]
    total = len(all_chunks)
    pending_before = len(pending)

    ai = load_ai_config()
    if not ollama_available(ai["base_url"]):
        logger.warning("Ollama indisponível em %s — aguardando próximo ciclo", ai["base_url"])
        state = load_state(state_path) or ExtractionJobState(
            pdf_dir=str(pdf_dirs[0]),
            output_dir=str(output_dir),
            model=ai["model"],
            total_chunks=total,
            processed_chunks=len(done),
        )
        state.total_chunks = total
        state.processed_chunks = len(done)
        save_state(state_path, state)
        return 0, pending_before, total, False

    batch = pending[: max(1, chunks_per_batch)]
    workers = max(1, min(parallel_workers, len(batch)))
    processed_now = 0
    failed_now = 0
    knowledge_rows: list[dict[str, Any]] = []
    corpus_rows: list[dict[str, Any]] = []

    def _extract_one(chunk: TextChunk) -> tuple[TextChunk, KnowledgeRecord | None]:
        record = extract_knowledge_with_ai(
            chunk,
            model=ai["model"],
            base_url=ai["base_url"],
            api_key=ai["api_key"],
            timeout=ai["timeout"],
            max_retries=ai["max_retries"],
            max_input_chars=ai["max_input_chars"],
        )
        return chunk, record

    if workers == 1:
        results = [_extract_one(chunk) for chunk in batch]
    else:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_extract_one, chunk) for chunk in batch]
            for fut in as_completed(futures):
                results.append(fut.result())

    for _chunk, record in results:
        if record is None:
            failed_now += 1
            continue
        knowledge_rows.append(asdict(record))
        corpus_rows.append(record.to_lex_record())
        processed_now += 1
        if delay_seconds > 0:
            time.sleep(delay_seconds)

    if knowledge_rows:
        append_jsonl(knowledge_jsonl, knowledge_rows)
    if corpus_rows:
        append_jsonl(corpus_jsonl, corpus_rows)

    processed_total = len(done) + processed_now
    state = ExtractionJobState(
        pdf_dir=str(pdf_dirs[0]),
        output_dir=str(output_dir),
        model=ai["model"],
        total_chunks=total,
        processed_chunks=processed_total,
        failed_chunks=(load_state(state_path).failed_chunks if load_state(state_path) else 0)
        + failed_now,
        last_chunk_id=batch[-1].chunk_id if batch else None,
    )
    save_state(state_path, state)

    finished = processed_total >= total
    logger.info(
        "Lote: +%s chunks · %s/%s total · pendentes %s · falhas lote %s · workers %s%s",
        processed_now,
        processed_total,
        total,
        max(0, total - processed_total),
        failed_now,
        workers,
        " · CONCLUÍDO" if finished else "",
    )
    return processed_now, pending_before, total, finished
