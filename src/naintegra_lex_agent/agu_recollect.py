"""Re-coleta de legislação Planalto (encoding correto) em repositório de backup separado."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .legal_text import pick_verbatim_body
from .norma_chunks import normalize_norma_url
from .planalto_legis import content_hash, fetch_planalto_text

DEFAULT_BACKUP_ROOT = Path("data/legislacao_agu_recollection")
PLANALTO_HOST = "planalto.gov.br"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


def load_source_records(source_dir: Path) -> dict[str, dict[str, Any]]:
    """Última versão por URL normalizada."""
    by_url: dict[str, dict[str, Any]] = {}
    for fp in sorted(source_dir.glob("*.jsonl")):
        for rec in iter_jsonl(fp):
            url = normalize_norma_url(str(rec.get("url") or ""))
            if not url:
                continue
            prev = by_url.get(url)
            body = pick_verbatim_body(rec) or ""
            prev_body = pick_verbatim_body(prev) or "" if prev else ""
            if not prev or len(body) >= len(prev_body):
                by_url[url] = rec
    return by_url


def is_planalto_url(url: str) -> bool:
    return PLANALTO_HOST in (url or "").lower()


def has_encoding_corruption(text: str) -> bool:
    if not text:
        return False
    if "\ufffd" in text:
        return True
    if re.search(r"Presid.{0,2}ncia", text) and "Presidência" not in text and "Presidencia" not in text:
        return True
    return False


def needs_planalto_recollection(rec: dict[str, Any]) -> bool:
    url = normalize_norma_url(str(rec.get("url") or ""))
    if not is_planalto_url(url):
        return False
    body = pick_verbatim_body(rec) or str(rec.get("summary") or "")
    return has_encoding_corruption(body)


def extract_summary(text: str, *, max_len: int = 600) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    if not t:
        return ""
    m = re.search(
        r"(?is)(DECRETO|LEI(?:\s+COMPLEMENTAR)?|MEDIDA\s+PROVIS[ÓO]RIA|EMENDA\s+CONSTITUCIONAL)"
        r".{20,400}",
        t,
    )
    if m:
        return m.group(0).strip()[:max_len]
    return t[:max_len]


@dataclass
class RecollectResult:
    url: str
    title: str
    ok: bool
    skipped: bool = False
    skip_reason: str | None = None
    error: str | None = None
    char_count: int = 0
    content_hash: str | None = None
    text: str | None = None


@dataclass
class RecollectRunReport:
    run_id: str
    source_dir: str
    output_dir: str
    started_at: str
    finished_at: str | None = None
    total_candidates: int = 0
    fetched_ok: int = 0
    failed: int = 0
    skipped: int = 0
    copied_lexml: int = 0
    results: list[RecollectResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "source_dir": self.source_dir,
            "output_dir": self.output_dir,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_candidates": self.total_candidates,
            "fetched_ok": self.fetched_ok,
            "failed": self.failed,
            "skipped": self.skipped,
            "copied_lexml": self.copied_lexml,
            "results": [
                {
                    "url": r.url,
                    "title": r.title,
                    "ok": r.ok,
                    "skipped": r.skipped,
                    "skip_reason": r.skip_reason,
                    "error": r.error,
                    "char_count": r.char_count,
                    "content_hash": r.content_hash,
                }
                for r in self.results
            ],
        }


def build_recollection_record(
    source: dict[str, Any],
    *,
    content: str,
    recollection_source: str,
) -> dict[str, Any]:
    url = normalize_norma_url(str(source.get("url") or ""))
    text = content.strip()
    out = dict(source)
    out["url"] = url
    out["content"] = text
    out["summary"] = extract_summary(text)
    out["source_domain"] = "www.planalto.gov.br"
    out["collection"] = "legislacao_agu_recollection"
    out["scraped_at"] = _utc_now()
    out["recollected_at"] = out["scraped_at"]
    out["recollection_source"] = recollection_source
    out["original_scraped_at"] = source.get("scraped_at")
    out["content_hash"] = content_hash(text)
    out["encoding_verified"] = not has_encoding_corruption(text)
    rid = hashlib.sha256(f"{url}:{out['content_hash']}".encode()).hexdigest()[:40]
    out["id"] = source.get("id") or rid
    return out


def fetch_planalto_record(rec: dict[str, Any], *, delay_s: float = 0.35) -> RecollectResult:
    url = normalize_norma_url(str(rec.get("url") or ""))
    title = str(rec.get("title") or url)
    if not is_planalto_url(url):
        return RecollectResult(url, title, ok=False, skipped=True, skip_reason="not_planalto")
    try:
        if delay_s > 0:
            time.sleep(delay_s)
        fetched = fetch_planalto_text(url)
        text = fetched.text.strip()
        if len(text) < 200:
            return RecollectResult(
                url, title, ok=False, error=f"texto curto ({len(text)} chars)"
            )
        if has_encoding_corruption(text):
            return RecollectResult(url, title, ok=False, error="encoding ainda corrompido")
        return RecollectResult(
            url,
            title,
            ok=True,
            char_count=len(text),
            content_hash=fetched.content_hash,
            text=text,
        )
    except Exception as exc:
        return RecollectResult(url, title, ok=False, error=str(exc))


def write_backup_readme(backup_root: Path) -> None:
    readme = backup_root / "README.md"
    if readme.is_file():
        return
    readme.write_text(
        """# Legislação AGU — re-coleta Planalto (backup)

Pasta **separada** de `data/legislacao_agu/` para facilitar backup e versionamento
(em repositório git próprio, se desejar).

## Conteúdo

- `runs/<timestamp>/legislacao_agu_recollection.jsonl` — normas re-coletadas com encoding ISO-8859-1
- `runs/<timestamp>/report.json` — relatório da execução
- `manifest.json` — último run e totais
- `state.json` — URLs já re-coletadas com sucesso

## Gerar

```bash
python3 scripts/recollect_agu_planalto_legislacao.py
```

## Ingerir no Lex (opcional)

```bash
export AGU_LEGIS_INPUT_DIR="$(pwd)/data/legislacao_agu_recollection/runs/<timestamp>"
python3 scripts/ingest_agu_legislacao_from_scraper.py --force
```
""",
        encoding="utf-8",
    )


def run_recollection(
    *,
    source_dir: Path,
    backup_root: Path,
    only_corrupt: bool = True,
    include_lexml_copy: bool = False,
    delay_s: float = 0.35,
    limit: int | None = None,
) -> tuple[Path, RecollectRunReport]:
    source_dir = source_dir.expanduser().resolve()
    backup_root = backup_root.expanduser().resolve()
    backup_root.mkdir(parents=True, exist_ok=True)
    write_backup_readme(backup_root)

    run_id = _run_id()
    run_dir = backup_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    out_jsonl = run_dir / "legislacao_agu_recollection.jsonl"

    report = RecollectRunReport(
        run_id=run_id,
        source_dir=str(source_dir),
        output_dir=str(backup_root),
        started_at=_utc_now(),
    )

    records = load_source_records(source_dir)
    candidates: list[dict[str, Any]] = []
    lexml_copies: list[dict[str, Any]] = []

    for rec in records.values():
        url = normalize_norma_url(str(rec.get("url") or ""))
        if is_planalto_url(url):
            if only_corrupt and not needs_planalto_recollection(rec):
                continue
            candidates.append(rec)
        elif include_lexml_copy:
            lexml_copies.append(rec)

    if limit is not None:
        candidates = candidates[: max(0, limit)]

    report.total_candidates = len(candidates)
    written: list[dict[str, Any]] = []

    with out_jsonl.open("w", encoding="utf-8") as out_fh:
        for rec in candidates:
            title = str(rec.get("title") or "")
            result = fetch_planalto_record(rec, delay_s=delay_s)
            report.results.append(result)

            if result.skipped:
                report.skipped += 1
                continue
            if not result.ok or not result.text:
                report.failed += 1
                print(f"[FAIL] {title}: {result.error}", flush=True)
                continue

            row = build_recollection_record(
                rec,
                content=result.text,
                recollection_source="naintegra_planalto_fetch",
            )
            out_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            written.append(row)
            report.fetched_ok += 1
            print(f"[OK] {title} ({result.char_count} chars)", flush=True)

        if include_lexml_copy:
            for rec in lexml_copies:
                row = dict(rec)
                row["collection"] = "legislacao_agu_recollection"
                row["recollection_source"] = "lexml_snapshot"
                row["recollected_at"] = _utc_now()
                out_fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                report.copied_lexml += 1

    report.finished_at = _utc_now()
    report_path = run_dir / "report.json"
    report_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifest = {
        "last_run_id": run_id,
        "last_run_at": report.finished_at,
        "backup_root": str(backup_root),
        "last_jsonl": str(out_jsonl),
        "last_report": str(report_path),
        "fetched_ok": report.fetched_ok,
        "failed": report.failed,
    }
    (backup_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    state_path = backup_root / "state.json"
    state: dict[str, Any] = {}
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
    urls = state.setdefault("urls_ok", {})
    for row in written:
        u = normalize_norma_url(str(row.get("url") or ""))
        if u:
            urls[u] = {
                "title": row.get("title"),
                "content_hash": row.get("content_hash"),
                "run_id": run_id,
                "recollected_at": row.get("recollected_at"),
            }
    state["updated_at"] = report.finished_at
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    latest = backup_root / "latest.jsonl"
    if out_jsonl.is_file() and out_jsonl.stat().st_size > 0:
        latest.write_bytes(out_jsonl.read_bytes())

    return out_jsonl, report
