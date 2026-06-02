#!/usr/bin/env python3
"""Automatiza Play Console: ficha da loja, upload AAB (teste interno) e assetlinks."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOBILE = ROOT / "mobile"
ASSETS = MOBILE / "store-assets" / "generated"
AAB = MOBILE / "dist" / "naintegra-lex-release.aab"
PACKAGE = "br.com.naintegracursos.lex"

STORE = {
    "title": "NaIntegra Lex",
    "short_description": "Lei seca, súmulas, flashcards e questões para concursos públicos.",
    "full_description": """Você se prepara para concurso público — fiscal, tribunais, jurídico, administrativo, MP, Defensoria ou carreiras policiais? O NaIntegra Lex reúne, em um só lugar, tudo o que você precisa para dominar legislação e jurisprudência — com método, clareza, revisão inteligente e material atualizado semanalmente.

Ideal para estudar durante o deslocamento no transporte público — ônibus, metrô, trem ou van.

• Lei seca — leitura artigo por artigo, com progresso e busca por tema
• Jurisprudência — súmulas, temas e julgados dos principais tribunais
• Flashcards — revisão espaçada
• Questões — banco integrado ao NaIntegra Cursos
• Ouvir — narração por voz dos dispositivos legais (ideal no transporte público)
• Anotações e grifos — salvas na sua conta
• Conteúdo atualizado toda semana

Requer assinatura NaIntegra Lex para acesso ao acervo completo.

Desenvolvido por NaIntegra Cursos.""",
    "email": "contato@naintegracursos.com.br",
    "privacy_url": "https://www.naintegracursos.com.br/lex/#/contato",
    "account_deletion_url": "https://www.naintegracursos.com.br/lex/#/excluir-conta",
}


def ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def select_developer_account(page) -> None:
    body = ""
    try:
        body = page.inner_text("body", timeout=5000)
    except Exception:
        pass
    if not re.search(r"conta de desenvolvedor|developer account|Escolha a conta", body, re.I):
        return
    for name in ("Arnold Scott", "NaIntegra", "naintegra"):
        loc = page.get_by_text(re.compile(name, re.I)).first
        if loc.count():
            loc.click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(2500)
            print(f"  conta dev: {name}", flush=True)
            return
    loc = page.locator("[role='listitem'], a, button, div").filter(has_text=re.compile(r"Arnold|NaIntegra", re.I)).first
    if loc.count():
        loc.click()
        page.wait_for_timeout(2500)
        print("  conta dev: match parcial", flush=True)
        return
    loc = page.locator("[role='listitem'], .dev-account, a, button").filter(has_text=re.compile(r".{3,}")).first
    if loc.count():
        loc.click()
        page.wait_for_timeout(2500)
        print("  conta dev: primeira opção", flush=True)


def wait_login(page, timeout_s: int = 600) -> None:
    print("Aguardando login na Play Console (máx. 10 min)...")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        url = page.url
        if "accounts.google.com" in url:
            time.sleep(2)
            continue
        if "play.google.com/console" in url and "/about" not in url:
            select_developer_account(page)
            print("Login OK:", url[:80], flush=True)
            return
        if "play.google.com/console" in url and "/about" in url:
            page.goto(
                "https://play.google.com/console/u/0/developers",
                wait_until="domcontentloaded",
                timeout=120_000,
            )
        time.sleep(2)
    raise TimeoutError("Timeout aguardando login na Play Console")


def open_app_dashboard(page) -> None:
    page.goto("https://play.google.com/console/u/0/developers", wait_until="domcontentloaded", timeout=120_000)
    wait_login(page)
    select_developer_account(page)
    page.wait_for_timeout(2000)

    direct = f"https://play.google.com/console/u/0/developers/-/app/{PACKAGE}/app-dashboard"
    page.goto(direct, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(2500)
    if PACKAGE in page.url and "app-dashboard" in page.url:
        print("App aberto (URL direta):", page.url)
        return

    for term in ("NaIntegra Lex", PACKAGE):
        link = page.locator(f"a[href*='{PACKAGE}'], a:has-text('{term}')").first
        if link.count():
            link.click()
            page.wait_for_load_state("domcontentloaded")
            print("App aberto:", page.url)
            return
        search = page.locator(
            "input[type='search'], input[placeholder*='Pesquis'], input[aria-label*='Search'], input[aria-label*='Pesquisar']"
        ).first
        if search.count() and search.is_visible():
            search.fill(term)
            page.wait_for_timeout(2000)
            link = page.locator(f"a:has-text('{term}'), a[href*='{PACKAGE}']").first
            if link.count():
                link.click()
                page.wait_for_load_state("domcontentloaded")
                print("App aberto (busca):", page.url)
                return

    raise RuntimeError(
        "App 'NaIntegra Lex' não encontrado na Play Console. "
        "Crie o app primeiro (passo 1) com package br.com.naintegracursos.lex"
    )


def fill_if_empty(page, selectors: list[str], value: str) -> None:
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count() == 0:
            continue
        try:
            current = loc.input_value(timeout=3000)
        except Exception:
            try:
                current = loc.inner_text(timeout=3000)
            except Exception:
                current = ""
        if not current.strip():
            loc.fill(value)
            print(f"  preenchido: {sel[:40]}...")
            return


def upload_file(page, selectors: list[str], path: Path) -> bool:
    if not path.exists():
        print(f"  AVISO: arquivo ausente {path}")
        return False
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count():
            loc.set_input_files(str(path))
            print(f"  upload: {path.name}")
            page.wait_for_timeout(2500)
            return True
    # fallback: primeiro input file visível
    loc = page.locator("input[type='file']").first
    if loc.count():
        loc.set_input_files(str(path))
        print(f"  upload (fallback): {path.name}")
        page.wait_for_timeout(2500)
        return True
    return False


def save_page(page) -> None:
    for label in ("Salvar", "Save", "Guardar"):
        btn = page.get_by_role("button", name=re.compile(label, re.I)).first
        if btn.count():
            btn.click()
            page.wait_for_timeout(2000)
            print("  salvo")
            return


def app_base_url(page) -> str:
    m = re.search(r"(https://play\.google\.com/console/u/\d+/developers/-/app/[^/]+)", page.url)
    if m:
        return m.group(1)
    return f"https://play.google.com/console/u/0/developers/-/app/{PACKAGE}"


def step_store_listing(page) -> None:
    print("\n==> Passo 2: Ficha da loja", flush=True)
    base = app_base_url(page)
    page.goto(f"{base}/store-presence/main-store-listing", wait_until="networkidle", timeout=180_000)
    page.wait_for_timeout(3000)

    for sel, val in (
        (["input[aria-label*='Título']", "input[aria-label*='title' i]", "input[name*='title']"], STORE["title"]),
        (
            ["textarea[aria-label*='breve']", "textarea[aria-label*='short' i]", "input[aria-label*='breve']"],
            STORE["short_description"],
        ),
        (
            ["textarea[aria-label*='completa']", "textarea[aria-label*='full' i]", "textarea[name*='description']"],
            STORE["full_description"],
        ),
    ):
        for s in sel:
            loc = page.locator(s).first
            if loc.count():
                loc.click()
                loc.fill(val)
                print(f"  texto: {s[:35]}", flush=True)
                break

    icon = ASSETS / "icon-512-play-store.png"
    feature = ASSETS / "feature-graphic-1024x500.png"
    shots = sorted(ASSETS.glob("screenshot-*.png"))

    for path, label in (
        (icon, "ícone"),
        (feature, "feature"),
        *[(s, s.name) for s in shots[:4]],
    ):
        ok = upload_file(page, ["input[type='file']"], path)
        print(f"  {'ok' if ok else 'falhou'}: {label}", flush=True)

    save_page(page)
    print("Ficha da loja atualizada.", flush=True)


def dump_debug(page, tag: str) -> Path:
    out = MOBILE / "dist" / f"play-debug-{tag}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out), full_page=True)
    text_path = out.with_suffix(".txt")
    try:
        text_path.write_text(page.inner_text("body")[:12000], encoding="utf-8")
    except Exception:
        pass
    print(f"  debug: {out}", flush=True)
    return out


def list_clickable_labels(page, limit: int = 40) -> list[str]:
    labels: list[str] = []
    for sel in ("button", "a[role='button']", "a", "[role='link']"):
        for el in page.locator(sel).all()[:limit]:
            try:
                t = el.inner_text(timeout=500).strip().replace("\n", " ")[:80]
                if t and t not in labels:
                    labels.append(t)
            except Exception:
                continue
    return labels


def click_first(page, patterns: list[str], role: str | None = None) -> bool:
    if role:
        for pat in patterns:
            loc = page.get_by_role(role, name=re.compile(pat, re.I)).first
            if loc.count():
                try:
                    loc.click(timeout=12000)
                    page.wait_for_timeout(1800)
                    return True
                except Exception:
                    pass
    return click_any(page, patterns)


def click_any(page, patterns: list[str], timeout_ms: int = 12000) -> bool:
    for pat in patterns:
        rx = re.compile(pat, re.I)
        for role in ("button", "link", "tab", "menuitem"):
            loc = page.get_by_role(role, name=rx).first
            if loc.count():
                try:
                    loc.scroll_into_view_if_needed(timeout=3000)
                    loc.click(timeout=timeout_ms)
                    page.wait_for_timeout(1800)
                    print(f"  clicou [{role}]: {pat}", flush=True)
                    return True
                except Exception:
                    pass
        for sel in ("button", "a", "material-button", "[role='button']"):
            loc = page.locator(sel).filter(has_text=rx).first
            if loc.count():
                try:
                    loc.scroll_into_view_if_needed(timeout=3000)
                    loc.click(timeout=timeout_ms)
                    page.wait_for_timeout(1800)
                    print(f"  clicou [{sel}]: {pat}", flush=True)
                    return True
                except Exception:
                    pass
        loc = page.get_by_text(rx).first
        if loc.count():
            try:
                loc.scroll_into_view_if_needed(timeout=3000)
                loc.click(timeout=timeout_ms)
                page.wait_for_timeout(1800)
                print(f"  clicou (texto): {pat}", flush=True)
                return True
            except Exception:
                pass
    return False


def step_internal_release(page) -> None:
    print("\n==> Passo 3: Teste interno + AAB", flush=True)
    if not AAB.exists():
        raise FileNotFoundError(f"AAB não encontrado: {AAB}")

    select_developer_account(page)
    base = app_base_url(page)
    track_urls = [
        f"{base}/tracks/internal-testing/releases/create",
        f"{base}/tracks/internal-testing",
        f"{base}/release/tracks/internal-testing",
        f"{base}/testing/tracks/internal-testing",
        f"{base}/release/internal-testing",
        f"{base}/tracks/internal",
    ]
    opened = False
    for u in track_urls:
        try:
            page.goto(u, wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(3000)
            select_developer_account(page)
            if page.locator("body").inner_text(timeout=5000):
                opened = True
                print(f"  trilho: {u}", flush=True)
                break
        except Exception:
            continue
    if not opened:
        page.goto(f"{base}/app-dashboard", wait_until="domcontentloaded")
        select_developer_account(page)
        click_first(page, [r"Teste interno|Internal testing|Internal test"], role="link")

    release_patterns = [
        r"Criar nova versão",
        r"Create new release",
        r"Criar versão",
        r"Create release",
        r"Nova versão",
        r"New release",
        r"Gerenciar faixa",
        r"Manage track",
        r"Editar versão",
        r"Edit release",
        r"Criar nova implantação",
    ]
    if not click_any(page, release_patterns):
        dump_debug(page, "internal-track")
        print("  tentando Internal app sharing...", flush=True)
        page.goto(
            "https://play.google.com/console/u/0/developers/app/internal-app-sharing",
            wait_until="domcontentloaded",
            timeout=120_000,
        )
        page.wait_for_timeout(3000)
        select_developer_account(page)
        click_first(page, [r"Upload|Enviar|Carregar"], role="button")
        if upload_file(page, ["input[type='file']"], AAB):
            page.wait_for_timeout(8000)
            click_first(page, [r"Confirm|Confirmar upload|Confirmar"])
            print("  AAB enviado via Internal app sharing (link na tela).", flush=True)
            return
        dump_debug(page, "internal-sharing")
        raise RuntimeError(
            "Botão de nova versão não encontrado. "
            f"Debug: mobile/dist/play-debug-internal-track.png"
        )

    if not upload_file(page, ["input[type='file'][accept*='aab']", "input[type='file']"], AAB):
        raise RuntimeError("Não foi possível anexar o AAB — faça upload manual na tela aberta.")

    page.wait_for_timeout(5000)
    for label in ("Avançar", "Next", "Review release", "Revisar versão"):
        btn = page.get_by_role("button", name=re.compile(label, re.I)).first
        if btn.count() and btn.is_enabled():
            btn.click()
            page.wait_for_timeout(2000)

    for label in (
        "Iniciar implantação",
        "Start rollout",
        "Implantar",
        "Deploy",
        "Save and publish",
        "Salvar e publicar",
    ):
        btn = page.get_by_role("button", name=re.compile(label, re.I)).first
        if btn.count() and btn.is_enabled():
            btn.click()
            page.wait_for_timeout(3000)
            print("Versão enviada para teste interno.")
            return
    print("Revise a tela e confirme a implantação manualmente se o botão não foi clicado.")


def scrape_play_sha256(page) -> str | None:
    print("\n==> Passo 4: SHA-256 App Signing", flush=True)
    base = app_base_url(page)
    for path in (
        "/app-signing/key-management",
        "/keymanagement",
        "/app-integrity",
        "/setup/app-integrity",
    ):
        try:
            page.goto(base + path, wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(2500)
            text = page.inner_text("body")
            m = re.search(r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){31})", text)
            if m:
                sha = m.group(1).upper()
                print("SHA-256 encontrado:", sha)
                return sha
        except Exception:
            continue
    return None


def apply_sha256(sha: str) -> None:
    subprocess.run(
        ["bash", str(MOBILE / "scripts" / "add-play-sha256.sh"), sha],
        check=True,
        cwd=str(ROOT),
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Automatiza Play Console (ficha + AAB + SHA)")
    parser.add_argument("--upload-only", action="store_true", help="Só envia AAB para teste interno")
    args = parser.parse_args()

    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    ensure_playwright()
    if not ASSETS.exists():
        subprocess.run([sys.executable, str(MOBILE / "scripts" / "generate-store-assets.py")], check=True)
    if not AAB.exists():
        subprocess.run(["bash", str(MOBILE / "scripts" / "build-release-aab.sh")], check=True)

    from playwright.sync_api import sync_playwright

    profile_dir = Path.home() / ".cache" / "naintegra-play-console-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        print(f"Perfil Play Console: {profile_dir}")
        launch_kwargs = {
            "headless": False,
            "viewport": {"width": 1440, "height": 900},
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        chrome_bin = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if chrome_bin.is_file():
            launch_kwargs["channel"] = "chrome"
        else:
            print("Chrome não instalado — usando Chromium do Playwright.")
        context = p.chromium.launch_persistent_context(str(profile_dir), **launch_kwargs)
        page = context.pages[0] if context.pages else context.new_page()

        page.goto(
            "https://play.google.com/console/u/0/developers",
            wait_until="domcontentloaded",
            timeout=120_000,
        )
        wait_login(page)
        open_app_dashboard(page)
        if not args.upload_only:
            step_store_listing(page)
        step_internal_release(page)
        sha = scrape_play_sha256(page)
        if sha:
            apply_sha256(sha)
        else:
            print(
                "SHA-256 do Play App Signing ainda não disponível (comum logo após o 1º upload). "
                "Quando aparecer em Integridade do app, rode:\n"
                f"  bash mobile/scripts/add-play-sha256.sh \"SEU_SHA256\""
            )

        print("\nConcluído. Revise o navegador da Play Console.")
        page.wait_for_timeout(8000)
        context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
