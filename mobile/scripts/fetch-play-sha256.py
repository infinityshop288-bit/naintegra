#!/usr/bin/env python3
"""Obtém SHA-256 do certificado App Signing no Play Console e atualiza assetlinks."""
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
DEV_ID = os.environ.get("PLAY_DEV_ACCOUNT_ID", "5476168127224845991")
PROFILE = Path.home() / ".cache" / "naintegra-play-console-profile"


def ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def body(page) -> str:
    try:
        return page.inner_text("body", timeout=8000)
    except Exception:
        return ""


def base() -> str:
    return f"https://play.google.com/console/u/0/developers/{DEV_ID}/app/{PACKAGE}"


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
            loc = page.get_by_text("Arnold Scott").first
            if loc.count():
                loc.click(timeout=5000)
                page.wait_for_timeout(2500)
        time.sleep(2)
    raise TimeoutError("login")


def goto_app(page) -> None:
    page.goto(base() + "/app-dashboard", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(3000)
    if PACKAGE not in page.url or "app-list" in page.url:
        for pat in (r"Ver app", r"NaIntegra LEX", r"NaIntegra Lex"):
            loc = page.get_by_text(re.compile(pat, re.I)).first
            if loc.count():
                loc.click(timeout=5000)
                page.wait_for_timeout(3000)
                break


def find_sha(text: str) -> str | None:
    # Prefer label near "App signing" / "assinatura do app"
    for block in re.split(r"\n{2,}", text):
        if re.search(r"app signing|assinatura do app|certificado de assinatura", block, re.I):
            m = re.search(r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){31})", block)
            if m:
                return m.group(1).upper()
    matches = re.findall(r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){31})", text)
    # Play often shows upload + app signing; app signing is typically second on key mgmt page
    return matches[-1].upper() if matches else None


def scrape_sha(page) -> str | None:
    goto_app(page)
    for path in (
        "/keymanagement",
        "/app-signing/key-management",
        "/app-integrity",
    ):
        url = base() + path
        print(f"  {url}", flush=True)
        try:
            page.goto(url, wait_until="networkidle", timeout=120_000)
            for _ in range(30):
                page.wait_for_timeout(2000)
                html = page.content()
                text = body(page)
                if "Carregando" in text and len(text) < 800:
                    continue
                sha = find_sha(text) or find_sha(html)
                if not sha:
                    sha = page.evaluate(
                        """() => {
                          const t = document.body?.innerText || '';
                          const m = t.match(/([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){31})/g);
                          return m ? m[m.length - 1].toUpperCase() : null;
                        }"""
                    )
                if sha:
                    print(f"  SHA-256: {sha}", flush=True)
                    out = MOBILE / "dist" / "play-app-signing-sha256.txt"
                    out.write_text(sha + "\n", encoding="utf-8")
                    page.screenshot(path=str(MOBILE / "dist" / "play-app-signing-sha256.png"), full_page=True)
                    return sha
        except Exception as exc:
            print(f"  erro: {exc}", flush=True)
    return None


def main() -> int:
    ensure_playwright()
    from playwright.sync_api import sync_playwright

    PROFILE.mkdir(parents=True, exist_ok=True)
    sha: str | None = None

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE),
            headless=False,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://play.google.com/console/u/0/developers", wait_until="domcontentloaded")
        wait_login(page)
        sha = scrape_sha(page)
        page.wait_for_timeout(3000)
        ctx.close()

    if not sha:
        print(
            "\nNão foi possível ler o SHA automaticamente.\n"
            "Copie manualmente em:\n"
            f"  {base()}/keymanagement\n"
            "  → Certificado de assinatura do app → SHA-256\n\n"
            f"  bash mobile/scripts/add-play-sha256.sh \"AA:BB:...\"",
            file=sys.stderr,
        )
        return 1

    subprocess.run(
        ["bash", str(MOBILE / "scripts" / "add-play-sha256.sh"), sha],
        check=True,
        cwd=str(ROOT),
    )
    print("\n[OK] assetlinks atualizado com SHA App Signing.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
