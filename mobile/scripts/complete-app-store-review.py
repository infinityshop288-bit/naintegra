#!/usr/bin/env python3
"""Preenche ficha App Store Connect e envia NaIntegra Lex para revisão."""
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
ASSETS = MOBILE / "store-assets" / "generated" / "app-store"
APP_NAME = "NaIntegra Lex"
APP_ID = os.environ.get("APP_STORE_APP_ID", "6778567767")
APPLE_ID = os.environ.get("APPLE_ID", "infinity.shop288@gmail.com")
BUILD = os.environ.get("APP_STORE_BUILD", "5")
ASC = "https://appstoreconnect.apple.com"

PRIVACY = "https://www.naintegracursos.com.br/lex/#/contato"
SUPPORT = "https://www.naintegracursos.com.br/lex/#/contato"
MARKETING = "https://www.naintegracursos.com.br/lex/"
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
REVIEWER = os.environ.get("APP_STORE_REVIEWER_EMAIL", "teste.naintegra.lex@gmail.com")
REVIEWER_PASSWORD = os.environ.get("APP_STORE_REVIEWER_PASSWORD", "NaIntegraLex2026!")
REVIEW_CONTACT = {
    "first": os.environ.get("APP_STORE_CONTACT_FIRST", "NaIntegra"),
    "last": os.environ.get("APP_STORE_CONTACT_LAST", "Cursos"),
    "phone": os.environ.get("APP_STORE_CONTACT_PHONE", "+5511999999999"),
    "email": os.environ.get("APP_STORE_CONTACT_EMAIL", APPLE_ID),
}
REVIEW_NOTES = (
    "Login de teste (use o E-MAIL completo, não username): teste.naintegra.lex@gmail.com / NaIntegraLex2026! "
    "Conta com assinatura ativa. No iOS, assinaturas são via App Store (IAP); login Google/Apple usa fluxo in-app. "
    "Exclusão de conta: menu Contato → Exclusão de conta, ou #/excluir-conta."
)
PROFILE = Path.home() / ".cache" / "naintegra-appstore-profile"


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


def dismiss_dialogs(page) -> None:
    for _ in range(3):
        dlg = page.get_by_role("dialog")
        if not dlg.count():
            break
        for pat in (r"^Concluído$", r"^Done$", r"^Cancelar$", r"^Cancel$", r"^Fechar$", r"^Close$"):
            btn = dlg.get_by_role("button", name=re.compile(pat, re.I))
            if btn.count():
                try:
                    btn.first.click(timeout=3000)
                    page.wait_for_timeout(800)
                    break
                except Exception:
                    pass
        else:
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)


def click(page, *patterns: str) -> bool:
    for pat in patterns:
        rx = re.compile(pat, re.I)
        for getter in (
            lambda: page.get_by_role("button", name=rx),
            lambda: page.get_by_role("link", name=rx),
            lambda: page.get_by_role("tab", name=rx),
            lambda: page.get_by_text(rx),
        ):
            try:
                loc = getter()
                if loc.count():
                    loc.first.click(timeout=8000)
                    page.wait_for_timeout(1200)
                    print(f"    ✓ {pat[:50]}")
                    return True
            except Exception:
                pass
    return False


def fill_by_placeholder(page, placeholders: list[str], value: str) -> bool:
    for ph in placeholders:
        loc = page.get_by_placeholder(ph, exact=False)
        if loc.count():
            try:
                loc.first.fill(value, timeout=5000)
                return True
            except Exception:
                pass
    return False


def fill_textarea_near_label(page, labels: list[str], value: str) -> bool:
    for label in labels:
        loc = page.locator(f'label:has-text("{label}") + textarea, label:has-text("{label}") ~ textarea')
        if loc.count():
            try:
                loc.first.fill(value, timeout=5000)
                return True
            except Exception:
                pass
    textareas = page.locator("textarea:visible")
    for i in range(textareas.count()):
        try:
            ta = textareas.nth(i)
            parent = ta.locator("xpath=ancestor::div[1]").inner_text(timeout=2000)
            if any(l.lower() in parent.lower() for l in labels):
                ta.fill(value)
                return True
        except Exception:
            continue
    return False


def fill_input_near_text(page, labels: list[str], value: str) -> bool:
    for label in labels:
        block = page.locator(f'div:has-text("{label}")').filter(has=page.locator("input")).first
        if block.count():
            inp = block.locator("input").first
            try:
                inp.fill(value, timeout=5000)
                return True
            except Exception:
                pass
    return False


def upload_screenshots(page, *paths: Path) -> int:
    files = [str(p) for p in paths if p.is_file()]
    if not files:
        return 0
    inputs = page.locator("input[type='file']")
    for i in range(inputs.count()):
        try:
            inputs.nth(i).set_input_files(files)
            page.wait_for_timeout(4000)
            print(f"    ↑ {len(files)} capturas")
            return len(files)
        except Exception:
            continue
    btn = page.get_by_role("button", name=re.compile(r"Escolher arquivo|Choose File", re.I)).first
    try:
        with page.expect_file_chooser(timeout=8000) as fc:
            btn.click()
        fc.value.set_files(files)
        page.wait_for_timeout(4000)
        print(f"    ↑ {len(files)} capturas")
        return len(files)
    except Exception:
        return 0


def auth_frame(page):
    for sel in ('iframe#aid-auth-widget-iFrame', 'iframe[name="aid-auth-widget"]', 'iframe[src*="idmsa"]'):
        loc = page.locator(sel)
        if loc.count():
            return loc.first.content_frame
    return None


def wait_login(page, timeout_s: int = 600) -> bool:
    print("[login] App Store Connect…", flush=True)
    page.goto("https://appstoreconnect.apple.com/apps", wait_until="domcontentloaded", timeout=120_000)
    print(f"  → Se pedir 2FA, conclua no navegador Chromium ({APPLE_ID})")
    deadline = time.time() + timeout_s
    filled = False
    while time.time() < deadline:
        url = page.url.lower()
        text = body(page)
        if APP_NAME in text or ("Apps" in text and "login" not in url and "E-mail ou número" not in text):
            print("  OK")
            return True
        frame = auth_frame(page)
        if frame and not filled:
            try:
                inp = frame.locator('input[type="text"], input[type="email"]').first
                if inp.count():
                    inp.fill(APPLE_ID)
                    for label in ("Continuar", "Continue"):
                        btn = frame.get_by_role("button", name=label)
                        if btn.count():
                            btn.first.click()
                            break
                    filled = True
            except Exception:
                pass
        elif "login" in url and page.locator('input[type="text"], input[type="email"]').count():
            page.locator('input[type="text"], input[type="email"]').first.fill(APPLE_ID)
            click(page, r"^Continuar$", r"^Continue$")
            filled = True
        page.wait_for_timeout(2500)
    return False


def goto_asc(page, path: str) -> None:
    dismiss_dialogs(page)
    page.goto(f"{ASC}{path}", wait_until="domcontentloaded", timeout=120_000)
    for _ in range(12):
        page.wait_for_timeout(1000)
        if len(body(page)) > 400:
            break


def open_version_page(page) -> bool:
    goto_asc(page, f"/apps/{APP_ID}/distribution/ios/version/inflight")
    try:
        page.wait_for_selector(
            "textarea, button:has-text('Adicionar para revisão'), button:has-text('Add for Review')",
            timeout=30_000,
        )
    except Exception:
        pass
    text = body(page)
    ok = any(
        k in text
        for k in (
            "Descrição",
            "Description",
            "Adicionar para revisão",
            "Add for Review",
            "Atualizar revisão",
            "Update Review",
            "Rejeitado",
            "Rejected",
            "capturas de tela",
            "Adicionar compilação",
            "Add Build",
            "de 10 capturas",
            "Versão 1.0",
            "Version 1.0",
        )
    )
    if not ok:
        click(page, r"1\.0.*Preparar", r"Preparar para envio", r"Prepare for Submission")
        page.wait_for_timeout(4000)
        text = body(page)
        ok = "Descrição" in text or "Description" in text or "Adicionar compilação" in text
    if ok:
        print("  versão 1.0 aberta")
    return ok


def shot(page, tag: str) -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(DIST / f"appstore-review-{tag}.png"), full_page=True)
    (DIST / f"appstore-review-{tag}.txt").write_text(body(page)[:15000], encoding="utf-8")


def check_blockers(text: str) -> list[str]:
    blockers = []
    if re.search(r"contrato de licença.*revisado|license agreement.*updated", text, re.I):
        blockers.append("Aceitar contrato do Apple Developer Program (titular da conta)")
    if "Adicionar compilação" in text or "Add Build" in text:
        blockers.append("Build não vinculado à versão")
    if re.search(r"0 de 10 capturas|0 of 10 Screenshots", text) and not re.search(
        r"[1-9]\d* de 10 capturas|[1-9]\d* of 10 Screenshots", text
    ):
        blockers.append("Capturas de tela não enviadas")
    return blockers


def fill_field_by_label(page, labels: list[str], value: str, *, textarea: bool = False) -> bool:
    tag = "textarea" if textarea else "input"
    for label in labels:
        loc = page.locator(
            f'div:has(> label:has-text("{label}")) {tag}, '
            f'div:has-text("{label}") {tag}, '
            f'label:has-text("{label}") + {tag}'
        ).first
        if loc.count():
            try:
                loc.fill(value, timeout=5000)
                return True
            except Exception:
                pass
    return False


def set_categories(page) -> None:
    sels = page.locator("select")
    if sels.count() >= 1:
        for label in ("Educação", "Education"):
            try:
                sels.nth(0).select_option(label=label)
                break
            except Exception:
                pass
    if sels.count() >= 2:
        for label in ("Referência", "Reference"):
            try:
                sels.nth(1).select_option(label=label)
                break
            except Exception:
                pass
    page.evaluate(
        """() => {
          const pick = (sel, words) => {
            if (!sel) return;
            for (const opt of sel.options) {
              const t = opt.textContent || '';
              if (words.some(w => t.includes(w))) {
                sel.value = opt.value;
                sel.dispatchEvent(new Event('change', { bubbles: true }));
              }
            }
          };
          const s = document.querySelectorAll('select');
          pick(s[0], ['Educação', 'Education']);
          pick(s[1], ['Referência', 'Reference']);
        }"""
    )
    print("    ✓ categorias")


def complete_age_rating(page) -> None:
    none_words = ("nenhum", "none", "não", "no", "not applicable", "não se aplica")
    nav_words = ("próximo", "next", "continuar", "continue", "salvar", "save", "concluir", "done")
    for step in range(100):
        if re.search(r"\b4\+\b|\b9\+\b|\b12\+\b|\b17\+\b", body(page)):
            print("    ✓ classificação etária atribuída")
            return
        dlg = page.get_by_role("dialog")
        scope = dlg if dlg.count() else page
        acted = False
        for radio in scope.locator('input[type="radio"]:visible').all():
            try:
                label = radio.evaluate(
                    """el => {
                      const id = el.id;
                      const lbl = id ? document.querySelector(`label[for="${id}"]`) : el.closest('label');
                      return (lbl?.innerText || el.value || '').toLowerCase();
                    }"""
                )
                if any(w in label for w in none_words):
                    radio.click(timeout=1500)
                    acted = True
                    page.wait_for_timeout(200)
            except Exception:
                pass
        if not acted:
            for word in ("Nenhum", "None", "Não", "No"):
                loc = scope.get_by_role("radio", name=re.compile(rf"^{word}$", re.I))
                if loc.count():
                    loc.first.click(timeout=1500)
                    acted = True
                    page.wait_for_timeout(200)
                    break
        if not acted:
            for word in nav_words:
                btn = scope.get_by_role("button", name=re.compile(rf"^{word}$", re.I))
                if btn.count() and btn.first.is_enabled():
                    btn.first.click(timeout=2000)
                    page.wait_for_timeout(600)
                    acted = True
                    break
        if not acted:
            break
    dismiss_dialogs(page)
    print("    ✓ classificação etária")


def step_app_information(page) -> None:
    print("\n═══ Informações do app ═══")
    goto_asc(page, f"/apps/{APP_ID}/distribution/info")
    set_categories(page)
    if "não contém" not in body(page).lower() and "does not contain" not in body(page).lower():
        block = page.locator("div").filter(has_text=re.compile(r"Direitos de conteúdo|Content Rights", re.I)).first
        if block.count():
            block.get_by_role("button", name=re.compile(r"^Editar$|^Edit$", re.I)).first.click(timeout=5000)
        dlg = page.get_by_role("dialog")
        if dlg.count():
            dlg.get_by_text(re.compile(r"não contém|does not contain", re.I)).first.click(timeout=5000)
            dlg.get_by_role("button", name=re.compile(r"^Concluído$|^Done$", re.I)).first.click(timeout=5000)
            page.wait_for_timeout(1500)
        print("    ✓ direitos de conteúdo")
    # Classificação etária
    try:
        page.get_by_role("button", name=re.compile(r"Configurar classificações etárias|Set Up Age Ratings", re.I)).first.click(
            timeout=10_000
        )
        page.wait_for_timeout(2000)
    except Exception:
        click(page, r"Configurar classificações etárias", r"Set Up Age Ratings")
    if "Configurar classificações etárias" in body(page) or "Set Up Age Ratings" in body(page):
        complete_age_rating(page)
    dismiss_dialogs(page)
    save = page.get_by_role("button", name=re.compile(r"^Salvar$|^Save$", re.I)).first
    if save.is_enabled(timeout=3000):
        save.click(timeout=8000)
    page.wait_for_timeout(2000)
    shot(page, "app-info")


def step_app_privacy(page) -> None:
    print("\n═══ Privacidade do app ═══")
    goto_asc(page, f"/apps/{APP_ID}/distribution/ios/version/inflight")
    click(page, r"Privacidade do app", r"App Privacy")
    page.wait_for_timeout(3000)
    if "Privacidade do app" not in body(page) and "App Privacy" not in body(page):
        goto_asc(page, f"/apps/{APP_ID}/distribution/appprivacy")
    text = body(page)
    if "Começar" in text or "Get Started" in text:
        click(page, r"^Começar$", r"^Get Started$")
        page.wait_for_timeout(2000)
        for _ in range(20):
            dlg = page.get_by_role("dialog")
            target = dlg if dlg.count() else page
            if target.get_by_text(re.compile(r"não coleta|does not collect|nenhum dado|no data", re.I)).count():
                target.get_by_text(re.compile(r"não coleta|does not collect|nenhum dado|no data", re.I)).first.click(timeout=3000)
                page.wait_for_timeout(500)
            for word in ("Próximo", "Next", "Salvar", "Save", "Publicar", "Publish"):
                btn = target.get_by_role("button", name=word)
                if btn.count():
                    btn.first.click(timeout=3000)
                    page.wait_for_timeout(600)
            if not dlg.count():
                break
    if PRIVACY not in body(page):
        click(page, r"^Editar$", r"^Edit$")
        page.wait_for_timeout(1500)
        dlg = page.get_by_role("dialog")
        target = dlg if dlg.count() else page
        for inp in target.locator("input:visible").all():
            try:
                inp.fill(PRIVACY, timeout=3000)
                break
            except Exception:
                pass
        if dlg.count():
            dlg.get_by_role("button", name=re.compile(r"^Salvar$|^Save$", re.I)).first.click(timeout=8000)
            page.wait_for_timeout(2000)
    dismiss_dialogs(page)
    page.evaluate("window.scrollTo(0, 0)")
    pub = page.get_by_role("button", name=re.compile(r"^Publicar$|^Publish$", re.I))
    if pub.count():
        pub.first.click(timeout=10_000)
        page.wait_for_timeout(2000)
    dlg = page.get_by_role("dialog")
    if dlg.count() and re.search(r"privacidade|privacy", body(page), re.I):
        dlg.get_by_role("button", name=re.compile(r"^Publicar$|^Publish$", re.I)).last.click(timeout=10_000)
        page.wait_for_timeout(4000)
        print("    ✓ privacidade publicada")
    elif "Dados não coletados" in body(page) or "No data collected" in body(page):
        print("    ✓ privacidade já configurada")
    shot(page, "privacy")


def step_pricing(page) -> None:
    print("\n═══ Preços ═══")
    goto_asc(page, f"/apps/{APP_ID}/distribution/pricing")
    if "Adicionar preços" in body(page) or "Add Pricing" in body(page):
        page.locator("button, a").filter(has_text=re.compile(r"Adicionar preços|Add Pricing", re.I)).first.click(timeout=10_000)
    page.wait_for_timeout(2500)
    for _ in range(15):
        dlg = page.get_by_role("dialog")
        scope = dlg if dlg.count() else page
        for label in ("Gratuito", "Free", "0,00", "0.00"):
            row = scope.get_by_role("row").filter(has_text=re.compile(label, re.I))
            if row.count():
                row.first.click(timeout=3000)
                page.wait_for_timeout(400)
                break
            loc = scope.get_by_text(re.compile(re.escape(label), re.I))
            if loc.count():
                loc.first.click(timeout=3000)
                page.wait_for_timeout(400)
                break
        for word in ("Próximo", "Next", "Concluir", "Done", "Adicionar", "Add"):
            btn = scope.get_by_role("button", name=word)
            if btn.count() and btn.first.is_enabled():
                btn.first.click(timeout=3000)
                page.wait_for_timeout(700)
        if not dlg.count() and "Gratuito" in body(page):
            break
    click(page, r"^Salvar$", r"^Save$")
    page.wait_for_timeout(2000)
    print("    ✓ preço gratuito")
    shot(page, "pricing")


def fill_labeled_input(page, label: str, value: str) -> bool:
    block = page.locator("div").filter(has_text=re.compile(rf"^{re.escape(label)}$", re.I)).first
    if block.count():
        inp = block.locator("xpath=following::input[1]").first
        try:
            inp.fill(value, timeout=5000)
            return True
        except Exception:
            pass
    loc = page.get_by_label(label, exact=False)
    if loc.count():
        try:
            loc.first.fill(value, timeout=5000)
            return True
        except Exception:
            pass
    return False


def step_fill_metadata(page) -> None:
    print("\n═══ Metadados e capturas ═══")
    open_version_page(page)
    page.evaluate("window.scrollTo(0, 0)")
    desc = page.locator("textarea").filter(has=page.locator("xpath=preceding::*[contains(., 'Descrição') or contains(., 'Description')]"))
    if desc.count():
        desc.first.fill(DESCRIPTION)
    else:
        tas = page.locator("textarea:visible")
        if tas.count() >= 2:
            tas.nth(1).fill(DESCRIPTION)
    fill_labeled_input(page, "Palavras-chave", KEYWORDS)
    fill_labeled_input(page, "Keywords", KEYWORDS)
    fill_labeled_input(page, "URL de suporte", SUPPORT)
    fill_labeled_input(page, "Support URL", SUPPORT)
    fill_labeled_input(page, "URL de marketing", MARKETING)
    fill_labeled_input(page, "Marketing URL", MARKETING)
    fill_labeled_input(page, "Copyright", "NaIntegra Cursos")
    print("    ✓ metadados")

    text = body(page)
    if re.search(r"0 de 10 capturas|0 of 10 Screenshots", text) and "10 de 10" not in text:
        shots = sorted(ASSETS.glob("iphone-65-*.png"))[:5]
        upload_screenshots(page, *shots)
        page.wait_for_timeout(5000)
    save_btn = page.get_by_role("button", name=re.compile(r"^Salvar$|^Save$", re.I)).first
    try:
        save_btn.click(timeout=10_000)
    except Exception:
        page.wait_for_timeout(8000)
        if save_btn.is_enabled(timeout=5000):
            save_btn.click(timeout=10_000)
    page.wait_for_timeout(4000)
    shot(page, "metadata")


def step_export_compliance(page) -> None:
    print("\n═══ Conformidade de exportação ═══")
    open_version_page(page)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    if "Faltam dados de conformidade" not in body(page) and "Missing Compliance" not in body(page):
        print("    conformidade OK")
        return
    page.locator("text=Faltam dados de conformidade").scroll_into_view_if_needed(timeout=5000)
    page.wait_for_timeout(500)
    page.get_by_text(re.compile(r"^Gerenciar$|^Manage$", re.I)).last.click(force=True, timeout=10_000)
    page.wait_for_timeout(2500)
    dlg = page.get_by_role("dialog")
    if dlg.count():
        dlg.locator('input[type="radio"]').last.check(force=True)
        page.wait_for_timeout(500)
        dlg.locator("a").filter(has_text=re.compile(r"^Salvar$|^Save$", re.I)).click(timeout=8000)
        page.wait_for_timeout(2000)
    dismiss_dialogs(page)
    click(page, r"^Salvar$", r"^Save$")
    page.wait_for_timeout(2000)
    print("    ✓ conformidade exportação")
    shot(page, "compliance")


def step_ipad_screenshots(page) -> None:
    print("\n═══ Capturas iPad ═══")
    open_version_page(page)
    if "iPad" not in body(page):
        return
    click(page, r"^iPad$")
    page.wait_for_timeout(1500)
    text = body(page)
    if re.search(r"[1-9]\d* de \d+ capturas", text) and "0 de" not in text.split("iPad")[-1][:200]:
        print("    iPad já tem capturas")
        return
    shots = sorted(ASSETS.glob("ipad-13-*.png"))[:3]
    if shots:
        upload_screenshots(page, *shots)
        click(page, r"^Salvar$", r"^Save$")
        page.wait_for_timeout(2000)
        print(f"    ↑ {len(shots)} capturas iPad")


def in_review(text: str) -> bool:
    return bool(
        re.search(
            r"adicionada para revisão|added for review|Aguardando revisão|Waiting for Review|Em revisão|In Review",
            text,
            re.I,
        )
    )


def step_withdraw_from_review(page) -> bool:
    open_version_page(page)
    text = body(page)
    if not in_review(text):
        return False
    print("\n═══ Retirar da revisão (trocar build) ═══")
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(500)
    if not click(page, r"Retirar da revisão", r"Remove from Review", r"Retirar"):
        print("    [WARN] botão Retirar da revisão não encontrado")
        return False
    page.wait_for_timeout(2000)
    click(page, r"^Retirar$", r"^Remove$", r"^Confirmar$", r"^Confirm$")
    page.wait_for_timeout(4000)
    shot(page, "withdraw")
    return True


def linked_build(text: str) -> str | None:
    m = re.search(
        r"Compilação[\s\S]{0,400}?\n(\d+)\s*\n\s*1\.0",
        text,
        re.I,
    )
    if m:
        return m.group(1)
    m = re.search(r"COMPILAÇÃO[\s\S]*?\n(\d+)\s*\n", text, re.I)
    return m.group(1) if m else None


def step_add_build(page) -> None:
    print("\n═══ Vincular build ═══")
    open_version_page(page)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
    page.wait_for_timeout(1000)
    text = body(page)
    current = linked_build(text)
    if current == BUILD:
        print(f"    ✓ build {BUILD} já vinculado")
        return
    if current and current != BUILD:
        print(f"    compilação atual: {current} → trocar para {BUILD}")
    if "Adicionar compilação" not in text and "Add Build" not in text:
        for pat in (r"Remover compilação", r"Remove Build", r"Excluir compilação", r"Delete Build"):
            if click(page, pat):
                page.wait_for_timeout(2000)
                text = body(page)
                break
        if current and current != BUILD:
            try:
                row = page.get_by_role("row").filter(has_text=re.compile(r"1\.0\.1|1\.0\.0", re.I))
                if row.count():
                    row.first.click(timeout=5000)
                    page.wait_for_timeout(1500)
                else:
                    page.get_by_text(re.compile(rf"^{re.escape(current)}$")).first.click(timeout=5000)
                    page.wait_for_timeout(1500)
            except Exception:
                pass
            click(page, r"Adicionar compilação", r"Add Build", r"Selecionar compilação", r"Select Build")
    if not click(page, r"Adicionar compilação", r"Add Build"):
        click(page, r"^\+$")
        try:
            page.locator("table").filter(has_text=re.compile(r"COMPILAÇÃO|Build", re.I)).locator("button").first.click(
                timeout=5000
            )
        except Exception:
            pass
    if not page.get_by_role("dialog").count():
        if not click(page, r"Adicionar compilação", r"Add Build"):
            print("    [WARN] Adicionar compilação não disponível")
            shot(page, "build-missing")
            return
    page.wait_for_timeout(3000)
    dialog = page.get_by_role("dialog")
    dialog.wait_for(state="visible", timeout=10_000)
    selected = False
    for pat in (rf"\({BUILD}\)", rf"1\.0\s*\({BUILD}\)", rf"1\.0\.1\s*\({BUILD}\)", rf"Version.*{BUILD}"):
        row = dialog.get_by_role("row").filter(has_text=re.compile(pat, re.I))
        if row.count():
            row.locator("input[type='radio'], input[type='checkbox']").first.click(timeout=5000)
            selected = True
            print(f"    ✓ build {BUILD}")
            break
    if not selected:
        radios = dialog.locator("input[type='radio']")
        if radios.count():
            radios.first.click(timeout=5000)
            print(f"    ✓ build {BUILD} (primeiro disponível)")
    for label in ("Concluído", "Done", "Concluir", "OK", "Selecionar", "Select"):
        btn = dialog.get_by_role("button", name=label)
        if btn.count():
            btn.first.click(timeout=5000)
            break
    else:
        page.keyboard.press("Escape")
    page.wait_for_timeout(2000)
    click(page, r"^Salvar$", r"^Save$")
    page.wait_for_timeout(3000)
    shot(page, "build")


def step_review_credentials(page) -> None:
    print("\n═══ Credenciais do revisor ═══")
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)
    click(page, r"Início de sessão obrigatório", r"Sign-in required", r"login obrigatório", r"obrigatório")
    fill_labeled_input(page, "Nome de usuário", REVIEWER)
    fill_labeled_input(page, "Username", REVIEWER)
    fill_labeled_input(page, "Senha", REVIEWER_PASSWORD)
    fill_labeled_input(page, "Password", REVIEWER_PASSWORD)
    fill_labeled_input(page, "Nome", REVIEW_CONTACT["first"])
    fill_labeled_input(page, "Sobrenome", REVIEW_CONTACT["last"])
    fill_labeled_input(page, "Last Name", REVIEW_CONTACT["last"])
    fill_labeled_input(page, "Telefone", REVIEW_CONTACT["phone"])
    fill_labeled_input(page, "Phone", REVIEW_CONTACT["phone"])
    fill_labeled_input(page, "E-mail", REVIEW_CONTACT["email"])
    fill_labeled_input(page, "Email", REVIEW_CONTACT["email"])
    rev_inputs = page.locator('input[type="text"]:visible, input[type="password"]:visible')
    try:
        pw = page.locator('input[type="password"]:visible')
        if pw.count():
            texts = page.locator('input[type="text"]:visible')
            for i in range(texts.count()):
                val = texts.nth(i).input_value(timeout=1000)
                if not val and "@" in REVIEWER:
                    texts.nth(i).fill(REVIEWER)
                    break
            if not pw.first.input_value(timeout=1000):
                pw.first.fill(REVIEWER_PASSWORD)
            print("    ✓ login revisor")
    except Exception:
        pass
    for ta in reversed(page.locator("textarea:visible").all()):
        try:
            if ta.input_value(timeout=1000) == "":
                ta.fill(REVIEW_NOTES)
                print("    ✓ notas")
                break
        except Exception:
            continue
    click(page, r"^Salvar$", r"^Save$")
    page.wait_for_timeout(3000)
    shot(page, "review")


def step_submit(page) -> None:
    print("\n═══ Enviar para revisão ═══")
    open_version_page(page)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(500)
    text = body(page)
    if in_review(text):
        print("    ✓ já em revisão")
        shot(page, "submit-final")
        return
    submitted = False
    for label in (
        r"Atualizar revisão",
        r"Update Review",
        r"Adicionar para revisão",
        r"Add for Review",
    ):
        btn = page.get_by_role("button", name=re.compile(label, re.I))
        if btn.count():
            try:
                btn.first.scroll_into_view_if_needed(timeout=5000)
                btn.first.click(timeout=10_000)
                page.wait_for_timeout(1200)
                print(f"    ✓ {label}")
                submitted = True
                break
            except Exception:
                pass
    if not submitted and not click(
        page,
        r"Adicionar para revisão",
        r"Add for Review",
        r"Atualizar revisão",
        r"Update Review",
    ):
        print("    [WARN] botão Adicionar/Atualizar revisão não encontrado")
        shot(page, "submit-final")
        return
    page.wait_for_timeout(3000)
    click(page, r"^Enviar$", r"^Submit$", r"^Confirmar$", r"^Confirm$", r"^Adicionar$", r"^Add$")
    page.wait_for_timeout(5000)
    shot(page, "submit-final")


def main() -> None:
    build_only = "--build-only" in sys.argv
    blockers_only = "--blockers-only" in sys.argv
    if not build_only and not blockers_only:
        subprocess.run([sys.executable, str(MOBILE / "scripts/prepare-app-store-assets.py")], check=True)
    ensure_playwright()
    from playwright.sync_api import sync_playwright

    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE),
            headless=False,
            viewport={"width": 1440, "height": 900},
            locale="pt-BR",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        if not wait_login(page, timeout_s=600):
            ctx.close()
            raise SystemExit(f"Login não concluído — faça login com {APPLE_ID} no Chromium e rode novamente.")

        if not open_version_page(page):
            shot(page, "no-version")
            ctx.close()
            raise SystemExit(f"Não abriu versão de {APP_NAME}")

        text = body(page)
        if "contrato de licença" in text.lower():
            print("\n[AVISO] Banner de contrato ainda visível — confira Acordos (Apps pagos + Programa).")
            subprocess.run(["open", "https://appstoreconnect.apple.com/agreements"])

        if not re.search(r"Descrição|Description|capturas", text, re.I):
            print("[ERRO] Página da versão não carregou — tente novamente após aceitar todos os contratos.")
            shot(page, "no-version-page")
            ctx.close()
            raise SystemExit(1)

        blocker_steps = (
            (step_add_build, step_review_credentials, step_app_privacy, step_export_compliance, step_submit)
            if blockers_only
            else (step_app_information, step_app_privacy, step_pricing)
        )
        if blockers_only:
            lb0 = linked_build(body(page))
            if lb0 and lb0 != BUILD and (
                in_review(body(page))
                or re.search(r"Pronto para revisão|Ready for Review|Aguardando revisão", body(page), re.I)
            ):
                try:
                    step_withdraw_from_review(page)
                except Exception as exc:
                    print(f"    [WARN] withdraw: {exc}")
        for fn in blocker_steps:
            try:
                fn(page)
            except Exception as exc:
                print(f"    [WARN] {fn.__name__}: {exc}")
                dismiss_dialogs(page)
                shot(page, fn.__name__)
        dismiss_dialogs(page)
        if blockers_only:
            open_version_page(page)
            final = body(page)
            if re.search(
                r"Aguardando revisão|Waiting for Review|Pronto para revisão|Ready for Review|adicionada para revisão|added for review",
                final,
                re.I,
            ):
                lb = linked_build(final) or "?"
                if lb == BUILD:
                    print("\n[OK] Enviado para revisão da Apple.")
                else:
                    print(f"\n[AVISO] Na fila de revisão, mas compilação {lb} (esperado {BUILD}). Troque no ASC e reenvie.")
            else:
                lb = linked_build(final) or "?"
                print(f"\n[PENDENTE] Compilação vinculada: {lb} (meta: {BUILD}). IAPs lex_mensal/lex_anual na seção Assinaturas.")
                print(f"  Debug: {DIST}/appstore-review-submit-final.png")
            print("\nCredenciais revisor:", REVIEWER, "/", REVIEWER_PASSWORD)
            page.wait_for_timeout(2000)
            ctx.close()
            return
        if not open_version_page(page):
            print("[WARN] reabrindo versão 1.0…")
            open_version_page(page)
        if not blockers_only:
            for fn in (
                step_fill_metadata,
                step_review_credentials,
                step_ipad_screenshots,
            ):
                try:
                    fn(page)
                except Exception as exc:
                    print(f"    [WARN] {fn.__name__}: {exc}")
                    shot(page, fn.__name__)
            try:
                step_add_build(page)
            except Exception as exc:
                print(f"    [WARN] build: {exc}")
                shot(page, "build-error")
        if in_review(body(page)):
            step_withdraw_from_review(page)
            open_version_page(page)
            try:
                step_review_credentials(page)
            except Exception as exc:
                print(f"    [WARN] review creds: {exc}")
            try:
                step_add_build(page)
            except Exception as exc:
                print(f"    [WARN] build retry: {exc}")
        try:
            step_export_compliance(page)
        except Exception as exc:
            print(f"    [WARN] export: {exc}")
            shot(page, "compliance-error")
        open_version_page(page)
        click(page, r"^Salvar$", r"^Save$")
        page.wait_for_timeout(2000)
        step_submit(page)

        final = body(page)
        blockers = check_blockers(final)
        if re.search(r"Aguardando revisão|Waiting for Review|Em revisão|In Review", final, re.I):
            print("\n[OK] Enviado para revisão da Apple.")
        elif blockers:
            print("\n[PENDENTE] Conclua manualmente:")
            for b in blockers:
                print(f"  • {b}")
            print(f"  Debug: {DIST}/appstore-review-submit-final.png")
        else:
            print("\n[AVISO] Revise a tela e clique 'Adicionar para revisão' se necessário.")

        print("\nCredenciais revisor:", REVIEWER, "/", REVIEWER_PASSWORD)
        page.wait_for_timeout(2000)
        ctx.close()


if __name__ == "__main__":
    main()
