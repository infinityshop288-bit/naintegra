#!/usr/bin/env python3
"""Passos 1–4 Play Console: listar pendências, preencher políticas, enviar revisão."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOBILE = ROOT / "mobile"
ASSETS = MOBILE / "store-assets" / "generated"
DIST = MOBILE / "dist"
AAB = DIST / "naintegra-lex-release.aab"
PACKAGE = "br.com.naintegracursos.lex"
DEV_ID = os.environ.get("PLAY_DEV_ACCOUNT_ID", "5476168127224845991")
PROFILE = Path.home() / ".cache" / "naintegra-play-console-profile"

PRIVACY = "https://www.naintegracursos.com.br/lex/#/contato"
DELETE_ACCOUNT = "https://www.naintegracursos.com.br/lex/#/excluir-conta"
EMAIL = "contato@naintegracursos.com.br"
REVIEWER = os.environ.get("PLAY_REVIEWER_EMAIL", "teste.naintegra.lex@gmail.com")
REVIEWER_PASSWORD = os.environ.get("PLAY_REVIEWER_PASSWORD", "NaIntegraLex2026!")
SHORT_DESC = "Lei seca, súmulas, flashcards e questões para concursos públicos."
FULL_DESC = """NaIntegra Lex — legislação, jurisprudência, flashcards e questões para concursos públicos.

• Lei seca, súmulas, temas e julgados
• Flashcards e questões com comentários
• Funciona offline no celular
• Assinatura para acervo completo

Política: https://www.naintegracursos.com.br/lex/#/contato
Exclusão de conta: https://www.naintegracursos.com.br/lex/#/excluir-conta
Contato: contato@naintegracursos.com.br"""


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


def dismiss_errors(page) -> None:
    for pat in (r"^close$", r"Dispensar", r"Dismiss", r"Tentar novamente", r"Try again"):
        click(page, pat)
    page.keyboard.press("Escape")


def wait_ready(page, timeout_s: int = 30) -> None:
    markers = (
        r"Painel de publicação|Publishing overview|NaIntegra",
        r"Teste fechado|Closed testing|Ficha da loja|Store listing",
        r"Enviar .* revisão|Send .* review|Gerenciar publicação",
    )
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        text = body(page)
        if "Ocorreu um erro inesperado" in text or "An unexpected error" in text:
            dismiss_errors(page)
            page.wait_for_timeout(1500)
            continue
        if re.search(r"Carregando o Google Play Console|Loading Google Play Console", text):
            page.wait_for_timeout(2000)
            continue
        if PACKAGE in page.url and any(re.search(m, text, re.I) for m in markers):
            return
        if PACKAGE in page.url and len(text) > 800 and "app-list" not in page.url:
            return
        page.wait_for_timeout(1500)
    dismiss_errors(page)


def base() -> str:
    return f"https://play.google.com/console/u/0/developers/{DEV_ID}/app/{PACKAGE}"


def shot(page, tag: str) -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    p = DIST / f"play-review-{tag}.png"
    page.screenshot(path=str(p), full_page=True)
    (DIST / f"play-review-{tag}.txt").write_text(body(page)[:15000], encoding="utf-8")
    print(f"  debug: {p}", flush=True)


def ensure_dev(page) -> None:
    if not re.search(r"Escolha a conta|Choose the developer", body(page), re.I):
        return
    for _ in range(5):
        loc = page.get_by_text("Arnold Scott").first
        if loc.count():
            loc.click(timeout=5000)
            page.wait_for_timeout(2500)
            return


def wait_login(page) -> None:
    print("[login] Play Console…", flush=True)
    for _ in range(300):
        if "accounts.google.com" in page.url:
            time.sleep(2)
            continue
        if "play.google.com/console" in page.url:
            ensure_dev(page)
            if not re.search(r"Escolha a conta|Choose the developer", body(page), re.I):
                print("  OK", flush=True)
                return
        time.sleep(2)
    raise TimeoutError("login")


def click(page, *patterns: str) -> bool:
    for pat in patterns:
        rx = re.compile(pat, re.I)
        for loc in (
            page.get_by_role("button", name=rx),
            page.get_by_role("link", name=rx),
            page.get_by_text(rx),
        ):
            try:
                if loc.count():
                    loc.first.click(timeout=6000)
                    page.wait_for_timeout(1200)
                    print(f"    ✓ {pat[:40]}", flush=True)
                    return True
            except Exception:
                pass
    return False


def save(page) -> None:
    click(page, r"^Salvar$", r"^Save$", r"Salvar alterações", r"Save changes", r"^Próximo$", r"^Next$", r"^Concluir$", r"^Done$")


def fill_first(page, selectors: list[str], value: str) -> bool:
    for sel in selectors:
        loc = page.locator(sel).first
        if loc.count():
            try:
                loc.click(timeout=3000)
                loc.fill(value)
                return True
            except Exception:
                pass
    return False


def upload(page, path: Path) -> bool:
    if not path.is_file():
        return False
    loc = page.locator("input[type='file']").first
    if loc.count():
        loc.set_input_files(str(path))
        page.wait_for_timeout(2500)
        return True
    return False


def goto_app(page) -> bool:
    page.goto(base() + "/app-dashboard", wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(2500)
    ensure_dev(page)
    wait_ready(page)
    if PACKAGE in page.url and "app-dashboard" in page.url:
        return True
    for pat in (r"Ver app", r"View app", r"NaIntegra LEX", r"NaIntegra Lex"):
        if click(page, pat):
            page.wait_for_timeout(3000)
            break
    ok = PACKAGE in page.url
    if ok:
        print(f"  app: {page.url[:90]}", flush=True)
    return ok


def goto(page, *paths: str) -> bool:
    if PACKAGE not in page.url:
        if not goto_app(page):
            return False
    for path in paths:
        try:
            page.goto(base() + path, wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(2500)
            ensure_dev(page)
            wait_ready(page)
            if PACKAGE in page.url and "app-list" not in page.url:
                return True
        except Exception:
            continue
    if PACKAGE in page.url and "app-list" not in page.url:
        return True
    return goto_app(page)


def step1_list_pending(page) -> list[str]:
    print("\n═══ PASSO 1: Pendências ═══", flush=True)
    items: list[str] = []
    goto(page, "/publishing/overview", "/publishing", "/app-dashboard")
    shot(page, "step1-overview")
    text = body(page)
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) > 120:
            continue
        if re.search(
            r"pendente|required|obrigat|complete|preench|enviar|revisão|review|alteração|change",
            line,
            re.I,
        ):
            items.append(line)
    # links com status incompleto
    for a in page.locator("a").all()[:80]:
        try:
            t = a.inner_text(timeout=400).strip()
            href = a.get_attribute("href") or ""
            if t and re.search(r"política|policy|conteúdo|content|classific|data safety|segurança|público|listing|loja", t, re.I):
                items.append(f"{t} → {href[-60:]}")
        except Exception:
            pass
    out = DIST / "play-pending-items.txt"
    out.write_text("\n".join(dict.fromkeys(items)) or text[:5000], encoding="utf-8")
    print(f"  {len(items)} linha(s) → {out}", flush=True)
    for it in items[:20]:
        print(f"    • {it[:100]}", flush=True)
    return items


def step2_store_listing(page) -> None:
    print("\n═══ PASSO 2a: Ficha da loja ═══", flush=True)
    goto(page, "/store-presence/main-store-listing")
    fill_first(page, ["input[aria-label*='Título' i]", "input[name*='title' i]"], "NaIntegra Lex")
    fill_first(
        page,
        ["textarea[aria-label*='breve' i]", "input[aria-label*='short' i]"],
        SHORT_DESC,
    )
    fill_first(
        page,
        ["textarea[aria-label*='completa' i]", "textarea[name*='description' i]"],
        FULL_DESC,
    )
    fill_first(page, ["input[type='email']", "input[aria-label*='e-mail' i]"], EMAIL)
    fill_first(
        page,
        ["input[aria-label*='privacidade' i]", "input[aria-label*='privacy' i]"],
        PRIVACY,
    )
    upload(page, ASSETS / "icon-512-play-store.png")
    upload(page, ASSETS / "feature-graphic-1024x500.png")
    for s in sorted(ASSETS.glob("screenshot-*.png"))[:4]:
        upload(page, s)
    save(page)
    shot(page, "step2-listing")


def step2_app_access(page) -> None:
    print("\n═══ PASSO 2b: Acesso ao app (revisor) ═══", flush=True)
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
        "O app exige login para acessar o acervo completo.\n\n"
        f"E-mail: {REVIEWER}\n"
        f"Senha: {REVIEWER_PASSWORD}\n\n"
        "Conta de teste com assinatura Lex ativa. "
        "Após login: Lei Seca, Jurisprudência, Flashcards e Questões disponíveis. "
        "Sem login, apenas telas públicas (preços/contato)."
    )
    fill_first(page, ["textarea"], instructions)
    fill_first(page, ["input[type='email']", "input[type='text']"], REVIEWER)
    save(page)
    shot(page, "step2-access")


def step2_ads(page) -> None:
    print("\n═══ PASSO 2c: Anúncios ═══", flush=True)
    goto(page, "/app-content/ad-id", "/app-content/ads-declaration", "/app-content/ads")
    click(page, r"Não contém anúncios", r"No, my app does not contain ads", r"Não", r"No")
    save(page)


def step2_content_rating(page) -> None:
    print("\n═══ PASSO 2d: Classificação de conteúdo ═══", flush=True)
    goto(page, "/app-content/content-rating", "/content-rating")
    click(page, r"Iniciar questionário", r"Start questionnaire", r"Continuar", r"Continue")
    for _ in range(25):
        if click(page, r"Educación|Education|Educação"):
            pass
        elif click(page, r"Não|No|Nenhum|None"):
            pass
        elif click(page, r"Salvar|Save|Próximo|Next|Enviar|Submit|Concluir|Done|Calcular|Calculate"):
            page.wait_for_timeout(1500)
        else:
            break
    save(page)
    shot(page, "step2-rating")


def step2_target_audience(page) -> None:
    print("\n═══ PASSo 2e: Público-alvo ═══", flush=True)
    goto(page, "/target-audience-content", "/app-content/target-audience")
    click(page, r"13|16|18|adulto|adult", r"Não direcionado a crianças", r"not directed at children")
    save(page)


def step2_data_safety(page) -> None:
    print("\n═══ PASSO 2f: Segurança dos dados ═══", flush=True)
    goto(page, "/data-privacy-security/data-safety", "/data-privacy-security")
    click(page, r"Iniciar|Start|Gerenciar|Manage", r"Próximo|Next")
    # respostas típicas app educacional com login
    for pat in (
        r"Sim, coletamos|Yes, we collect",
        r"Conta|Account",
        r"E-mail|Email",
        r"Atividade do app|App activity",
        r"Autenticação|Authentication",
        r"Não vendemos|We don't sell|No,.*sell",
        r"Opcional|Optional|Obrigatório|Required",
    ):
        click(page, pat)
    save(page)
    shot(page, "step2-data-safety")


def step2_closed_track(page) -> None:
    print("\n═══ PASSO 2g: Teste fechado (BR + testadores) ═══", flush=True)
    goto(page, "/tracks/closed-testing/countries")
    page.evaluate(
        """() => {
          const el = [...document.querySelectorAll('[debug-id="country-name"]')]
            .find(n => n.textContent.trim() === 'Brasil');
          if (!el) return false;
          const row = el.closest('[role="row"]') || el.parentElement?.parentElement;
          const cb = row?.querySelector('input[type="checkbox"]');
          if (cb) cb.click(); else el.click();
          return true;
        }"""
    )
    save(page)
    goto(page, "/tracks/closed-testing/testers")
    click(page, r"Criar lista", r"Create list", r"Testadores", r"Testers")
    fill_first(page, ["input[type='text']"], "NaIntegra Lex testers")
    fill_first(page, ["textarea"], "\n".join(
        e.strip()
        for e in os.environ.get(
            "PLAY_TESTER_EMAILS",
            "infinity.shop288@gmail.com,contato@naintegracursos.com.br,teste.naintegra.lex@gmail.com",
        ).split(",")
        if "@" in e
    ))
    save(page)
    shot(page, "step2-closed")


def step2_rollout(page) -> bool:
    print("\n═══ PASSO 2h: Upload AAB + implantar teste fechado ═══", flush=True)
    if not AAB.is_file():
        alt = Path.home() / "Documents/NaIntegra-Lex-GooglePlay/naintegra-lex-release-v1.0.1-offline.aab"
        if alt.is_file():
            import shutil
            shutil.copy2(alt, AAB)
        else:
            print(f"  AAB ausente: {AAB}", flush=True)
            return False

    for path in ("/tracks/closed-testing/releases", "/tracks/closed-testing"):
        goto(page, path)
        if click(page, r"Editar versão", r"Edit release", r"Revisar versão", r"Review release"):
            break
    else:
        goto(page, "/tracks/closed-testing/releases/create")
        click(page, r"Criar nova versão", r"Create new release", r"Nova versão")

    inp = page.locator("input[type='file']").first
    if inp.count():
        inp.set_input_files(str(AAB))
        print(f"  AAB: {AAB.name}", flush=True)
        page.wait_for_timeout(8000)

    click(page, r"Avançar", r"Next", r"Revisar versão", r"Review release")
    page.wait_for_timeout(2000)
    for _ in range(5):
        if click(
            page,
            r"Iniciar implantação para teste fechado",
            r"Iniciar implantação",
            r"Start rollout to closed testing",
            r"Start rollout",
            r"Implantar",
            r"Deploy",
            r"Salvar e publicar",
            r"Save and publish",
        ):
            page.wait_for_timeout(4000)
            click(page, r"^Confirmar$", r"^Confirm$", r"Enviar", r"Send")
            page.wait_for_timeout(3000)
            shot(page, "step2-rollout")
            if re.search(r"implantação|rollout|enviad|publicad|review", body(page), re.I):
                print("  implantação OK", flush=True)
                return True
    shot(page, "step2-rollout")
    return False


def step3_send_review(page) -> bool:
    print("\n═══ PASSO 3: Enviar para revisão ═══", flush=True)
    goto(page, "/publishing/overview", "/publishing", "/app-dashboard")
    wait_ready(page)
    shot(page, "step3-before-send")

    def confirm_send() -> bool:
        for _ in range(3):
            click(page, r"Enviar", r"Send", r"Confirmar", r"Confirm", r"Publicar", r"Publish")
            page.wait_for_timeout(2500)
            text = body(page)
            if re.search(
                r"enviad.* revisão|sent for review|em análise|under review|aguardando revisão",
                text,
                re.I,
            ):
                return True
        return False

    for pat in (
        r"Enviar .* alterações para revisão",
        r"Send .* changes for review",
        r"Enviar .* para revisão",
        r"Enviar para revisão",
        r"Send for review",
        r"Publicar alterações",
        r"Publish changes",
        r"Gerenciar publicação",
        r"Manage publication",
    ):
        if click(page, pat):
            page.wait_for_timeout(2000)
            if confirm_send():
                shot(page, "step3-after-send")
                return True

    goto(page, "/publishing/overview")
    for link in page.locator("button, a, [role='button']").all()[:60]:
        try:
            t = link.inner_text(timeout=400).strip()
            if not t or len(t) > 80:
                continue
            if re.search(r"enviar.*revisão|send.*review|publicar alterações|publish changes", t, re.I):
                link.click(timeout=6000)
                page.wait_for_timeout(2000)
                if confirm_send():
                    shot(page, "step3-sent")
                    return True
        except Exception:
            pass
    return False


def step4_summary(page) -> None:
    print("\n═══ PASSO 4: Aguardar revisão (até 7 dias) ═══", flush=True)
    goto(page, "/publishing/overview", "/app-dashboard")
    shot(page, "step4-final")
    msg = DIST / "play-review-status.txt"
    msg.write_text(
        f"URL: {page.url}\n\n{body(page)[:8000]}",
        encoding="utf-8",
    )
    print(f"  Status salvo: {msg}", flush=True)
    print(
        "\n  Enquanto aguarda:\n"
        "  • Acompanhe Play Console → Painel de publicação\n"
        "  • Testadores recebem e-mail após aprovação\n"
        "  • Não reenvie o AAB sem necessidade\n",
        flush=True,
    )


def main() -> int:
    ensure_playwright()
    from playwright.sync_api import sync_playwright

    skip_forms = os.environ.get("PLAY_REVIEW_SKIP_FORMS", "").lower() in ("1", "true", "yes")
    PROFILE.mkdir(parents=True, exist_ok=True)
    ok_send = False

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
        if not goto_app(page):
            raise RuntimeError("Não entrou no app NaIntegra Lex")

        step1_list_pending(page)
        if not skip_forms:
            step2_store_listing(page)
            step2_app_access(page)
            step2_ads(page)
            step2_content_rating(page)
            step2_target_audience(page)
            step2_data_safety(page)
        step2_closed_track(page)
        step2_rollout(page)
        ok_send = step3_send_review(page)
        step4_summary(page)

        page.wait_for_timeout(8000)
        ctx.close()

    if not ok_send:
        print("\n[WARN] 'Enviar para revisão' não confirmado — confira play-review-step3-before-send.png", file=sys.stderr)
        return 1
    print("\n[OK] Alterações enviadas para revisão Google.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
