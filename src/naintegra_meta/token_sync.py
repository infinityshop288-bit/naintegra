"""Validação e renovação do Page Access Token (somente META_ACCESS_TOKEN no .env)."""

from __future__ import annotations

import httpx

from naintegra_meta.settings import MetaSettings

GRAPH = "https://graph.facebook.com/v23.0"
EXPECTED_IG = "delegadoluizcarlos"
SCOPES = (
    "pages_show_list,pages_read_engagement,pages_manage_posts,instagram_basic,"
    "instagram_content_publish,instagram_manage_comments,instagram_manage_insights,"
    "ads_read,ads_management,business_management"
)


class MetaTokenSyncError(Exception):
    pass


def _app_token(app_id: str, app_secret: str) -> str:
    return f"{app_id}|{app_secret}"


def debug_token(token: str, app_id: str, app_secret: str) -> dict:
    r = httpx.get(
        f"{GRAPH}/debug_token",
        params={"input_token": token, "access_token": _app_token(app_id, app_secret)},
        timeout=30,
    )
    return r.json().get("data") or {}


def token_is_valid(settings: MetaSettings) -> bool:
    token = settings.meta_access_token or ""
    app_id = settings.meta_app_id or ""
    app_secret = settings.meta_app_secret or ""
    if not token or not app_id or not app_secret:
        return False
    return debug_token(token, app_id, app_secret).get("is_valid") is True


def _exchange_long_lived(app_id: str, app_secret: str, user_token: str) -> str:
    r = httpx.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": user_token,
        },
        timeout=60,
    )
    body = r.json()
    token = body.get("access_token")
    if not token:
        err = body.get("error", {})
        raise MetaTokenSyncError(err.get("message", str(body)))
    return token


def _list_pages(user_token: str) -> list[dict]:
    r = httpx.get(
        f"{GRAPH}/me/accounts",
        params={
            "access_token": user_token,
            "fields": "id,name,access_token,instagram_business_account{id,username}",
        },
        timeout=60,
    )
    body = r.json()
    if "error" in body:
        raise MetaTokenSyncError(body["error"].get("message", str(body)))
    return body.get("data") or []


def page_token_from_user_token(app_id: str, app_secret: str, user_token: str) -> dict[str, str]:
    dbg = debug_token(user_token, app_id, app_secret)
    if not dbg.get("is_valid"):
        err = (dbg.get("error") or {}).get("message", "token inválido")
        raise MetaTokenSyncError(err)

    # Page tokens via /me/accounts; tenta long-lived quando possível.
    try:
        list_token = _exchange_long_lived(app_id, app_secret, user_token)
    except MetaTokenSyncError:
        list_token = user_token
    pages = _list_pages(list_token)
    if not pages:
        raise MetaTokenSyncError("Nenhuma página Facebook encontrada.")

    target = next(
        (p for p in pages if (p.get("instagram_business_account") or {}).get("username") == EXPECTED_IG),
        pages[0],
    )
    page_token = target.get("access_token")
    if not page_token:
        raise MetaTokenSyncError("Página sem access_token.")

    if not debug_token(page_token, app_id, app_secret).get("is_valid"):
        raise MetaTokenSyncError("Page token gerado inválido.")

    ig = target.get("instagram_business_account") or {}
    return {
        "META_ACCESS_TOKEN": page_token,
        "FB_PAGE_ID": str(target.get("id") or ""),
        "IG_USER_ID": str(ig.get("id") or ""),
    }


def save_page_token_direct(page_token: str, settings: MetaSettings) -> dict[str, str]:
    """Valida e persiste Page Token colado do Graph API Explorer."""
    app_id = settings.meta_app_id or ""
    app_secret = settings.meta_app_secret or ""
    if not app_id or not app_secret:
        raise MetaTokenSyncError("META_APP_ID e META_APP_SECRET obrigatórios")

    dbg = debug_token(page_token, app_id, app_secret)
    if not dbg.get("is_valid"):
        err = (dbg.get("error") or {}).get("message", "token inválido")
        raise MetaTokenSyncError(err)

    fb_page = settings.fb_page_id or ""
    ig_user = settings.ig_user_id or ""

    r = httpx.get(
        f"{GRAPH}/{fb_page}",
        params={"fields": "id,name,instagram_business_account{id,username}", "access_token": page_token},
        timeout=30,
    )
    page = r.json()
    if "error" in page:
        pages = httpx.get(
            f"{GRAPH}/me/accounts",
            params={
                "access_token": page_token,
                "fields": "id,name,access_token,instagram_business_account{id,username}",
            },
            timeout=30,
        ).json().get("data") or []
        target = next(
            (p for p in pages if (p.get("instagram_business_account") or {}).get("username") == EXPECTED_IG),
            pages[0] if pages else None,
        )
        if not target:
            raise MetaTokenSyncError("Token válido mas sem acesso à página do @delegadoluizcarlos")
        page_token = target.get("access_token") or page_token
        fb_page = str(target.get("id") or fb_page)
        ig = target.get("instagram_business_account") or {}
        ig_user = str(ig.get("id") or ig_user)
    else:
        ig = page.get("instagram_business_account") or {}
        if ig.get("username") != EXPECTED_IG:
            raise MetaTokenSyncError(f"Página vinculada a @{ig.get('username')}, esperado @{EXPECTED_IG}")
        ig_user = str(ig.get("id") or ig_user)

    return {
        "META_ACCESS_TOKEN": page_token,
        "FB_PAGE_ID": fb_page,
        "IG_USER_ID": ig_user,
    }


def verify_pairing(settings: MetaSettings) -> dict:
    """Valida pareamento Page ↔ IG usando META_ACCESS_TOKEN atual."""
    token = settings.meta_access_token or ""
    fb_page = settings.fb_page_id or ""
    ig_user = settings.ig_user_id or ""
    app_id = settings.meta_app_id or ""
    app_secret = settings.meta_app_secret or ""

    result: dict = {"valid": False, "checks": {}}
    if not token:
        result["checks"]["token"] = "META_ACCESS_TOKEN vazio"
        return result

    dbg = debug_token(token, app_id, app_secret) if app_id and app_secret else {}
    result["checks"]["token_valid"] = dbg.get("is_valid") is True
    result["checks"]["token_type"] = dbg.get("type")
    result["checks"]["scopes"] = len(dbg.get("scopes") or [])
    if dbg.get("error"):
        result["checks"]["token_error"] = dbg["error"].get("message", "")

    if not dbg.get("is_valid"):
        return result

    r = httpx.get(
        f"{GRAPH}/{fb_page}",
        params={
            "fields": "id,name,instagram_business_account{id,username,followers_count}",
            "access_token": token,
        },
        timeout=30,
    )
    page = r.json()
    if "error" in page:
        result["checks"]["page_error"] = page["error"].get("message", "")
        return result

    ig = page.get("instagram_business_account") or {}
    result["checks"]["page_name"] = page.get("name")
    result["checks"]["ig_username"] = ig.get("username")
    result["checks"]["ig_id_match"] = ig.get("id") == ig_user
    result["checks"]["followers"] = ig.get("followers_count")
    result["valid"] = ig.get("username") == EXPECTED_IG and ig.get("id") == ig_user
    return result
