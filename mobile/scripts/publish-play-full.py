#!/usr/bin/env python3
"""Loop Play Console: países BR, testadores, upload AAB teste fechado, implantar."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOBILE = ROOT / "mobile"
AAB = MOBILE / "dist" / "naintegra-lex-release.aab"
PACKAGE = "br.com.naintegracursos.lex"
DEV_ACCOUNT_ID = os.environ.get("PLAY_DEV_ACCOUNT_ID", "5476168127224845991")
PROFILE = Path.home() / ".cache" / "naintegra-play-console-profile"
TESTERS = [
    e.strip()
    for e in os.environ.get(
        "PLAY_TESTER_EMAILS",
        "infinity.shop288@gmail.com,contato@naintegracursos.com.br,teste.naintegra.lex@gmail.com",
    ).split(",")
    if e.strip() and "@" in e
]


def ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


def body_text(page) -> str:
    try:
        return page.inner_text("body", timeout=8000)
    except Exception:
        return ""


def ensure_dev_account(page) -> None:
    for _ in range(8):
        text = body_text(page)
        if not re.search(r"Escolha a conta|Choose the developer account", text, re.I):
            return
        for sel in (
            page.get_by_text("Arnold Scott", exact=False),
            page.locator("[role='listitem']").filter(has_text=re.compile(r"Arnold", re.I)),
            page.locator("a, button, div").filter(has_text=re.compile(r"^Arnold Scott$", re.I)),
        ):
            try:
                if sel.count():
                    sel.first.click(timeout=5000)
                    page.wait_for_timeout(3000)
                    print("  conta: Arnold Scott", flush=True)
                    break
            except Exception:
                continue
        page.wait_for_timeout(1500)


def wait_login(page, timeout_s: int = 600) -> None:
    print("Login Play Console...", flush=True)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if "accounts.google.com" in page.url:
            time.sleep(2)
            continue
        if "play.google.com/console" in page.url:
            ensure_dev_account(page)
            if not re.search(r"Escolha a conta|Choose the developer", body_text(page), re.I):
                print("  login OK", flush=True)
                return
        time.sleep(2)
    raise TimeoutError("Login Play Console")


def click_text(page, *patterns: str) -> bool:
    for pat in patterns:
        rx = re.compile(pat, re.I)
        loc = page.get_by_text(rx).first
        try:
            if loc.count():
                loc.click(timeout=8000)
                page.wait_for_timeout(1500)
                print(f"  click: {pat}", flush=True)
                return True
        except Exception:
            pass
        loc = page.locator("button, a, [role='button'], [role='tab']").filter(has_text=rx).first
        try:
            if loc.count():
                loc.click(timeout=8000)
                page.wait_for_timeout(1500)
                print(f"  click btn: {pat}", flush=True)
                return True
        except Exception:
            pass
    return False


def save(page) -> None:
    click_text(page, r"^Salvar$", r"^Save$", r"Salvar alterações", r"Save changes", r"^Aplicar$")


def app_base(page) -> str:
    return f"https://play.google.com/console/u/0/developers/{DEV_ACCOUNT_ID}/app/{PACKAGE}"


def goto_app(page) -> None:
    url = f"{app_base(page)}/app-dashboard"
    page.goto(url, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(3000)
    ensure_dev_account(page)
    if PACKAGE not in page.url or "app-list" in page.url:
        for pat in (r"Ver app", r"View app", r"NaIntegra LEX", r"NaIntegra Lex"):
            if click_text(page, pat):
                page.wait_for_timeout(3000)
                break
    print(f"  app URL: {page.url[:100]}", flush=True)


def ensure_app(page) -> bool:
    if PACKAGE in page.url and "app-list" not in page.url:
        return True
    goto_app(page)
    return PACKAGE in page.url and "app-list" not in page.url


def goto_track(page, path: str) -> None:
    if not ensure_app(page):
        raise RuntimeError("fora do app NaIntegra Lex")
    page.goto(f"{app_base(page)}{path}", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(3500)
    ensure_dev_account(page)
    if "app-list" in page.url or PACKAGE not in page.url:
        goto_app(page)
        page.goto(f"{app_base(page)}{path}", wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(3500)


def configure_countries(page) -> bool:
    print("\n[1/4] Países — Brasil", flush=True)
    for path in (
        "/tracks/closed-testing/countries",
        "/tracks/closed-testing/country-targeting",
        "/tracks/closed-testing",
    ):
        goto_track(page, path)
        click_text(page, r"Países e regiões", r"Countries and regions", r"Países", r"Countries")
        search = page.locator("input[type='search'], input[placeholder*='Pesquis' i]").first
        if search.count():
            search.fill("Brasil")
            page.wait_for_timeout(1000)
        # checkbox Brasil
        for label in ("Brasil", "Brazil"):
            name_loc = page.locator(f'[debug-id="country-name"]:has-text("{label}")').first
            if not name_loc.count():
                name_loc = page.get_by_text(label, exact=True).first
            if not name_loc.count():
                continue
            try:
                name_loc.scroll_into_view_if_needed(timeout=5000)
                row = name_loc.locator("xpath=ancestor::*[@role='row' or @role='checkbox' or contains(@class,'country')][1]")
                cb = row.locator("input[type='checkbox']").first
                if not cb.count():
                    cb = page.locator("input[type='checkbox']").filter(
                        has=page.locator(f'[debug-id="country-name"]:has-text("{label}")')
                    ).first
                if cb.count():
                    cb.check(force=True)
                else:
                    name_loc.click(force=True)
                print("  BR marcado", flush=True)
                save(page)
                return True
            except Exception as exc:
                print(f"  tentativa {label}: {exc}", flush=True)
                try:
                    page.evaluate(
                        """(label) => {
                          const nodes = [...document.querySelectorAll('[debug-id="country-name"]')];
                          const el = nodes.find(n => n.textContent.trim() === label);
                          if (!el) return false;
                          el.scrollIntoView({block:'center'});
                          const row = el.closest('[role="row"]') || el.parentElement?.parentElement;
                          const cb = row?.querySelector('input[type="checkbox"]');
                          if (cb) { cb.click(); return true; }
                          el.click();
                          return true;
                        }""",
                        label,
                    )
                    print("  BR via JS", flush=True)
                    save(page)
                    return True
                except Exception:
                    pass
        click_text(page, r"Adicionar países", r"Add countries", r"Selecionar todos", r"Select all")
        save(page)
    return False


def configure_testers(page) -> bool:
    print("\n[2/4] Testadores", flush=True)
    goto_track(page, "/tracks/closed-testing/testers")
    if not click_text(page, r"Testadores", r"Testers"):
        goto_track(page, "/tracks/closed-testing")
        click_text(page, r"Testadores", r"Testers")
    click_text(page, r"Criar lista", r"Create list", r"Nova lista", r"Create email list", r"Adicionar testadores")
    name_in = page.locator("input[type='text']").first
    if name_in.count():
        try:
            if not name_in.input_value().strip():
                name_in.fill("NaIntegra Lex testers")
        except Exception:
            name_in.fill("NaIntegra Lex testers")
    area = page.locator("textarea").first
    if area.count():
        area.fill("\n".join(TESTERS))
        print(f"  testers: {TESTERS}", flush=True)
    save(page)
    click_text(page, r"Criar", r"Create", r"Salvar lista", r"Save list")
    return True


def upload_and_rollout(page) -> bool:
    print("\n[3/4] Upload AAB + implantar", flush=True)
    if not AAB.exists():
        subprocess.run(["bash", str(MOBILE / "scripts/build-release-aab.sh")], check=True)

    for path in ("/tracks/closed-testing/releases", "/tracks/closed-testing"):
        goto_track(page, path)
        if click_text(page, r"Editar versão", r"Edit release", r"Revisar versão", r"Review release"):
            if finalize_rollout(page):
                return True

    goto_track(page, "/tracks/closed-testing/releases/create")
    click_text(page, r"Criar nova versão", r"Create new release", r"Nova versão")
    inp = page.locator("input[type='file']").first
    if inp.count():
        inp.set_input_files(str(AAB))
        print(f"  AAB: {AAB.name}", flush=True)
        page.wait_for_timeout(12000)
    if not ensure_app(page):
        goto_track(page, "/tracks/closed-testing/releases")
    return finalize_rollout(page)


def finalize_rollout(page) -> bool:
    click_text(page, r"Avançar", r"Next", r"Revisar versão", r"Review release")
    page.wait_for_timeout(3000)
    text = body_text(page)
    debug = MOBILE / "dist" / "play-rollout-debug.txt"
    if re.search(r"nenhum país|no country", text, re.I):
        print("  ERRO: adicionar Brasil em Países e regiões", flush=True)
    if re.search(r"testadores|testers", text, re.I) and re.search(
        r"não especificou|not specified|nenhum testador|no testers", text, re.I
    ):
        print("  AVISO: configurar lista de testadores", flush=True)
    for attempt in range(6):
        if click_text(
            page,
            r"Iniciar implantação para teste fechado",
            r"Iniciar implantação",
            r"Start rollout to closed testing",
            r"Start rollout",
            r"Implantar",
            r"Deploy",
            r"Salvar e publicar",
            r"Save and publish",
            r"Enviar para revisão",
            r"Send for review",
            r"^Confirmar$",
            r"^Confirm$",
        ):
            page.wait_for_timeout(5000)
            click_text(page, r"^Confirmar$", r"^Confirm$", r"Enviar", r"Send")
            page.wait_for_timeout(3000)
            text = body_text(page)
            if re.search(r"implantação iniciada|rollout|publicad|enviad|em análise|under review", text, re.I):
                print("  implantação OK", flush=True)
                return True
        page.wait_for_timeout(2000)
    debug.write_text(text[:12000], encoding="utf-8")
    shot = MOBILE / "dist" / "play-rollout-debug.png"
    page.screenshot(path=str(shot), full_page=True)
    print(f"  debug rollout: {shot}", flush=True)
    return False


def scrape_sha(page) -> str | None:
    print("\n[4/4] SHA App Signing", flush=True)
    base = app_base(page)
    for path in ("/app-signing/key-management", "/keymanagement", "/app-integrity"):
        page.goto(base + path, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(2500)
        m = re.search(r"([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){31})", body_text(page))
        if m:
            return m.group(1).upper()
    return None


def main() -> int:
    ensure_playwright()
    from playwright.sync_api import sync_playwright

    PROFILE.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE),
            headless=False,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://play.google.com/console/u/0/developers", wait_until="domcontentloaded", timeout=120_000)
        wait_login(page)
        goto_app(page)

        try:
            if not configure_countries(page):
                errors.append("países")
        except Exception as exc:
            print(f"  países erro: {exc}", flush=True)
            errors.append("países")
        try:
            if not configure_testers(page):
                errors.append("testadores")
        except Exception as exc:
            print(f"  testadores erro: {exc}", flush=True)
            errors.append("testadores")
        try:
            if not upload_and_rollout(page):
                errors.append("upload/implantação")
        except Exception as exc:
            print(f"  upload erro: {exc}", flush=True)
            errors.append("upload/implantação")

        sha = scrape_sha(page)
        if sha:
            subprocess.run(["bash", str(MOBILE / "scripts/add-play-sha256.sh"), sha], cwd=str(ROOT))
            print(f"  assetlinks: {sha}", flush=True)

        shot = MOBILE / "dist" / "play-publish-final.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"\nScreenshot: {shot}", flush=True)
        page.wait_for_timeout(5000)
        ctx.close()

    if errors:
        print("Pendências:", ", ".join(errors), file=sys.stderr)
        return 1
    print("Play teste fechado OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
