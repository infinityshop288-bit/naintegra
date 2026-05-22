from __future__ import annotations

import json
import logging
from pathlib import Path

from .schemas import NormalizedDocument

logger = logging.getLogger(__name__)


def write_organized_manifest(
    organized_root: Path,
    batch_id: str,
    documents: list[NormalizedDocument],
    *,
    kind: str = "organização",
) -> Path | None:
    """Escreve apenas camadas derivadas + referências ao material preservado (sem regravar o arquivo bruto)."""

    if not documents:
        return None
    batch_dir = organized_root / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = batch_dir / "manifest.jsonl"

    with manifest_path.open("w", encoding="utf-8") as f:
        for doc in documents:
            derivative_meta = {k: v for k, v in doc.meta.items() if str(k).lower().startswith("ai")}
            verbatim_meta = {k: v for k, v in doc.meta.items() if k not in derivative_meta}
            exp = verbatim_meta.pop("explicacao", None)
            gab = verbatim_meta.pop("gabarito", None)
            gab_disc = verbatim_meta.pop("gabarito_discursivo", None)
            if gab_disc is None:
                gab_disc = verbatim_meta.pop("resposta_oficial", None)
            verbatim = {
                "titulo": doc.title,
                "dispositivo_legal": doc.body,
                "texto": doc.body,
                "source_system": doc.source_system,
                "crawl_batch_id": doc.crawl_batch_id,
                "meta": verbatim_meta,
            }
            if exp:
                verbatim["explicacao"] = exp
            if gab is not None and str(gab).strip():
                verbatim["gabarito"] = str(gab).strip()
            if gab_disc is not None and str(gab_disc).strip():
                verbatim["gabarito_discursivo"] = str(gab_disc).strip()
            row = {
                "external_id": doc.external_id,
                "preservation": doc.preservation,
                "verbatim": verbatim,
                "organization": {
                    "doc_type": doc.doc_type.value,
                    "organized": doc.organized,
                },
                "derivative": derivative_meta,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    logger.info("Manifesto (%s) gravado em %s (%s itens)", kind, manifest_path, len(documents))
    return manifest_path
