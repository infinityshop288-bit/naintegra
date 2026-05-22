from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path


class AIDecisionCache:
    """Replica decisões da IA: mesma chave de conteúdo → mesmos campos organizados."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute(
            """
            create table if not exists ai_decisions (
              cache_key text primary key,
              payload_json text not null,
              created_at text not null default (datetime('now'))
            )
            """
        )
        self._conn.commit()

    def get(self, cache_key: str) -> dict | None:
        with self._lock:
            cur = self._conn.execute(
                "select payload_json from ai_decisions where cache_key = ?", (cache_key,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return json.loads(row[0])

    def set(self, cache_key: str, payload: dict) -> None:
        with self._lock:
            self._conn.execute(
                """
                insert into ai_decisions (cache_key, payload_json)
                values (?, ?)
                on conflict(cache_key) do update set
                  payload_json = excluded.payload_json,
                  created_at = datetime('now')
                """,
                (cache_key, json.dumps(payload, ensure_ascii=False)),
            )
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()
