#!/usr/bin/env python3
"""Configura teste fechado na Play Console: países (BR) + lista de testadores."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOBILE = ROOT / "mobile"
PACKAGE = "br.com.naintegracursos.lex"
DEFAULT_TESTERS = [
    "infinity.shop288@gmail.com",
    "contato@naintegracursos.com.br",
    "teste.naintegra.lex@gmail.com",
]


def ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def tester_emails() -> list[str]:
    raw = os.environ.get("PLAY_TESTER_EMAILS", "")
    if raw.strip():
        return [e.strip() for e in re.split(r"[\s,;]+", raw) if e.strip() and "@" in e]
    return list(DEFAULT_TESTERS)


def select_developer_account(page) -> None:
    try:
        body = page.inner_text("body", timeout=5000)
    except Exception:
        return
    if not re.search(r"conta de desenvolvedor|developer account|Escolha a conta", body, re.I):
        return
    for name in ("Arnold Scott", "NaIntegra", "naintegra"):
        loc = page.get_by_text(re.compile(name, re.I)).first
        if loc.count():
            loc.click()
            page.wait_for_timeout(2500)
            print(f"  conta dev: {name}", flush=True)
            return


def wait_login(page, timeout_s: int = 600) -> None:
    print("Aguardando login na Play Console...", flush=True)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        url = page.url
        if "accounts.google.com" in url:
            time.sleep(2)
            continue
        if "play.google.com/console" in url and "/about" not in url:
            select_developer_account(page)
            print("Login OK", flush=True)
            return
        time.sleep(2)
    raise TimeoutError("Timeout aguardando login")


def click_any(page, patterns: list[str]) -> bool:
    for pat in patterns:
        rx = re.compile(pat, re.I)
        loc = page.get_by_text(rx).first
        if loc.count():
            try:
                loc.click(timeout=8000)
                page.wait_for_timeout(1500)
                print(f"  clicou texto: {pat}", flush=True)
                return True
            except Exception:
                pass
        for role in ("button", "link", "tab", "menuitem"):
            try:
                loc = page.get_by_role(role, name=rx).first
                if loc.count():
                    loc.click(timeout=8000)
                    page.wait_for_timeout(1500)
                    print(f"  clicou [{role}]: {pat}", flush=True)
                    return True
            except Exception:
                pass
        loc = page.locator("button, a, [role='button'], [role='tab']").filter(has_text=rx).first
        if loc.count():
            try:
                loc.click(timeout=8000)
                page.wait_for_timeout(1500)
                print(f"  clicou filtro: {pat}", flush=True)
                return True
            except Exception:
                pass
    return False


def save_page(page) -> None:
    for label in ("Salvar", "Save", "Guardar", "Aplicar", "Apply"):
        btn = page.get_by_role("button", name=re.compile(label, re.I)).first
        if btn.count():
            try:
                btn.click(timeout=5000)
                page.wait_for_timeout(2000)
                print("  salvo", flush=True)
                return
            except Exception:
                pass


def app_base(page) -> str:
    m = re.search(r"(https://play\.google\.com/console/u/\d+/developers/-/app/[^/]+)", page.url)
    if m:
        return m.group(1)
    return f"https://play.google.com/console/u/0/developers/-/app/{PACKAGE}"


def open_closed_track(page) -> None:
    base = app_base(page)
    urls = [
        f"{base}/tracks/closed-testing",
        f"{base}/release/tracks/closed-testing",
        f"{base}/testing/tracks/closed-testing",
        f"{base}/tracks/alpha",
    ]
    for u in urls:
        try:
            page.goto(u, wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(3000)
            select_developer_account(page)
            if "closed" in page.url.lower() or "alpha" in page.url.lower() or "teste" in page.inner_text("body").lower():
                print(f"  faixa: {u}", flush=True)
                return
        except Exception:
            continue
    page.goto(f"{base}/app-dashboard", wait_until="domcontentloaded")
    click_any(page, [r"Teste fechado|Closed testing|Closed test"])


def configure_countries(page) -> None:
    print("\n==> Países e regiões (Brasil)", flush=True)
    click_any(page, [
        r"Países e regiões",
        r"Countries and regions",
        r"Países",
        r"Countries",
        r"Disponibilidade",
        r"Gerenciar países",
        r"Manage countries",
    ])

    # Selecionar Brasil na lista ou busca
    search = page.locator(
        "input[type='search'], input[placeholder*='Pesquis'], input[aria-label*='Search'], input[aria-label*='Pesquis']"
    ).first
    if search.count():
        search.fill("Brasil")
        page.wait_for_timeout(1200)

    for label in (r"^Brasil$", r"^Brazil$", r"Brasil \(BR\)"):
        loc = page.get_by_text(re.compile(label, re.I)).first
        if loc.count():
            try:
                row = loc.locator("xpath=ancestor::*[.//input[@type='checkbox']][1]")
                if row.count():
                    cb = row.locator("input[type='checkbox']").first
                    if cb.count() and not cb.is_checked():
                        cb.check(force=True)
                    else:
                        loc.click()
                else:
                    loc.click()
                page.wait_for_timeout(800)
                print("  Brasil selecionado", flush=True)
                break
            except Exception:
                pass

    click_any(page, [r"Adicionar países", r"Add countries", r"Selecionar países", r"Select countries"])
    click_any(page, [r"^Brasil$", r"^Brazil$"])
    save_page(page)


def configure_testers(page, emails: list[str]) -> None:
    print("\n==> Testadores", flush=True)
    click_any(page, [
        r"Testadores",
        r"Testers",
        r"Lista de testadores",
        r"Manage testers",
    ])

    click_any(page, [
        r"Criar lista",
        r"Create list",
        r"Nova lista",
        r"New list",
        r"Adicionar testadores",
        r"Add testers",
    ])

    name = "NaIntegra Lex testers"
    for sel in ("input[aria-label*='nome' i]", "input[aria-label*='name' i]", "input[type='text']"):
        loc = page.locator(sel).first
        if loc.count():
            try:
                val = loc.input_value(timeout=2000)
                if not val.strip():
                    loc.fill(name)
                    print(f"  lista: {name}", flush=True)
                break
            except Exception:
                pass

    emails_box = page.locator(
        "textarea, input[aria-label*='e-mail' i], input[aria-label*='email' i]"
    ).first
    payload = "\n".join(emails)
    if emails_box.count():
        emails_box.fill(payload)
        print(f"  e-mails: {', '.join(emails)}", flush=True)
    else:
        for email in emails:
            add = page.locator("input[type='email'], textarea").first
            if add.count():
                add.fill(email)
                click_any(page, [r"Adicionar|Add|Invite|Convidar"])
                page.wait_for_timeout(800)

    save_page(page)
    click_any(page, [r"Salvar alterações|Save changes|Confirmar|Confirm"])


def main() -> int:
    ensure_playwright()
    from playwright.sync_api import sync_playwright

    emails = tester_emails()
    profile = Path.home() / ".cache" / "naintegra-play-console-profile"
    profile.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        kwargs = {
            "headless": False,
            "viewport": {"width": 1440, "height": 900},
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        chrome = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        if chrome.is_file():
            kwargs["channel"] = "chrome"
        ctx = p.chromium.launch_persistent_context(str(profile), **kwargs)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        page.goto("https://play.google.com/console/u/0/developers", wait_until="domcontentloaded", timeout=120_000)
        wait_login(page)
        dash = f"https://play.google.com/console/u/0/developers/-/app/{PACKAGE}/app-dashboard"
        page.goto(dash, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(2000)
        select_developer_account(page)

        open_closed_track(page)
        configure_countries(page)
        configure_testers(page, emails)

        out = MOBILE / "dist" / "play-closed-track-config.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out), full_page=True)
        print(f"\nScreenshot: {out}", flush=True)
        print(
            "\nPróximo passo na Play Console:\n"
            "  Teste fechado → revisar versão 2 → Iniciar implantação\n"
            "  (O aviso de desofuscação/ProGuard pode ser ignorado — o app não usa R8.)",
            flush=True,
        )
        page.wait_for_timeout(6000)
        ctx.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
