#!/usr/bin/env python3
"""Cadastra testadores do teste fechado e preenche Acesso ao app (Play Console)."""
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
PACKAGE = "br.com.naintegracursos.lex"
DEV_ID = os.environ.get("PLAY_DEV_ACCOUNT_ID", "5476168127224845991")
PROFILE = Path.home() / ".cache" / "naintegra-play-console-profile"

DEFAULT_TESTERS = (
    "infinity.shop288@gmail.com,"
    "contato@naintegracursos.com.br,"
    "teste.naintegra.lex@gmail.com"
)
REVIEWER_EMAIL = os.environ.get("PLAY_REVIEWER_EMAIL", "teste.naintegra.lex@gmail.com")
REVIEWER_PASSWORD = os.environ.get("PLAY_REVIEWER_PASSWORD", "NaIntegraLex2026!")


def ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def tester_emails() -> list[str]:
    raw = os.environ.get("PLAY_TESTER_EMAILS", DEFAULT_TESTERS)
    return [e.strip() for e in re.split(r"[\s,;]+", raw) if e.strip() and "@" in e]


def body(page) -> str:
    try:
        return page.inner_text("body", timeout=8000)
    except Exception:
        return ""


def base() -> str:
    return f"https://play.google.com/console/u/0/developers/{DEV_ID}/app/{PACKAGE}"


def click(page, *patterns: str) -> bool:
    for pat in patterns:
        rx = re.compile(pat, re.I)
        for role in ("button", "link", "tab", "menuitem", None):
            try:
                loc = (
                    page.get_by_role(role, name=rx).first
                    if role
                    else page.get_by_text(rx).first
                )
                if loc.count():
                    loc.click(timeout=8000)
                    page.wait_for_timeout(1500)
                    return True
            except Exception:
                pass
    return False


def fill_first(page, selectors: list[str], value: str) -> bool:
    for sel in selectors:
        loc = page.locator(sel).first
        if not loc.count():
            continue
        try:
            loc.fill(value, timeout=5000)
            return True
        except Exception:
            pass
    return False


def save(page) -> None:
    for pat in (r"Salvar", r"Save", r"Aplicar", r"Apply", r"Confirmar", r"Confirm"):
        if click(page, pat):
            return


def wait_login(page) -> None:
    print("[login] Play Console…", flush=True)
    for _ in range(300):
        if "accounts.google.com" in page.url:
            time.sleep(2)
            continue
        if "play.google.com/console" in page.url:
            if not re.search(r"Escolha a conta|Choose the developer", body(page), re.I):
                print("  OK", flush=True)
                return
            click(page, r"Arnold Scott")
        time.sleep(2)
    raise TimeoutError("login")


def goto(page, *paths: str) -> None:
    for path in paths:
        try:
            page.goto(f"{base()}{path}", wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(2500)
            if PACKAGE in page.url:
                return
        except Exception:
            continue


def configure_testers(page, emails: list[str]) -> None:
    print("\n==> Testadores (teste fechado)", flush=True)
    goto(page, "/tracks/closed-testing/testers")
    click(page, r"Criar lista", r"Create list", r"Testadores", r"Testers", r"Gerenciar")
    fill_first(page, ["input[type='text']"], "NaIntegra Lex testers")
    fill_first(page, ["textarea"], "\n".join(emails))
    if not fill_first(page, ["textarea"], "\n".join(emails)):
        fill_first(page, ["input[type='email']"], emails[0])
    save(page)
    print(f"  e-mails: {', '.join(emails)}", flush=True)


def configure_app_access(page) -> None:
    print("\n==> Acesso ao app (revisor)", flush=True)
    goto(
        page,
        "/app-content/testing-credentials",
        "/app-content/app-access",
        "/policy/app-content",
    )
    click(page, r"Gerenciar", r"Manage", r"Acesso ao app", r"App access")
    click(
        page,
        r"Todas as funcionalidades|All functionality",
        r"Parte ou todas|Some or all",
        r"restrit|restricted|login",
    )
    instructions = (
        "O app exige login para acessar o acervo completo (leis, jurisprudência, flashcards e questões).\n\n"
        f"E-mail: {REVIEWER_EMAIL}\n"
        f"Senha: {REVIEWER_PASSWORD}\n\n"
        "Conta de teste com assinatura Lex ativa até 2027. "
        "Após entrar, todo o conteúdo fica disponível. "
        "Sem login, apenas telas públicas (preços e contato)."
    )
    fill_first(page, ["textarea"], instructions)
    fill_first(page, ["input[type='email']", "input[type='text']"], REVIEWER_EMAIL)
    save(page)
    print(f"  revisor: {REVIEWER_EMAIL}", flush=True)


def main() -> int:
    ensure_playwright()
    from playwright.sync_api import sync_playwright

    emails = tester_emails()
    PROFILE.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        kwargs = {
            "headless": False,
            "viewport": {"width": 1440, "height": 900},
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if chrome.is_file():
            kwargs["channel"] = "chrome"
        ctx = p.chromium.launch_persistent_context(str(PROFILE), **kwargs)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://play.google.com/console/u/0/developers", wait_until="domcontentloaded")
        wait_login(page)
        page.goto(f"{base()}/app-dashboard", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        configure_testers(page, emails)
        configure_app_access(page)

        DIST.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(DIST / "play-test-access-config.png"), full_page=True)
        (DIST / "play-test-access-config.txt").write_text(body(page)[:12000], encoding="utf-8")
        print(f"\nScreenshot: {DIST / 'play-test-access-config.png'}", flush=True)
        page.wait_for_timeout(5000)
        ctx.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
