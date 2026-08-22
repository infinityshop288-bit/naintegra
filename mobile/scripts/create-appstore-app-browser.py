#!/usr/bin/env python3
"""Cria app no App Store Connect via navegador (login Apple necessário)."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

BUNDLE_ID = "br.com.naintegracursos.lex"
APP_NAME = "NaIntegra Lex"
SKU = "naintegra-lex"
APPLE_ID = "infinity.shop288@gmail.com"


def ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def wait_logged_in(page, timeout_s: int = 180) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        url = page.url.lower()
        if "login" in url or "idmsa.apple.com" in url:
            if page.locator('input[type="text"], input[type="email"]').count():
                page.locator('input[type="text"], input[type="email"]').first.fill(APPLE_ID)
                for label in ("Continuar", "Continue"):
                    btn = page.get_by_role("button", name=label)
                    if btn.count():
                        btn.first.click()
                        break
            page.wait_for_timeout(2500)
            continue
        body = page.inner_text("body", timeout=5000)
        if any(x in body for x in ("Apps", "Meus apps", "App Store Connect")) and "E-mail ou número" not in body:
            return True
        page.wait_for_timeout(2000)
    return False


def main() -> None:
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

        print("Aguardando login no App Store Connect (até 3 min)…")
        if not wait_logged_in(page):
            print("[BLOQUEIO] Faça login em infinity.shop288@gmail.com no navegador aberto.")
            page.wait_for_timeout(120_000)

        body = page.inner_text("body", timeout=10000)
        if APP_NAME in body:
            print(f"[OK] App '{APP_NAME}' já existe.")
            ctx.close()
            return

        # Abrir diálogo Novo app
        opened = False
        for name in ("Adicionar apps", "Add Apps", "Novo app", "New App"):
            btn = page.get_by_role("button", name=name)
            if btn.count():
                btn.first.click()
                opened = True
                break
            link = page.get_by_role("menuitem", name=name)
            if link.count():
                link.first.click()
                opened = True
                break
        if not opened:
            page.locator("button").filter(has_text="+").first.click(timeout=5000)
            page.get_by_role("menuitem", name="Novo app").or_(page.get_by_role("menuitem", name="New App")).first.click(timeout=5000)

        page.wait_for_timeout(2000)
        dialog = page.locator('[role="dialog"], .modal, #newAppModal').first
        dialog.wait_for(state="visible", timeout=30_000)

        # iOS
        for sel in ('input[value="IOS"]', 'label:has-text("iOS")'):
            box = dialog.locator(sel)
            if box.count():
                box.first.click(force=True)
                break

        text_inputs = dialog.locator('input[type="text"]:visible')
        if text_inputs.count() >= 1:
            text_inputs.nth(0).fill(APP_NAME)
        if text_inputs.count() >= 2:
            text_inputs.nth(1).fill(SKU)

        for label in ("Idioma principal", "Primary Language"):
            sel = dialog.get_by_label(label, exact=False)
            if sel.count():
                for opt in ("Português (Brasil)", "Portuguese (Brazil)"):
                    try:
                        sel.select_option(label=opt)
                        break
                    except Exception:
                        pass
                break

        for label in ("ID do pacote", "Bundle ID", "Pacote"):
            sel = dialog.get_by_label(label, exact=False)
            if sel.count():
                for opt in (BUNDLE_ID, APP_NAME):
                    try:
                        sel.select_option(label=opt)
                        break
                    except Exception:
                        try:
                            sel.select_option(value=opt)
                        except Exception:
                            pass
                break

        for label in ("Acesso de usuário", "User Access"):
            sel = dialog.get_by_label(label, exact=False)
            if sel.count():
                for opt in ("Acesso total", "Full Access"):
                    try:
                        sel.select_option(label=opt)
                        break
                    except Exception:
                        pass
                break

        for name in ("Criar", "Create"):
            btn = dialog.get_by_role("button", name=name)
            if btn.count():
                btn.first.click()
                break

        page.wait_for_timeout(8000)
        if APP_NAME in page.inner_text("body", timeout=10000):
            print(f"[OK] App '{APP_NAME}' criado no App Store Connect.")
        else:
            print("[AVISO] Confirme manualmente se o app foi criado.")
        ctx.close()


if __name__ == "__main__":
    main()
