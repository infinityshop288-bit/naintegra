from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterator
from pathlib import Path

logger = logging.getLogger(__name__)

_UTF8_BOM = b"\xef\xbb\xbf"


def iter_inbox_files(inbox: Path, glob_pattern: str, include_json: bool) -> list[Path]:
    if not inbox.exists():
        logger.warning("Inbox não existe: %s", inbox)
        return []
    files = sorted(inbox.glob(glob_pattern))
    if include_json:
        files.extend(sorted(inbox.glob("*.json")))
    return sorted({p.resolve() for p in files if p.is_file()})


def iter_records_from_file(path: Path) -> Iterator[dict]:
    if path.suffix.lower() == ".jsonl":
        with path.open("rb") as f:
            line_no = 0
            while True:
                byte_offset = f.tell()
                line_bytes = f.readline()
                if not line_bytes:
                    break
                line_no += 1
                raw_content = line_bytes.rstrip(b"\r\n")
                if not raw_content.strip():
                    continue
                if raw_content.lstrip().startswith(b"#"):
                    continue
                digest = hashlib.sha256(raw_content).hexdigest()
                try:
                    text = raw_content.decode("utf-8")
                    obj = json.loads(text.strip())
                except (UnicodeDecodeError, json.JSONDecodeError) as e:
                    logger.warning("JSONL inválido %s:%s: %s", path, line_no, e)
                    continue
                if isinstance(obj, dict):
                    obj["_source_file"] = str(path)
                    obj["_source_line"] = line_no
                    obj["_source_byte_offset"] = byte_offset
                    obj["_verbatim_payload_sha256"] = digest
                    yield obj
                else:
                    logger.warning("Linha %s:%s não é objeto JSON", path, line_no)
        return

    if path.suffix.lower() == ".json":
        raw_bytes = path.read_bytes()
        bom_len = len(_UTF8_BOM) if raw_bytes.startswith(_UTF8_BOM) else 0
        try:
            text = raw_bytes.decode("utf-8")
            obj = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            logger.warning("JSON inválido %s: %s", path, e)
            return
        file_digest = hashlib.sha256(raw_bytes).hexdigest()
        if isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, dict):
                    digest = hashlib.sha256(
                        json.dumps(item, sort_keys=True, ensure_ascii=False).encode("utf-8")
                    ).hexdigest()
                    item["_source_file"] = str(path)
                    item["_source_index"] = i
                    item["_verbatim_payload_sha256"] = digest
                    item["_verbatim_parent_file_sha256"] = file_digest
                    yield item
        elif isinstance(obj, dict):
            obj["_source_file"] = str(path)
            obj["_verbatim_payload_sha256"] = file_digest
            obj["_source_byte_offset"] = bom_len
            yield obj
