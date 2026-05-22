from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class StateStore:
    """Evita reprocessar o mesmo conteúdo quando o arquivo permanece no inbox."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute(
            """
            create table if not exists processed (
              external_id text primary key,
              content_hash text not null,
              updated_at text not null default (datetime('now'))
            )
            """
        )
        self._conn.commit()

    def should_skip(self, external_id: str, content_hash: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "select content_hash from processed where external_id = ?", (external_id,)
            )
            row = cur.fetchone()
            return row is not None and row[0] == content_hash

    def mark(self, external_id: str, content_hash: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                insert into processed (external_id, content_hash)
                values (?, ?)
                on conflict(external_id) do update set
                  content_hash = excluded.content_hash,
                  updated_at = datetime('now')
                """,
                (external_id, content_hash),
            )
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()
