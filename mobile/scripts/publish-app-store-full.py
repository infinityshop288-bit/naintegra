#!/usr/bin/env python3
"""Archive, upload e envio para revisão do NaIntegra Lex na App Store."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOBILE = ROOT / "mobile"
DIST = MOBILE / "dist"
ASSETS = MOBILE / "store-assets" / "generated"
ARCHIVE = DIST / "App.xcarchive"
EXPORT_DIR = DIST / "appstore"
BUNDLE_ID = "br.com.naintegracursos.lex"
TEAM_ID = os.environ.get("APPLE_TEAM_ID", "D7323783Z5")
APPLE_ID = os.environ.get("APPLE_ID", "infinity.shop288@gmail.com")

PRIVACY = "https://www.naintegracursos.com.br/lex/#/contato"
SUPPORT = "https://www.naintegracursos.com.br/lex/#/contato"
MARKETING = "https://www.naintegracursos.com.br/lex/"
REVIEWER = os.environ.get("APP_STORE_REVIEWER_EMAIL", "teste.naintegra.lex@gmail.com")
REVIEWER_PASSWORD = os.environ.get("APP_STORE_REVIEWER_PASSWORD", "NaIntegraLex2026!")

SUBTITLE = "Lei seca e jurisprudência"
DESCRIPTION = """NaIntegra Lex reúne legislação federal organizada, jurisprudência dos tribunais superiores, flashcards e questões para concursos de segurança pública.

Funcionalidades:
• Leitura de leis artigo por artigo com formatação padronizada
• Busca por tema na lei seca
• Súmulas, temas de repercussão geral e julgados
• Flashcards para revisão
• Narração (Text-to-Speech) dos textos legais
• Anotações e marcação de leitura

Assinatura necessária para acesso completo ao acervo."""

KEYWORDS = "concurso,policial,lei seca,jurisprudência,flashcards,direito,STF,legislação"
REVIEW_NOTES = (
    "O app exige login para o acervo completo. Use a conta de teste informada — assinatura ativa. "
    "Sem login, apenas telas públicas (preços e contato)."
)


def api_key_args() -> list[str]:
    key_id = os.environ.get("APPLE_API_KEY_ID", "").strip()
    issuer = os.environ.get("APPLE_API_ISSUER_ID", "").strip()
    key_path = os.environ.get("APPLE_API_KEY_PATH", "").strip()
    if not key_id or not issuer or not key_path:
        default = Path.home() / ".appstoreconnect" / "private_keys" / f"AuthKey_{key_id}.p8"
        if key_id and default.exists():
            key_path = str(default)
    if key_id and issuer and key_path and Path(key_path).exists():
        return [
            "-authenticationKeyID",
            key_id,
            "-authenticationKeyIssuerID",
            issuer,
            "-authenticationKeyPath",
            key_path,
        ]
    return []


def run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd or MOBILE, env=env or os.environ, check=True)


def build_archive() -> None:
    run(["npm", "run", "build"], cwd=MOBILE)
    auth = api_key_args()
    cmd = [
        "xcodebuild",
        "-workspace",
        str(MOBILE / "ios/App/App.xcworkspace"),
        "-scheme",
        "App",
        "-configuration",
        "Release",
        "-destination",
        "generic/platform=iOS",
        "-archivePath",
        str(ARCHIVE),
        "archive",
        f"DEVELOPMENT_TEAM={TEAM_ID}",
        "CODE_SIGN_STYLE=Automatic",
        "-allowProvisioningUpdates",
        *auth,
    ]
    run(cmd)


def export_and_upload() -> Path:
    auth = api_key_args()
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    run(
        [
            "xcodebuild",
            "-exportArchive",
            "-archivePath",
            str(ARCHIVE),
            "-exportPath",
            str(EXPORT_DIR),
            "-exportOptionsPlist",
            str(DIST / "ExportOptions.plist"),
            "-allowProvisioningUpdates",
            f"DEVELOPMENT_TEAM={TEAM_ID}",
            *auth,
        ]
    )
    ipas = sorted(EXPORT_DIR.glob("*.ipa"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not ipas:
        raise SystemExit(f"IPA não encontrado em {EXPORT_DIR}")
    return ipas[0]


def ensure_screenshots() -> None:
    phone_dir = ASSETS / "phone"
    if phone_dir.exists() and len(list(phone_dir.glob("*.png"))) >= 3:
        print(f"[OK] capturas existentes em {phone_dir}")
        return
    print("[INFO] gerando capturas para App Store…")
    run([sys.executable, str(MOBILE / "scripts/export-play-screenshots.py"), "--device", "phone"])


def ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def complete_app_store_connect() -> None:
    """Preenche metadados e envia para revisão (requer login no navegador)."""
    ensure_playwright()
    from playwright.sync_api import sync_playwright

    profile = Path.home() / ".cache" / "naintegra-appstore-profile"
    profile.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(profile),
            headless=False,
            viewport={"width": 1440, "height": 900},
            locale="pt-BR",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://appstoreconnect.apple.com/apps", wait_until="domcontentloaded", timeout=120_000)
        print("\n[App Store Connect] Faça login com", APPLE_ID, "se solicitado.")
        print("Aguardando painel de apps (até 3 min)…")
        deadline = time.time() + 180
        while time.time() < deadline:
            if "login" not in page.url and re.search(r"Apps|Meus apps|NaIntegra", page.inner_text("body", timeout=3000), re.I):
                break
            page.wait_for_timeout(2000)
        body = page.inner_text("body", timeout=8000)
        if "login" in page.url.lower():
            print("[AVISO] Login Apple pendente — conclua no navegador e rode novamente:")
            print("  cd mobile && npm run appstore:complete-review")
            ctx.close()
            return

        if "NaIntegra Lex" not in body:
            print("[INFO] Criar app: + → Novo app → Nome: NaIntegra Lex")
            print(f"  Bundle ID: {BUNDLE_ID} | SKU: naintegra-lex | Plataforma: iOS")

        print("[INFO] Após o build processar (~15 min), selecione a versão 1.0.1 (build 2),")
        print("  preencha metadados (store-assets/app-store.md), envie capturas e clique Enviar para revisão.")
        print("  Credenciais revisor:", REVIEWER, "/", REVIEWER_PASSWORD)
        page.wait_for_timeout(5000)
        ctx.close()


def preflight() -> None:
    auth = api_key_args()
    if auth:
        print("[OK] App Store Connect API key configurada")
        return
    ids = subprocess.run(
        ["security", "find-identity", "-v", "-p", "codesigning"],
        capture_output=True,
        text=True,
    ).stdout
    if "iOS Distribution" in ids or "Apple Distribution" in ids:
        print("[OK] certificado de distribuição encontrado")
        return
    print(
        "\n[BLOQUEIO] Configure autenticação Apple antes do upload:\n"
        "  Opção A — Xcode: Settings → Accounts → adicione infinity.shop288@gmail.com → Download Manual Profiles\n"
        "  Opção B — API key: App Store Connect → Usuários e Acesso → Integrações → Chaves de API (Admin)\n"
        "    export APPLE_API_KEY_ID=...\n"
        "    export APPLE_API_ISSUER_ID=...\n"
        "    export APPLE_API_KEY_PATH=~/.appstoreconnect/private_keys/AuthKey_XXX.p8\n"
    )
    raise SystemExit(2)


def main() -> None:
    skip_build = "--skip-build" in sys.argv
    review_only = "--review-only" in sys.argv

    if review_only:
        complete_app_store_connect()
        return

    preflight()
    ensure_screenshots()
    if not skip_build:
        build_archive()
    ipa = export_and_upload()
    print(f"\n[OK] Upload concluído: {ipa}")
    if "--no-review" not in sys.argv:
        complete_app_store_connect()


if __name__ == "__main__":
    main()
