#!/usr/bin/env python3
"""Verifica integrações do dashboard @delegadoluizcarlos."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Carrega .env manualmente (sem expor valores)
ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
if ENV.exists():
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k and k not in os.environ:
            os.environ[k] = v

sys.path.insert(0, str(ROOT / "src"))

import httpx

from naintegra_meta.settings import MetaSettings

settings = MetaSettings()
results: list[dict] = []


def ok(name: str, detail: str = "OK") -> None:
    results.append({"check": name, "status": "ok", "detail": detail})
    print(f"  ✓ {name}: {detail}")


def warn(name: str, detail: str) -> None:
    results.append({"check": name, "status": "warn", "detail": detail})
    print(f"  ⚠ {name}: {detail}")


def fail(name: str, detail: str) -> None:
    results.append({"check": name, "status": "fail", "detail": detail})
    print(f"  ✗ {name}: {detail}")


print("\n=== Verificação Dashboard @delegadoluizcarlos ===\n")

# --- Config ---
print("[Configuração .env]")
if settings.meta_access_token:
    ok("META_ACCESS_TOKEN", f"presente ({len(settings.meta_access_token)} chars)")
else:
    fail("META_ACCESS_TOKEN", "VAZIO — obrigatório para Graph API")

ig = settings.ig_user_id or ""
if ig.isdigit():
    ok("IG_USER_ID", f"id numérico ({ig})")
elif ig:
    warn("IG_USER_ID", f"'{ig}' parece username, não ID numérico da conta Business")
else:
    fail("IG_USER_ID", "não configurado")

if settings.fb_page_id:
    ok("FB_PAGE_ID", settings.fb_page_id)
else:
    warn("FB_PAGE_ID", "não configurado")

if settings.meta_ad_account_id:
    act = settings.meta_ad_account_id
    ok("META_AD_ACCOUNT_ID", act if act.startswith("act_") else f"act_{act} (prefixo auto)")
else:
    warn("META_AD_ACCOUNT_ID", "não configurado")

if settings.anthropic_api_key:
    key = settings.anthropic_api_key
    if key.startswith("sk-ant-"):
        ok("ANTHROPIC_API_KEY", "formato sk-ant-…")
    else:
        warn("ANTHROPIC_API_KEY", "formato atípico (esperado sk-ant-…)")
else:
    fail("ANTHROPIC_API_KEY", "não configurado")

if settings.supabase_url and settings.supabase_anon_key:
    ok("SUPABASE", settings.supabase_url)
else:
    fail("SUPABASE", "URL ou anon key ausente")

print("\n[Meta Graph API]")
if settings.meta_access_token:
    try:
        from naintegra_meta.meta_client import MetaClient, MetaApiError

        client = MetaClient(settings.meta_access_token)
        dbg = client.debug_token()
        data = dbg.get("data") or {}
        is_valid = data.get("is_valid")
        expires = data.get("expires_at", "?")
        scopes = data.get("scopes") or []
        if is_valid:
            ok("debug_token", f"válido, expira em {expires}, {len(scopes)} permissões")
            needed = {"instagram_basic", "instagram_content_publish", "pages_read_engagement"}
            missing = needed - set(scopes)
            if missing:
                warn("permissoes_ig", f"faltam: {', '.join(sorted(missing))}")
            else:
                ok("permissoes_ig", "básicas presentes")
        else:
            fail("debug_token", "token inválido ou expirado")
    except MetaApiError as e:
        fail("debug_token", str(e)[:200])
    except Exception as e:
        fail("debug_token", f"{type(e).__name__}: {e}")

    if settings.ig_user_id and settings.ig_user_id.isdigit():
        try:
            from naintegra_meta.meta_client import InstagramFacebook, MetaApiError

            ig_client = InstagramFacebook(
                client,
                ig_user_id=settings.ig_user_id,
                fb_page_id=settings.fb_page_id,
            )
            profile = ig_client.profile()
            ok("instagram_profile", f"@{profile.get('username')} — {profile.get('followers_count')} seguidores")
            try:
                ig_client.account_insights(period="day")
                ok("instagram_insights", "Graph API insights OK")
            except MetaApiError:
                summary = ig_client.media_engagement_summary(limit=5)
                ok(
                    "instagram_insights",
                    f"fallback media_api ({summary.get('total_interactions')} interações em {summary.get('posts_analyzed')} posts)",
                )
        except MetaApiError as e:
            fail("instagram_profile", str(e)[:200])
else:
    warn("meta_api", "pulado (sem token)")

print("\n[Anthropic / Claude]")
if settings.anthropic_api_key:
    try:
        with httpx.Client(timeout=30.0) as http:
            r = http.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.anthropic_model,
                    "max_tokens": 32,
                    "messages": [{"role": "user", "content": "Responda só: ok"}],
                },
            )
        if r.status_code == 200:
            ok("claude_api", f"modelo {settings.anthropic_model}")
        else:
            err = r.json().get("error", {}).get("message", r.text[:150])
            if "credit balance" in err.lower():
                try:
                    from naintegra_meta.content_ai import generate_content_ideas

                    ideas, src = generate_content_ideas("teste", "carrossel", settings=settings)
                    if src == "fallback" and ideas:
                        warn("claude_api", f"sem créditos — fallback local ativo ({len(ideas)} ideias)")
                    else:
                        fail("claude_api", f"HTTP {r.status_code}: {err}")
                except Exception:
                    warn("claude_api", f"sem créditos — usando fallback local")
            else:
                fail("claude_api", f"HTTP {r.status_code}: {err}")
    except Exception as e:
        fail("claude_api", str(e)[:200])

print("\n[Supabase]")
if settings.supabase_url and settings.supabase_anon_key:
    try:
        with httpx.Client(timeout=15.0) as http:
            r = http.get(
                f"{settings.supabase_url.rstrip('/')}/rest/v1/",
                headers={"apikey": settings.supabase_anon_key},
            )
        if r.status_code < 500:
            ok("supabase_reach", f"HTTP {r.status_code}")
        else:
            fail("supabase_reach", f"HTTP {r.status_code}")

        with httpx.Client(timeout=15.0) as http:
            r = http.get(
                f"{settings.supabase_url.rstrip('/')}/rest/v1/content_queue",
                headers={
                    "apikey": settings.supabase_anon_key,
                    "Accept-Profile": "delegado",
                },
                params={"select": "id", "limit": "1"},
            )
        if r.status_code == 200:
            ok("schema_delegado", "tabela content_queue acessível")
        elif r.status_code == 404:
            fail("schema_delegado", "PostgREST não enxerga delegado — rode NOTIFY pgrst reload ou configure_delegado_supabase.sh")
        elif r.status_code == 406:
            warn("schema_delegado", "schema delegado não exposto na API (Settings → Exposed schemas)")
        else:
            warn("schema_delegado", f"HTTP {r.status_code} — migration ou RLS pendente")
    except Exception as e:
        fail("supabase", str(e)[:200])

print("\n[API FastAPI]")
try:
    from naintegra_meta.api import app

    ok("fastapi_app", app.title)
except Exception as e:
    fail("fastapi_app", str(e))

# Resumo
print("\n=== Resumo ===")
oks = sum(1 for r in results if r["status"] == "ok")
warns = sum(1 for r in results if r["status"] == "warn")
fails = sum(1 for r in results if r["status"] == "fail")
print(f"  {oks} OK | {warns} avisos | {fails} falhas\n")

out = ROOT / "data" / "delegado_verify.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

sys.exit(1 if fails else 0)
