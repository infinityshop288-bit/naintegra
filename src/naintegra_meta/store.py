"""Persistência Supabase para fila de conteúdo e automações."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx

from naintegra_meta.settings import MetaSettings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DelegadoStore:
    def __init__(self, settings: MetaSettings) -> None:
        self.settings = settings
        self.schema = settings.delegado_schema
        self.base = (settings.supabase_url or "").rstrip("/")
        self.key = settings.supabase_service_role_key or settings.supabase_anon_key or ""

    @property
    def configured(self) -> bool:
        return bool(self.base and self.key)

    def _headers(self, user_jwt: str | None = None) -> dict[str, str]:
        token = user_jwt or self.key
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept-Profile": self.schema,
            "Content-Profile": self.schema,
        }

    def _table(self, name: str) -> str:
        return f"{self.base}/rest/v1/{name}"

    async def list_queue(self, user_jwt: str) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                self._table("content_queue"),
                headers=self._headers(user_jwt),
                params={"select": "*", "order": "scheduled_at.asc.nullslast,created_at.desc"},
            )
        if resp.status_code >= 400:
            return []
        return resp.json()

    async def upsert_queue_item(self, user_jwt: str, item: dict[str, Any]) -> dict[str, Any]:
        payload = {**item}
        if not payload.get("id"):
            payload["id"] = str(uuid4())
        payload.setdefault("created_at", _now_iso())
        payload["updated_at"] = _now_iso()
        if not self.configured:
            return payload
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self._table("content_queue"),
                headers={**self._headers(user_jwt), "Prefer": "return=representation,resolution=merge-duplicates"},
                json=payload,
            )
        if resp.status_code >= 400:
            raise RuntimeError(resp.text[:500])
        rows = resp.json()
        return rows[0] if isinstance(rows, list) and rows else payload

    async def delete_queue_item(self, user_jwt: str, item_id: str) -> None:
        if not self.configured:
            return
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.delete(
                self._table("content_queue"),
                headers=self._headers(user_jwt),
                params={"id": f"eq.{item_id}"},
            )

    async def list_automations(self, user_jwt: str) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                self._table("automations"),
                headers=self._headers(user_jwt),
                params={"select": "*", "order": "nome.asc"},
            )
        if resp.status_code >= 400:
            return []
        return resp.json()

    async def set_automation_status(
        self, user_jwt: str, automation_id: str, status: str
    ) -> dict[str, Any]:
        if not self.configured:
            return {"id": automation_id, "status": status}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.patch(
                self._table("automations"),
                headers={**self._headers(user_jwt), "Prefer": "return=representation"},
                params={"id": f"eq.{automation_id}"},
                json={"status": status, "updated_at": _now_iso()},
            )
        if resp.status_code >= 400:
            raise RuntimeError(resp.text[:500])
        rows = resp.json()
        return rows[0] if isinstance(rows, list) and rows else {"id": automation_id, "status": status}

    async def log_insight_snapshot(self, user_jwt: str, snapshot: dict[str, Any]) -> None:
        if not self.configured:
            return
        payload = {**snapshot, "captured_at": _now_iso()}
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                self._table("insight_snapshots"),
                headers=self._headers(user_jwt),
                json=payload,
            )

    async def list_insight_snapshots(self, user_jwt: str, limit: int = 30) -> list[dict[str, Any]]:
        if not self.configured:
            return []
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                self._table("insight_snapshots"),
                headers=self._headers(user_jwt),
                params={
                    "select": "*",
                    "order": "captured_at.desc",
                    "limit": str(limit),
                },
            )
        if resp.status_code >= 400:
            return []
        return resp.json()
