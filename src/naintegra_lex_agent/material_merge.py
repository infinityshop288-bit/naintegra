"""Funde JSONL de várias pastas num único corpus na inbox (dedupe por id)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .settings import Settings

logger = logging.getLogger(__name__)


def settings_with_trilhante_informativo_root(settings: Settings) -> Settings:
    """Inclui ``trilhante_informativo_root`` em ``material_merge_extra_roots`` (uma vez, sem duplicar)."""

    root = settings.trilhante_informativo_root
    if root is None:
        return settings
    path = Path(root).expanduser()
    try:
        resolved = str(path.resolve())
    except OSError:
        resolved = str(path)
    roots = [r.strip() for r in settings.material_merge_extra_roots.split(",") if r.strip()]
    if resolved not in roots:
        roots.append(resolved)
    return settings.model_copy(update={"material_merge_extra_roots": ",".join(roots)})


def _merge_key(record: dict[str, Any]) -> str:
    for key in ("external_id", "id", "urn", "lexml_id", "hash_id", "public_id"):
        val = record.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    payload = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"_anon:{hash(payload)}"


def _iter_plain_records(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as e:
                logger.warning("JSONL ignorado %s: %s", path, e)
                continue
            if isinstance(obj, dict):
                yield obj


def merge_material_into_corpus(settings: Settings) -> Path:
    """Mescla extra_roots + demais *.jsonl da inbox (exceto o destino) em corpus único."""

    inbox = settings.crawl_inbox_path.resolve()
    dest = inbox / settings.corpus_output_name
    merged: dict[str, dict[str, Any]] = {}

    # Corpus atual primeiro (menor prioridade); extras e demais JSONL na inbox sobrescrevem por id.
    paths_list: list[Path] = []
    if dest.exists():
        paths_list.append(dest)

    roots = [r.strip() for r in settings.material_merge_extra_roots.split(",") if r.strip()]
    for root in roots:
        p = Path(root)
        if not p.is_dir():
            logger.debug("Pasta de fusão inexistente (pulada): %s", p)
            continue
        paths_list.extend(sorted(p.glob("**/*.jsonl")))

    if inbox.exists():
        for p in sorted(inbox.glob("*.jsonl")):
            if p.name == settings.corpus_output_name:
                continue
            paths_list.append(p)

    seen_paths: set[Path] = set()
    ordered: list[Path] = []
    for p in paths_list:
        rp = p.resolve()
        if rp in seen_paths:
            continue
        seen_paths.add(rp)
        ordered.append(rp)

    for path in ordered:
        if not path.is_file():
            continue
        if path.name in ("manifest.jsonl",):
            continue
        for obj in _iter_plain_records(path):
            merged[_merge_key(obj)] = obj

    inbox.mkdir(parents=True, exist_ok=True)
    header = "# NaIntegra Lex — corpus consolidado (fusão automática de fontes)."
    lines_out = [header]
    for key in sorted(merged.keys()):
        lines_out.append(json.dumps(merged[key], ensure_ascii=False))
    dest.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    logger.info(
        "Corpus fundido em %s (%s registros únicos; %s arquivos-fonte)",
        dest,
        len(merged),
        len(ordered),
    )
    return dest
