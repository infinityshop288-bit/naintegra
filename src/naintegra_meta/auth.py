"""Autenticação Supabase JWT + allowlist de e-mails."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from naintegra_meta.settings import MetaSettings, _env_first

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str


def _settings() -> MetaSettings:
    return MetaSettings()


async def get_bearer_token(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if creds is None or not creds.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token ausente")
    return creds.credentials.strip()


async def require_delegado_user(
    jwt: str = Depends(get_bearer_token),
    settings: MetaSettings = Depends(_settings),
) -> AuthUser:
    supabase_url = (settings.supabase_url_resolved or "").rstrip("/")
    anon_key = settings.supabase_anon_key or _env_first("SUPABASE_ANON_KEY")
    if not supabase_url or not anon_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Supabase não configurado")

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            f"{supabase_url}/auth/v1/user",
            headers={"Authorization": f"Bearer {jwt}", "apikey": anon_key},
        )

    if resp.status_code in (401, 403):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida")
    if resp.status_code >= 400:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Falha ao validar sessão")

    body = resp.json()
    user_id = body.get("id")
    email = (body.get("email") or "").strip().lower()
    if not user_id or not email:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido")

    if email not in settings.allowed_email_set:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito ao dashboard @delegadoluizcarlos",
        )

    return AuthUser(id=user_id, email=email)
