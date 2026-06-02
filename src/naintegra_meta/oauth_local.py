"""OAuth Meta — fluxo manual (sem localhost; evita erro de domínio do app)."""

from __future__ import annotations

import webbrowser
from urllib.parse import quote

from naintegra_meta.token_sync import SCOPES, MetaTokenSyncError, page_token_from_user_token

# Redirect oficial Meta — já permitido na maioria dos apps; não exige 127.0.0.1 em App Domains.
LOGIN_SUCCESS = "https://www.facebook.com/connect/login_success.html"


def build_oauth_url(app_id: str) -> str:
    return (
        "https://www.facebook.com/v23.0/dialog/oauth?"
        f"client_id={app_id}&redirect_uri={quote(LOGIN_SUCCESS, safe='')}"
        f"&scope={SCOPES}&response_type=token&display=page"
    )


def oauth_manual_user_token(app_id: str, *, open_browser: bool = True) -> str:
    """Abre OAuth Meta; usuário cola access_token da barra de URL após login."""
    url = build_oauth_url(app_id)
    print("\n=== Autorização Meta (sem localhost) ===\n", flush=True)
    print("1) Faça login e autorize no browser")
    print("2) Na barra de endereço, copie o valor após  #access_token=  (até &expires_in)\n")
    print(url, "\n", flush=True)
    if open_browser:
        webbrowser.open(url)
    user_token = input("Cole o access_token aqui: ").strip()
    if not user_token:
        raise MetaTokenSyncError("Token vazio.")
    if user_token.startswith("EAA"):
        return user_token
    # usuário colou URL inteira
    if "access_token=" in user_token:
        from urllib.parse import parse_qs, urlparse

        frag = user_token.split("#", 1)[-1] if "#" in user_token else user_token.split("access_token=", 1)[-1]
        if frag.startswith("access_token="):
            frag = frag.split("access_token=", 1)[1]
        parsed = parse_qs(frag.replace("&", "&"))
        tok = parsed.get("access_token", [frag.split("&")[0]])[0]
        if tok.startswith("EAA"):
            return tok
    raise MetaTokenSyncError("Token inválido — copie só o access_token (começa com EAA…)")


def renew_via_manual_oauth(app_id: str, app_secret: str) -> dict[str, str]:
    user_token = oauth_manual_user_token(app_id)
    return page_token_from_user_token(app_id, app_secret, user_token)
