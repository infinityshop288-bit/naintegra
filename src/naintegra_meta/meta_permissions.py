"""Checagem de permissões Meta e links de configuração."""

from __future__ import annotations

from typing import Any

import httpx

from naintegra_meta.settings import MetaSettings
from naintegra_meta.token_sync import SCOPES, debug_token, page_token_from_user_token

GRAPH = "https://graph.facebook.com/v23.0"

REQUIRED_SCOPES = {
    "instagram_manage_insights": "Insights de conta (alcance, engajamento)",
    "ads_read": "Leitura de campanhas e métricas de anúncios",
}

OPTIONAL_SCOPES = {
    "ads_management": "Criar/editar campanhas",
    "instagram_content_publish": "Publicar no Instagram",
}


class MetaPermissionsError(Exception):
    pass


def token_scopes(settings: MetaSettings) -> set[str]:
    token = settings.meta_access_token or ""
    app_id = settings.meta_app_id or ""
    app_secret = settings.meta_app_secret or ""
    if not token or not app_id or not app_secret:
        return set()
    dbg = debug_token(token, app_id, app_secret)
    return set(dbg.get("scopes") or [])


def missing_scopes_for_token(token: str, app_id: str, app_secret: str) -> dict[str, str]:
    dbg = debug_token(token, app_id, app_secret)
    have = set(dbg.get("scopes") or [])
    return {scope: label for scope, label in REQUIRED_SCOPES.items() if scope not in have}


def missing_scopes(settings: MetaSettings) -> dict[str, str]:
    token = settings.meta_access_token or ""
    app_id = settings.meta_app_id or ""
    app_secret = settings.meta_app_secret or ""
    if not token or not app_id or not app_secret:
        return dict(REQUIRED_SCOPES)
    return missing_scopes_for_token(token, app_id, app_secret)


def oauth_url(app_id: str) -> str:
    from urllib.parse import quote

    from naintegra_meta.oauth_local import LOGIN_SUCCESS

    return (
        "https://www.facebook.com/v23.0/dialog/oauth?"
        f"client_id={app_id}&redirect_uri={quote(LOGIN_SUCCESS, safe='')}"
        f"&scope={SCOPES}&response_type=token&display=page"
    )


def graph_explorer_url(app_id: str) -> str:
    return f"https://developers.facebook.com/tools/explorer/{app_id}/"


def business_id(settings: MetaSettings) -> str | None:
    token = settings.meta_access_token or ""
    page_id = settings.fb_page_id or ""
    if not token or not page_id:
        return None
    r = httpx.get(
        f"{GRAPH}/{page_id}",
        params={"fields": "business{id,name}", "access_token": token},
        timeout=30,
    )
    body = r.json()
    if "error" in body:
        return None
    return (body.get("business") or {}).get("id")


def setup_links(settings: MetaSettings) -> dict[str, str]:
    app_id = settings.meta_app_id or "2257277374806887"
    biz = business_id(settings) or ""
    act = (settings.meta_ad_account_id or "").replace("act_", "")
    links = {
        "oauth": oauth_url(app_id),
        "graph_explorer": graph_explorer_url(app_id),
        "app_review": f"https://developers.facebook.com/apps/{app_id}/app-review/permissions/",
    }
    if biz:
        links["business_apps"] = (
            f"https://business.facebook.com/settings/apps/{app_id}?business_id={biz}"
        )
        if act:
            links["ad_account"] = (
                f"https://business.facebook.com/settings/ad-accounts/{act}?business_id={biz}"
            )
            links["assign_ad_account"] = (
                f"https://business.facebook.com/settings/ad-accounts/{act}"
                f"?business_id={biz}&assign_app={app_id}"
            )
    return links


def permissions_report(settings: MetaSettings) -> dict[str, Any]:
    have = sorted(token_scopes(settings))
    missing = missing_scopes(settings)
    dbg = debug_token(
        settings.meta_access_token or "",
        settings.meta_app_id or "",
        settings.meta_app_secret or "",
    )
    return {
        "token_valid": dbg.get("is_valid") is True,
        "token_type": dbg.get("type"),
        "scopes": have,
        "missing_required": missing,
        "setup_links": setup_links(settings),
        "business_id": business_id(settings),
    }


def renew_with_insights_scope(settings: MetaSettings, user_token: str) -> dict[str, str]:
    """Converte user token em page token após reautorização com scopes completos."""
    app_id = settings.meta_app_id or ""
    app_secret = settings.meta_app_secret or ""
    if not app_id or not app_secret:
        raise MetaPermissionsError("META_APP_ID e META_APP_SECRET obrigatórios")
    updates = page_token_from_user_token(app_id, app_secret, user_token.strip())
    still_missing = missing_scopes_for_token(updates["META_ACCESS_TOKEN"], app_id, app_secret)
    if still_missing:
        names = ", ".join(still_missing)
        raise MetaPermissionsError(
            f"Token salvo, mas ainda faltam permissões: {names}. "
            "No Graph Explorer, marque instagram_manage_insights e ads_read ao gerar o token."
        )
    return updates
