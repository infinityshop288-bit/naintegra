"""Gera flashcards a partir de DOCX (verbetes) e publica no schema lex (NaIntegra Lex)."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from docx import Document

from .ai_organizer import OLLAMA_DEFAULT_OPENAI_API_BASE, _openai_compatible_chat, default_ai_model

logger = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]

DECK_CATALOG: list[tuple[str, str, str]] = [
    ("dir-const", "Direito Constitucional", "Direito Público"),
    ("dir-proc-civil", "Direito Processual Civil", "Processo"),
    ("dir-proc-penal", "Direito Processual Penal", "Processo"),
    ("dir-adm", "Direito Administrativo", "Direito Público"),
    ("dir-penal-geral", "Direito Penal - Parte Geral", "Direito Público"),
    ("dir-civil-obrig", "Direito Civil - Obrigações e Contratos", "Direito Privado"),
    ("dir-eleitoral", "Direito Eleitoral", "Direito Público"),
    ("jurisprudencia", "Jurisprudência", "Jurisprudência"),
    ("dir-civil-geral", "Direito Civil - Parte Geral", "Direito Privado"),
    ("dir-penal-especial", "Direito Penal - Parte Especial", "Direito Público"),
    ("dir-financeiro", "Direito Financeiro", "Direito Público"),
    ("tutela-coletiva", "Tutela Coletiva e Direito Processual Coletivo", "Processo"),
    ("lei-improbidade", "Lei de Improbidade Administrativa", "Direito Público"),
    ("dir-economico", "Direito Econômico", "Direito Público"),
    ("dir-previdenciario", "Direito Previdenciário", "Direito Privado"),
]

DISCIPLINE_NAMES = {name for _, name, _ in DECK_CATALOG}

LAW_REF_RE = re.compile(
    r"(Lei n[.º°]?\s*[\d./]+|Lei nº\s*[\d./]+|CF|CDC|CC|CPC|CPP|CP|CTN|CLT|ECA|LGPD|"
    r"Súmula(?:\s+Vinculante)?\s*\d+|REsp|RE \d|ADI \d|ADPF \d|Decreto[\s\d./]+)",
    re.I,
)

DISCIPLINE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Direito Constitucional", ("constitucional", "cf:", "cf ", "art. 5", "emenda constitucional", "adi ", "adpf ")),
    ("Direito Processual Civil", ("cpc", "processual civil", "código de processo civil", "recurso especial", "agravo de instrumento")),
    (
        "Direito Processual Penal",
        (
            "cpp",
            "processo penal",
            "processual penal",
            "código de processo penal",
            "inquérito",
            "inquerito",
            "júri",
            "juri",
            "habeas corpus",
            "prisão preventiva",
            "prisao preventiva",
            "flagrante",
            "art. 157",
            "art. 386",
            "art. 404",
            "art. 576",
        ),
    ),
    ("Direito Administrativo", ("administra", "servidor", "8.112", "8.666", "14.133", "licita", "improbidade", "concessão", "ppp", "organização social")),
    ("Direito Penal - Parte Geral", ("código penal", "cp:", " cp ", "crime", "pena", "dosimetria", "culpabilidade")),
    ("Direito Penal - Parte Especial", ("crimes contra", "parte especial", "estelionato", "peculato", "corrupção passiva")),
    ("Direito Civil - Obrigações e Contratos", ("cdc", "consumidor", "contrato", "obriga", "responsabilidade civil", "indenização")),
    ("Direito Civil - Parte Geral", ("código civil", "cc:", " cc ", "pessoa jurídica", "posse", "propriedade", "família")),
    ("Direito Eleitoral", ("eleitor", "tse", "campanha", "candidato", "partido político", "9.096", "9.504")),
    ("Jurisprudência", ("stf", "stj", "súmula", "jurisprudência", "resp", "re ", "tema repetitivo", "repercussão geral")),
    ("Direito Financeiro", ("orçament", "financeiro", "lrf", "ldo", "loa", "receita pública", "dívida pública")),
    ("Tutela Coletiva e Direito Processual Coletivo", ("ação civil pública", "acp", "mandado de segurança coletivo", "tutela coletiva", "7.347", "8.078")),
    ("Lei de Improbidade Administrativa", ("improbidade", "8.429", "ato de improbidade")),
    ("Direito Econômico", ("concorrência", "cade", "defesa da concorrência", "12.529", "regulação econômica")),
    ("Direito Previdenciário", ("previd", "inss", "aposentadoria", "benefício previdenciário", "8.213", "8.742")),
]

CLASSIFY_SYSTEM = """Você classifica flashcards jurídicos por disciplina.
Responda SOMENTE JSON válido no formato:
{"items":[{"i":0,"discipline":"Nome exato"}]}
Use exatamente um destes nomes de discipline:
""" + "\n".join(f"- {n}" for n in sorted(DISCIPLINE_NAMES))


@dataclass
class FlashcardDraft:
    page_index: int
    card_index: int
    front: str
    back: str
    discipline: str | None = None
    highlight: str | None = None
    source_ref: str | None = None

    def key(self) -> str:
        ref = self.source_ref or ""
        return f"{ref}|p{self.page_index}:c{self.card_index}"


@dataclass
class FlashcardsJobState:
    source_path: str
    page_chars: int
    min_cards_per_page: int
    total_pages: int = 0
    processed_pages: int = 0
    generated_cards: int = 0
    classified_cards: int = 0
    published_cards: int = 0
    last_page_index: int = -1
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z0-9]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def load_docx_paragraphs(path: Path) -> list[str]:
    doc = Document(str(path))
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]


def load_pdf_pages(path: Path) -> list[tuple[str, str]]:
    """Extrai texto por página: [(source_ref, text), ...]."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Instale pymupdf: pip install pymupdf") from exc

    out: list[tuple[str, str]] = []
    doc = fitz.open(str(path))
    try:
        for i, page in enumerate(doc):
            text = page.get_text("text").strip()
            if len(text) < 40:
                continue
            out.append((f"{path.name} · p.{i + 1}", text))
    finally:
        doc.close()
    return out


def load_pdf_folder_pages(folder: Path, *, dedupe: bool = True) -> list[tuple[str, str]]:
    """Concatena páginas de todos os PDFs do diretório (ordem alfabética)."""
    seen: set[tuple[int, str]] = set()
    pages: list[tuple[str, str]] = []
    for pdf in sorted(folder.glob("*.pdf")):
        if dedupe:
            stem = re.sub(r"\s*\(\d+\)$", "", pdf.stem)
            key = (pdf.stat().st_size, stem)
            if key in seen:
                continue
            seen.add(key)
        pages.extend(load_pdf_pages(pdf))
    return pages


def paginate_text_pages(
    page_entries: list[tuple[str, str]],
    page_chars: int = 2800,
) -> list[tuple[str, str]]:
    """Agrupa páginas PDF curtas ou divide páginas longas em pseudo-páginas."""
    out: list[tuple[str, str]] = []
    for source_ref, text in page_entries:
        if len(text) <= page_chars * 1.2:
            out.append((source_ref, text))
            continue
        paras = [ln.strip() for ln in text.split("\n") if ln.strip()]
        buf = ""
        part = 1
        for para in paras:
            chunk = para + "\n"
            if len(buf) + len(chunk) > page_chars and buf.strip():
                out.append((f"{source_ref} ({part})", buf.strip()))
                part += 1
                buf = chunk
            else:
                buf += chunk
        if buf.strip():
            out.append((f"{source_ref} ({part})" if part > 1 else source_ref, buf.strip()))
    return out


def paginate_paragraphs(paragraphs: list[str], page_chars: int = 2800) -> list[str]:
    pages: list[str] = []
    buf = ""
    for para in paragraphs:
        chunk = para + "\n"
        if len(buf) + len(chunk) > page_chars and buf.strip():
            pages.append(buf.strip())
            buf = chunk
        else:
            buf += chunk
    if buf.strip():
        pages.append(buf.strip())
    return pages


def _extract_ref(text: str) -> str:
    m = LAW_REF_RE.search(text)
    if m:
        return m.group(1).strip()
    first = text.split("\n", 1)[0].strip()
    return first[:120] if first else "trecho legal"


def _split_page_blocks(page: str, min_cards: int) -> list[str]:
    lines = [ln.strip() for ln in page.split("\n") if ln.strip() and ln.strip() != "(...)"]
    if not lines:
        return [page.strip()] if page.strip() else []
    if len(lines) >= min_cards:
        groups: list[list[str]] = [[] for _ in range(min_cards)]
        for i, ln in enumerate(lines):
            groups[i % min_cards].append(ln)
        return ["\n".join(g) for g in groups if g]
    if len(page) >= min_cards * 200:
        mid = len(page) // min_cards
        chunks = []
        start = 0
        for i in range(min_cards):
            end = len(page) if i == min_cards - 1 else min(start + mid, len(page))
            part = page[start:end].strip()
            if part:
                chunks.append(part)
            start = end
        return chunks or [page]
    merged = "\n".join(lines)
    return [merged] * min_cards


QUESTAO_RE = re.compile(r"QUEST[ÃA]O\s*(\d+)", re.I)


def _question_from_block(block: str, ref: str, card_idx: int) -> str:
    block_clean = re.sub(r"\s+", " ", block).strip()
    q = QUESTAO_RE.search(block)
    if q and card_idx == 0:
        after = block_clean[q.end() : q.end() + 180].strip(" .:-")
        if len(after) > 20:
            return f"Questão {q.group(1)}: {after}?"
    if card_idx == 0:
        return f"O que estabelece {ref}?"
    if "?" in block_clean[:200]:
        return block_clean.split("?", 1)[0].strip() + "?"
    verbs = ("é ", "são ", "pode ", "podem ", "deve ", "deverá ", "compete ", "constitui ")
    lower = block_clean.lower()
    for v in verbs:
        pos = lower.find(v)
        if 0 <= pos <= 120:
            snippet = block_clean[pos : pos + 100].rstrip(".,;")
            return f"Complete ou explique: {snippet}…"
    return f"Qual a regra jurídica sobre {ref} (aspecto {card_idx + 1})?"


def generate_cards_heuristic(
    page: str,
    page_index: int,
    min_cards: int = 2,
    *,
    page_source_ref: str | None = None,
) -> list[FlashcardDraft]:
    blocks = _split_page_blocks(page, min_cards)
    cards: list[FlashcardDraft] = []
    for i, block in enumerate(blocks[: max(min_cards, len(blocks))]):
        if len(block) < 40:
            continue
        ref = _extract_ref(block)
        front = _question_from_block(block, ref, i)
        back = block.strip()
        if len(front) < 15 or len(back) < 40:
            continue
        cards.append(
            FlashcardDraft(
                page_index=page_index,
                card_index=i,
                front=front[:500],
                back=back[:4000],
                source_ref=page_source_ref or ref,
            )
        )
    while len(cards) < min_cards and page.strip():
        i = len(cards)
        ref = _extract_ref(page)
        cards.append(
            FlashcardDraft(
                page_index=page_index,
                card_index=i,
                front=_question_from_block(page, ref, i)[:500],
                back=page.strip()[:4000],
                source_ref=page_source_ref or ref,
            )
        )
    return cards[: max(min_cards, len(cards))]


def guess_discipline(text: str) -> str:
    disc, _score = guess_discipline_scored(text)
    return disc


def guess_discipline_scored(text: str) -> tuple[str, int]:
    lower = text.lower()
    scores: dict[str, int] = {}
    for discipline, keys in DISCIPLINE_KEYWORDS:
        score = sum(1 for k in keys if k in lower)
        if score:
            scores[discipline] = score
    if scores:
        best = max(scores, key=scores.get)
        return best, scores[best]
    return "Direito Administrativo", 0


def _parse_classify_json(raw: str, expected: int) -> list[str | None]:
    try:
        data = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError:
        return [None] * expected
    items = data.get("items") or data.get("disciplines") or data.get("classifications")
    if isinstance(items, list) and items and isinstance(items[0], str):
        return [(x if x in DISCIPLINE_NAMES else None) for x in items[:expected]]
    out: list[str | None] = [None] * expected
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                idx = item.get("i", item.get("index"))
                disc = item.get("discipline") or item.get("disciplina")
                try:
                    idx_i = int(idx)
                except (TypeError, ValueError):
                    continue
                if 0 <= idx_i < expected and disc in DISCIPLINE_NAMES:
                    out[idx_i] = disc
    return out


def classify_disciplines_ai(
    cards: list[FlashcardDraft],
    *,
    provider: str,
    api_key: str,
    model: str,
    base_url: str | None,
    timeout: float,
    max_retries: int = 3,
) -> None:
    if not cards:
        return
    lines = []
    for i, c in enumerate(cards):
        snippet = f"{c.front}\n{(c.back or '')[:220]}"
        lines.append(f"{i}. {snippet}")
    user = "Classifique cada item abaixo (campo i = índice):\n\n" + "\n\n".join(lines)
    if provider == "ollama" and not (base_url or "").strip():
        base_url = OLLAMA_DEFAULT_OPENAI_API_BASE

    last_err: Exception | None = None
    raw = ""
    for attempt in range(1, max_retries + 1):
        try:
            raw = _openai_compatible_chat(
                base_url=base_url or OLLAMA_DEFAULT_OPENAI_API_BASE,
                api_key=api_key.strip() or None,
                model=model,
                system=CLASSIFY_SYSTEM,
                user_prompt=user,
                timeout=timeout,
                temperature=0.1,
            )
            last_err = None
            break
        except Exception as exc:
            last_err = exc
            logger.warning("IA disciplina tentativa %s/%s falhou: %s", attempt, max_retries, exc)
            time.sleep(min(2 * attempt, 10))

    if last_err is not None:
        logger.warning("IA indisponível; mantendo heurística de disciplina.")
        for card in cards:
            if not card.discipline:
                card.discipline = guess_discipline(f"{card.front}\n{card.back}")
        return

    parsed = _parse_classify_json(raw, len(cards))
    for card, disc in zip(cards, parsed, strict=False):
        if disc:
            card.discipline = disc
        elif not card.discipline:
            card.discipline = guess_discipline(f"{card.front}\n{card.back}")


def generate_cards_ai_page(
    page: str,
    page_index: int,
    *,
    min_cards: int,
    provider: str,
    api_key: str,
    model: str,
    base_url: str | None,
    timeout: float,
) -> list[FlashcardDraft]:
    system = (
        "Você gera flashcards jurídicos para concurso (JE/JF/DF). "
        f"Crie EXATAMENTE {min_cards} cards objetivos. "
        'Responda SOMENTE JSON: {"cards":[{"discipline":"...","front":"...","back":"...","highlight":null}]} '
        "Disciplinas permitidas:\n" + "\n".join(f"- {n}" for n in sorted(DISCIPLINE_NAMES))
    )
    user = f"Página {page_index + 1}:\n{page[:6000]}"
    if provider == "ollama" and not (base_url or "").strip():
        base_url = OLLAMA_DEFAULT_OPENAI_API_BASE
    raw = _openai_compatible_chat(
        base_url=base_url or OLLAMA_DEFAULT_OPENAI_API_BASE,
        api_key=api_key.strip() or None,
        model=model,
        system=system,
        user_prompt=user,
        timeout=timeout,
        temperature=0.2,
    )
    try:
        data = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError:
        return generate_cards_heuristic(page, page_index, min_cards)
    items = data.get("cards") or []
    out: list[FlashcardDraft] = []
    for i, item in enumerate(items[: min_cards]):
        if not isinstance(item, dict):
            continue
        front = str(item.get("front") or "").strip()
        back = str(item.get("back") or "").strip()
        if len(front) < 10 or len(back) < 20:
            continue
        disc = item.get("discipline")
        disc_str = disc if disc in DISCIPLINE_NAMES else guess_discipline(f"{front}\n{back}")
        highlight = item.get("highlight")
        out.append(
            FlashcardDraft(
                page_index=page_index,
                card_index=i,
                front=front[:500],
                back=back[:4000],
                discipline=disc_str,
                highlight=str(highlight).strip() if highlight else None,
                source_ref=_extract_ref(page),
            )
        )
    if len(out) < min_cards:
        out.extend(generate_cards_heuristic(page, page_index, min_cards - len(out)))
    return out[: max(min_cards, len(out))]


def load_ai_settings() -> dict[str, Any]:
    provider = os.environ.get("LEX_AGENT_AI_PROVIDER", "ollama").strip() or "ollama"
    model = os.environ.get("LEX_AGENT_AI_MODEL", "").strip() or default_ai_model(provider)
    return {
        "provider": provider,
        "api_key": os.environ.get("LEX_AGENT_OPENAI_API_KEY", "")
        or os.environ.get("LEX_AGENT_OPENAI_COMPATIBLE_API_KEY", "")
        or os.environ.get("LEX_AGENT_ANTHROPIC_API_KEY", ""),
        "model": model,
        "base_url": os.environ.get("LEX_AGENT_OPENAI_COMPATIBLE_BASE_URL", "").strip() or None,
        "timeout": float(os.environ.get("LEX_FLASHCARDS_AI_TIMEOUT_SECONDS", "300")),
        "batch_size": int(os.environ.get("LEX_FLASHCARDS_CLASSIFY_BATCH", "20")),
        "chunk_classify_batch": int(os.environ.get("LEX_FLASHCARDS_CHUNK_CLASSIFY_BATCH", "0")),
        "max_retries": int(os.environ.get("LEX_FLASHCARDS_AI_RETRIES", "3")),
    }


def _sql_str(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def build_insert_sql(
    cards: list[FlashcardDraft],
    deck_ids: dict[str, str],
    sort_start: dict[str, int],
) -> str:
    counters = dict(sort_start)
    values: list[str] = []
    for card in cards:
        discipline = card.discipline or guess_discipline(f"{card.front}\n{card.back}")
        deck_id = deck_ids.get(discipline) or deck_ids["Direito Administrativo"]
        counters[deck_id] = counters.get(deck_id, 0) + 1
        values.append(
            "("
            f"{_sql_str(deck_id)}::uuid, "
            f"{_sql_str(card.front)}, "
            f"{_sql_str(card.back)}, "
            f"{_sql_str(card.highlight)}, "
            f"{counters[deck_id]}"
            ")"
        )
    sort_start.clear()
    sort_start.update(counters)
    if not values:
        return ""
    return (
        "INSERT INTO lex.flashcards (deck_id, front, back, highlight, sort_order) VALUES\n"
        + ",\n".join(values)
        + ";\n"
    )


def load_supabase_cfg() -> tuple[str, str]:
    url = os.environ.get("LEX_AGENT_SUPABASE_URL", "").strip()
    key = os.environ.get("LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("Defina LEX_AGENT_SUPABASE_URL e LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY.")
    return url.rstrip("/"), key


def fetch_deck_map(client: httpx.Client, base: str, headers: dict) -> dict[str, str]:
    res = client.get(
        f"{base}/rest/v1/flashcard_decks?select=id,name,slug&order=sort_order.asc",
        headers=headers,
    )
    res.raise_for_status()
    decks = res.json()
    by_name = {d["name"]: d["id"] for d in decks}
    missing = [name for _, name, _ in DECK_CATALOG if name not in by_name]
    if missing:
        payload = []
        for i, (slug, name, category) in enumerate(DECK_CATALOG, 1):
            if name in missing:
                payload.append({"slug": slug, "name": name, "category": category, "sort_order": i})
        if payload:
            ins = client.post(
                f"{base}/rest/v1/flashcard_decks",
                headers={**headers, "Prefer": "return=representation"},
                json=payload,
            )
            ins.raise_for_status()
            for d in ins.json():
                by_name[d["name"]] = d["id"]
    return by_name


def fetch_max_sort_orders(client: httpx.Client, base: str, headers: dict) -> dict[str, int]:
    res = client.get(
        f"{base}/rest/v1/flashcards?select=deck_id,sort_order&order=sort_order.desc&limit=1000",
        headers=headers,
    )
    res.raise_for_status()
    out: dict[str, int] = {}
    for row in res.json():
        deck_id = row["deck_id"]
        sort_order = int(row.get("sort_order") or 0)
        out[deck_id] = max(out.get(deck_id, 0), sort_order)
    return out


def publish_cards(cards: list[FlashcardDraft], *, dry_run: bool = False) -> int:
    if not cards:
        return 0
    if dry_run:
        logger.info("[dry-run/jsonl-only] %s cards prontos para publicação", len(cards))
        return len(cards)

    base, key = load_supabase_cfg()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept-Profile": "lex",
        "Content-Profile": "lex",
        "Content-Type": "application/json",
    }
    rows = []
    for card in cards:
        discipline = card.discipline or guess_discipline(f"{card.front}\n{card.back}")
        rows.append(
            {
                "discipline": discipline,
                "front": card.front,
                "back": card.back,
                "highlight": card.highlight,
            }
        )

    with httpx.Client(timeout=120.0) as client:
        res = client.post(
            f"{base}/rest/v1/rpc/ingest_flashcards_batch",
            headers=headers,
            json={"rows": rows},
        )
        if res.status_code >= 400:
            logger.warning("RPC ingest falhou (%s): %s", res.status_code, res.text[:300])
            return 0
        try:
            inserted = int(res.json())
        except (TypeError, ValueError):
            inserted = len(rows)
    return inserted


def save_jsonl(path: Path, cards: list[FlashcardDraft]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")


def load_processed_page_keys(jsonl_path: Path) -> set[str]:
    if not jsonl_path.is_file():
        return set()
    keys: set[str] = set()
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            keys.add(
                f"{row.get('source_ref') or ''}|p{row.get('page_index')}:c{row.get('card_index')}"
            )
    return keys


def load_completed_pages(jsonl_path: Path, min_cards_per_page: int) -> set[int]:
    if not jsonl_path.is_file():
        return set()
    counts: dict[int, int] = {}
    with jsonl_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            page_index = int(row.get("page_index", -1))
            if page_index >= 0:
                counts[page_index] = counts.get(page_index, 0) + 1
    return {p for p, n in counts.items() if n >= min_cards_per_page}


def save_state(path: Path, state: FlashcardsJobState) -> None:
    state.updated_at = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(asdict(state), ensure_ascii=False, indent=2), encoding="utf-8")


def run_flashcards_pipeline_from_pages(
    *,
    page_entries: list[tuple[str, str]],
    source_path: str,
    output_dir: Path,
    page_chars: int = 2800,
    min_cards_per_page: int = 2,
    ai_mode: str = "classify",
    publish_batch_pages: int = 25,
    max_pages: int | None = None,
    dry_run: bool = False,
    delay_seconds: float = 0.0,
) -> FlashcardsJobState:
    """page_entries: lista de (source_ref, texto_da_página)."""
    ai = load_ai_settings()
    pages = list(page_entries)
    if max_pages is not None:
        pages = pages[:max_pages]

    cards_jsonl = output_dir / "cards.jsonl"
    state_path = output_dir / "state.json"
    done_keys = load_processed_page_keys(cards_jsonl)
    completed_pages = load_completed_pages(cards_jsonl, min_cards_per_page)

    state = FlashcardsJobState(
        source_path=source_path,
        page_chars=page_chars,
        min_cards_per_page=min_cards_per_page,
        total_pages=len(pages),
    )
    if state_path.is_file():
        try:
            prev = json.loads(state_path.read_text(encoding="utf-8"))
            state.processed_pages = int(prev.get("processed_pages") or 0)
            state.published_cards = int(prev.get("published_cards") or 0)
            state.generated_cards = int(prev.get("generated_cards") or 0)
            state.classified_cards = int(prev.get("classified_cards") or 0)
        except (json.JSONDecodeError, OSError):
            pass

    chunk_cards: list[FlashcardDraft] = []
    chunk_start: int | None = None

    def flush_chunk(end_page_index: int) -> None:
        nonlocal chunk_cards, chunk_start, state
        if not chunk_cards:
            chunk_start = None
            return

        save_jsonl(cards_jsonl, chunk_cards)
        for c in chunk_cards:
            done_keys.add(c.key())

        if ai_mode != "generate":
            min_score = int(os.environ.get("LEX_FLASHCARDS_HEURISTIC_MIN_SCORE", "2"))
            uncertain = [
                c
                for c in chunk_cards
                if guess_discipline_scored(f"{c.front}\n{c.back}")[1] < min_score
            ]
            classify_batch = int(ai.get("chunk_classify_batch") or 0)
            if classify_batch <= 0:
                classify_batch = max(len(uncertain), 1)
            for batch_start in range(0, len(uncertain), classify_batch):
                batch = uncertain[batch_start : batch_start + classify_batch]
                if not batch:
                    continue
                classify_disciplines_ai(
                    batch,
                    provider=ai["provider"],
                    api_key=ai["api_key"],
                    model=ai["model"],
                    base_url=ai["base_url"],
                    timeout=ai["timeout"],
                    max_retries=ai["max_retries"],
                )
                if delay_seconds:
                    time.sleep(delay_seconds)

        state.generated_cards += len(chunk_cards)
        state.classified_cards += len(chunk_cards)
        published = publish_cards(chunk_cards, dry_run=dry_run)
        state.published_cards += published
        state.processed_pages = end_page_index + 1
        state.last_page_index = end_page_index
        save_state(state_path, state)
        logger.info(
            "Páginas %s-%s/%s · +%s cards · total publicados %s",
            (chunk_start or 0) + 1,
            end_page_index + 1,
            len(pages),
            len(chunk_cards),
            state.published_cards,
        )
        chunk_cards = []
        chunk_start = None

    for page_index, (source_ref, page_text) in enumerate(pages):
        if page_index in completed_pages:
            continue

        if ai_mode == "generate":
            page_cards = generate_cards_ai_page(
                page_text,
                page_index,
                min_cards=min_cards_per_page,
                provider=ai["provider"],
                api_key=ai["api_key"],
                model=ai["model"],
                base_url=ai["base_url"],
                timeout=ai["timeout"],
            )
            for c in page_cards:
                c.source_ref = source_ref
        else:
            page_cards = generate_cards_heuristic(
                page_text,
                page_index,
                min_cards_per_page,
                page_source_ref=source_ref,
            )
            for c in page_cards:
                c.discipline, _ = guess_discipline_scored(f"{c.front}\n{c.back}")

        new_cards = [c for c in page_cards if c.key() not in done_keys]
        if not new_cards:
            continue

        if chunk_start is None:
            chunk_start = page_index
        chunk_cards.extend(new_cards)

        pages_in_chunk = page_index - chunk_start + 1
        if pages_in_chunk >= publish_batch_pages:
            flush_chunk(page_index)

    if chunk_cards:
        flush_chunk(len(pages) - 1)

    return state


def run_flashcards_pipeline_from_pdf_folder(
    *,
    folder_path: Path,
    output_dir: Path,
    page_chars: int = 2800,
    min_cards_per_page: int = 2,
    ai_mode: str = "classify",
    publish_batch_pages: int = 25,
    max_pages: int | None = None,
    dry_run: bool = False,
    delay_seconds: float = 0.0,
    dedupe_pdfs: bool = True,
) -> FlashcardsJobState:
    raw_pages = load_pdf_folder_pages(folder_path, dedupe=dedupe_pdfs)
    page_entries = paginate_text_pages(raw_pages, page_chars)
    return run_flashcards_pipeline_from_pages(
        page_entries=page_entries,
        source_path=str(folder_path),
        output_dir=output_dir,
        page_chars=page_chars,
        min_cards_per_page=min_cards_per_page,
        ai_mode=ai_mode,
        publish_batch_pages=publish_batch_pages,
        max_pages=max_pages,
        dry_run=dry_run,
        delay_seconds=delay_seconds,
    )


def run_flashcards_pipeline(
    *,
    docx_path: Path,
    output_dir: Path,
    page_chars: int = 2800,
    min_cards_per_page: int = 2,
    ai_mode: str = "classify",
    publish_batch_pages: int = 25,
    max_pages: int | None = None,
    dry_run: bool = False,
    delay_seconds: float = 0.0,
) -> FlashcardsJobState:
    """ai_mode: classify (heurística + IA disciplina) | generate (IA gera conteúdo e disciplina)."""
    paragraphs = load_docx_paragraphs(docx_path)
    text_pages = paginate_paragraphs(paragraphs, page_chars)
    page_entries = [(docx_path.name, t) for t in text_pages]
    return run_flashcards_pipeline_from_pages(
        page_entries=page_entries,
        source_path=str(docx_path),
        output_dir=output_dir,
        page_chars=page_chars,
        min_cards_per_page=min_cards_per_page,
        ai_mode=ai_mode,
        publish_batch_pages=publish_batch_pages,
        max_pages=max_pages,
        dry_run=dry_run,
        delay_seconds=delay_seconds,
    )
