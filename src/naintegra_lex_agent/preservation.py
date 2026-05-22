from __future__ import annotations

import hashlib
import shutil
from pathlib import Path


def copy_inbox_files_to_preservation(
    files: list[Path],
    raw_preserved_root: Path,
    batch_id: str,
) -> dict[Path, str]:
    """Copia arquivos da inbox sem alteração de bytes. Retorna mapa inbox_resolvido → caminho relativo a raw_preserved_root."""

    batch_dir = raw_preserved_root / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    root_resolved = raw_preserved_root.resolve()
    mapping: dict[Path, str] = {}
    used_dest_names: set[str] = set()

    for path in files:
        resolved = path.resolve()
        dest = batch_dir / path.name
        dest_name = dest.name
        if dest.exists() or dest_name in used_dest_names:
            h = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:10]
            dest = batch_dir / f"{path.stem}_{h}{path.suffix}"
            dest_name = dest.name
        used_dest_names.add(dest_name)
        shutil.copy2(path, dest)
        dest_resolved = dest.resolve()
        mapping[resolved] = str(dest_resolved.relative_to(root_resolved))
    return mapping
