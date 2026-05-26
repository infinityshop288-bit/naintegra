#!/usr/bin/env python3
"""Smoke tests for NaIntegra Lex mobile apps (Android + iOS Capacitor shells)."""
from __future__ import annotations

import json
import plistlib
import re
import ssl
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
MOBILE = ROOT / "mobile"
PROD_BASE = "https://www.naintegracursos.com.br/lex"
TIMEOUT = 20


@dataclass
class Suite:
    name: str
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def ok(self, msg: str) -> None:
        self.passed.append(msg)

    def fail(self, msg: str) -> None:
        self.failed.append(msg)

    def skip(self, msg: str) -> None:
        self.skipped.append(msg)


def fetch(url: str, *, method: str = "GET") -> tuple[int, dict[str, str], bytes]:
    req = Request(url, method=method, headers={"User-Agent": "NaIntegraLexMobileSmoke/1.0"})
    ctx = ssl.create_default_context()
    with urlopen(req, timeout=TIMEOUT, context=ctx) as resp:
        headers = {k.lower(): v for k, v in resp.headers.items()}
        return resp.status, headers, resp.read()


def curl_fetch(url: str) -> tuple[int, bytes]:
    """Fallback via curl quando Python SSL falha (comum no macOS dev)."""
    proc = subprocess.run(
        ["curl", "-sS", "-L", "-w", "\n%{http_code}", url],
        capture_output=True,
        timeout=TIMEOUT,
    )
    if proc.returncode != 0:
        raise URLError(proc.stderr.decode("utf-8", errors="replace") or "curl failed")
    raw = proc.stdout
    if b"\n" not in raw:
        raise URLError("curl resposta inválida")
    body, code_line = raw.rsplit(b"\n", 1)
    return int(code_line.decode().strip()), body


def http_get(url: str) -> tuple[int, bytes]:
    try:
        status, _, body = fetch(url)
        return status, body
    except URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            return curl_fetch(url)
        raise


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def android_manifest(path: Path) -> ET.Element:
    tree = ET.parse(path)
    root = tree.getroot()
    ns = {"a": "http://schemas.android.com/apk/res/android"}
    root.ns = ns  # type: ignore[attr-defined]
    return root


def test_project_structure(android: Suite, ios: Suite, shared: Suite) -> None:
    required_android = [
        MOBILE / "android/app/build.gradle",
        MOBILE / "android/app/src/main/AndroidManifest.xml",
        MOBILE / "android/app/src/main/java/br/com/naintegracursos/lex/MainActivity.java",
        MOBILE / "android/gradlew",
    ]
    for p in required_android:
        if p.exists():
            android.ok(f"arquivo presente: {p.relative_to(ROOT)}")
        else:
            # MainActivity path may differ — try glob
            if "MainActivity" in p.name:
                matches = list((MOBILE / "android").rglob("MainActivity.java"))
                if matches:
                    android.ok(f"MainActivity encontrado: {matches[0].relative_to(ROOT)}")
                    continue
            android.fail(f"arquivo ausente: {p.relative_to(ROOT)}")

    ios_required = [
        MOBILE / "ios/App/App.xcworkspace",
        MOBILE / "ios/App/Podfile",
        MOBILE / "ios/App/App/Info.plist",
        MOBILE / "ios/App/App/AppDelegate.swift",
    ]
    for p in ios_required:
        if p.exists():
            ios.ok(f"arquivo presente: {p.relative_to(ROOT)}")
        else:
            ios.fail(f"arquivo ausente: {p.relative_to(ROOT)}")

    if (MOBILE / "ios/App/Podfile.lock").exists():
        ios.ok("Podfile.lock presente (pods instalados)")
    else:
        ios.fail("Podfile.lock ausente — rode pod install")

    for p in [MOBILE / "capacitor.config.ts", MOBILE / "package.json", MOBILE / "www/index.html"]:
        if p.exists():
            shared.ok(f"base Capacitor: {p.relative_to(ROOT)}")
        else:
            shared.fail(f"base ausente: {p.relative_to(ROOT)}")


def test_capacitor_config(shared: Suite) -> dict:
    cfg_path = MOBILE / "ios/App/App/capacitor.config.json"
    if not cfg_path.exists():
        shared.fail("capacitor.config.json não sincronizado em iOS")
        return {}
    cfg = load_json(cfg_path)
    expected_id = "br.com.naintegracursos.lex"
    if cfg.get("appId") == expected_id:
        shared.ok(f"appId = {expected_id}")
    else:
        shared.fail(f"appId incorreto: {cfg.get('appId')}")
    if cfg.get("appName") == "NaIntegra Lex":
        shared.ok("appName = NaIntegra Lex")
    else:
        shared.fail(f"appName incorreto: {cfg.get('appName')}")
    server = cfg.get("server") or {}
    url = server.get("url", "")
    if url.startswith("https://www.naintegracursos.com.br/lex"):
        shared.ok(f"server.url remoto: {url}")
    else:
        shared.fail(f"server.url inesperado: {url!r}")
    plugins = cfg.get("plugins") or {}
    if "SplashScreen" in plugins and "StatusBar" in plugins:
        shared.ok("plugins SplashScreen + StatusBar configurados")
    else:
        shared.fail("plugins nativos incompletos")
    pkg = cfg.get("packageClassList") or []
    for name in ("AppPlugin", "SplashScreenPlugin", "StatusBarPlugin"):
        if name in pkg:
            shared.ok(f"plugin nativo registrado: {name}")
        else:
            shared.fail(f"plugin ausente: {name}")
    return cfg


def test_android_manifest(android: Suite) -> None:
    manifest = MOBILE / "android/app/src/main/AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")
    gradle = (MOBILE / "android/app/build.gradle").read_text(encoding="utf-8")
    app_id = "br.com.naintegracursos.lex"
    if f'applicationId "{app_id}"' in gradle:
        android.ok(f"applicationId Gradle = {app_id}")
    else:
        android.fail("applicationId Gradle incorreto")
    if "android.permission.INTERNET" in text:
        android.ok("permissão INTERNET")
    else:
        android.fail("permissão INTERNET ausente")
    if "www.naintegracursos.com.br" in text and 'pathPrefix="/lex"' in text.replace(" ", ""):
        android.ok("deep link HTTPS /lex")
    else:
        android.fail("deep link HTTPS /lex ausente")
    if f'android:scheme="{app_id}"' in text.replace(" ", ""):
        android.ok(f"custom URL scheme {app_id}")
    else:
        android.fail("custom URL scheme ausente")
    if "NaIntegra Lex" in (MOBILE / "android/app/src/main/res/values/strings.xml").read_text():
        android.ok("nome do app nos strings.xml")
    else:
        android.fail("nome do app ausente em strings.xml")
    icon = MOBILE / "android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png"
    if icon.exists() and icon.stat().st_size > 1000:
        android.ok("ícone launcher personalizado")
    else:
        android.fail("ícone launcher ausente ou placeholder")


def test_ios_config(ios: Suite) -> None:
    plist_path = MOBILE / "ios/App/App/Info.plist"
    with plist_path.open("rb") as fh:
        plist = plistlib.load(fh)
    if plist.get("CFBundleDisplayName") == "NaIntegra Lex":
        ios.ok("CFBundleDisplayName = NaIntegra Lex")
    else:
        ios.fail(f"CFBundleDisplayName: {plist.get('CFBundleDisplayName')}")
    pbx = (MOBILE / "ios/App/App.xcodeproj/project.pbxproj").read_text(encoding="utf-8")
    if "PRODUCT_BUNDLE_IDENTIFIER = br.com.naintegracursos.lex" in pbx:
        ios.ok("PRODUCT_BUNDLE_IDENTIFIER correto")
    else:
        ios.fail("PRODUCT_BUNDLE_IDENTIFIER incorreto")
    if "MARKETING_VERSION = 1.0.0" in pbx:
        ios.ok("MARKETING_VERSION = 1.0.0")
    else:
        ios.fail("MARKETING_VERSION diferente de 1.0.0")
    url_types = plist.get("CFBundleURLTypes") or []
    schemes: set[str] = set()
    for item in url_types:
        for s in item.get("CFBundleURLSchemes") or []:
            schemes.add(s)
    for expected in ("NaIntegraLex", "br.com.naintegracursos.lex"):
        if expected in schemes:
            ios.ok(f"URL scheme iOS: {expected}")
        else:
            ios.fail(f"URL scheme iOS ausente: {expected}")
    icon = MOBILE / "ios/App/App/Assets.xcassets/AppIcon.appiconset/AppIcon-1024.png"
    if icon.exists() and icon.stat().st_size > 1000:
        ios.ok("AppIcon 1024 personalizado")
    else:
        ios.fail("AppIcon 1024 ausente")


def test_bundled_www(shared: Suite) -> None:
    www = MOBILE / "www"
    required = [
        "index.html",
        "auth-callback.html",
        "manifest.json",
        "js/app.js",
        "js/config.js",
        "js/auth.js",
        "data/corpus.json",
        "data/legis_catalog.json",
        "data/legis_bodies.json",
        "data/flashcards.json",
        "data/questoes_catalog.json",
        "data/juris_bodies.json",
        "data/legis_known_meta.json",
        "js/offline-store.js",
    ]
    for rel in required:
        p = www / rel
        if p.exists() and p.stat().st_size > 0:
            shared.ok(f"www/{rel} empacotado")
        else:
            shared.fail(f"www/{rel} ausente ou vazio")
    cfg_text = (www / "js/config.js").read_text(encoding="utf-8")
    if "supabaseUrl" in cfg_text and "oauthCallbackUrl" in cfg_text:
        shared.ok("config.js com Supabase e OAuth")
    else:
        shared.fail("config.js incompleto")
    # assets copiados para plataformas
    for platform, base in (
        ("Android", MOBILE / "android/app/src/main/assets/public"),
        ("iOS", MOBILE / "ios/App/App/public"),
    ):
        if (base / "index.html").exists():
            shared.ok(f"assets {platform}: index.html sincronizado")
        else:
            shared.fail(f"assets {platform}: index.html não sincronizado")


def test_assetlinks(shared: Suite) -> None:
    local = json.loads((ROOT / "web/site-root/.well-known/assetlinks.json").read_text(encoding="utf-8"))
    fps = local[0]["target"].get("sha256_cert_fingerprints") or []
    if fps:
        shared.ok(f"assetlinks local: {len(fps)} fingerprint(s)")
    else:
        shared.fail("assetlinks local sem SHA-256")
    try:
        status, body = http_get("https://www.naintegracursos.com.br/.well-known/assetlinks.json")
        if status != 200:
            shared.fail(f"assetlinks produção HTTP {status}")
            return
        live = json.loads(body.decode("utf-8"))
        live_fps = live[0]["target"].get("sha256_cert_fingerprints") or []
        if live_fps:
            shared.ok(f"assetlinks produção: {len(live_fps)} fingerprint(s)")
        else:
            shared.fail("assetlinks produção sem SHA-256 (CDN pode demorar)")
        for fp in fps:
            if fp in live_fps:
                shared.ok(f"fingerprint publicado: {fp[:23]}…")
            else:
                shared.fail(f"fingerprint local ausente na produção: {fp[:23]}…")
    except (URLError, json.JSONDecodeError, KeyError, IndexError) as exc:
        shared.fail(f"assetlinks produção: {exc}")


def test_production_web(shared: Suite) -> None:
    pages = [
        f"{PROD_BASE}/",
        f"{PROD_BASE}/index.html",
        f"{PROD_BASE}/auth-callback.html",
        f"{PROD_BASE}/js/app.js",
        f"{PROD_BASE}/js/config.js",
        f"{PROD_BASE}/data/legis_known_meta.json",
        f"{PROD_BASE}/manifest.json",
    ]
    for url in pages:
        try:
            status, body = http_get(url)
            if status == 200 and len(body) > 0:
                shared.ok(f"HTTP 200 {url.replace(PROD_BASE, '') or '/'}")
            else:
                shared.fail(f"HTTP {status} vazio: {url}")
        except (HTTPError, URLError, TimeoutError) as exc:
            shared.fail(f"falha HTTP {url}: {exc}")

    try:
        status, html = http_get(f"{PROD_BASE}/")
        text = html.decode("utf-8", errors="replace")
        for needle in ("NaIntegra Lex", "sidebar-nav", "lei-seca", "flashcards"):
            if needle in text:
                shared.ok(f"HTML produção contém: {needle}")
            else:
                shared.fail(f"HTML produção sem: {needle}")
    except (HTTPError, URLError, TimeoutError) as exc:
        shared.fail(f"falha ao ler HTML produção: {exc}")


def test_supabase(shared: Suite) -> None:
    cfg_text = (MOBILE / "www/js/config.js").read_text(encoding="utf-8")
    m_url = re.search(r'supabaseUrl:\s*"([^"]+)"', cfg_text)
    m_key = re.search(r'supabaseAnonKey:\s*\n?\s*"([^"]+)"', cfg_text)
    if not m_url or not m_key:
        shared.fail("não foi possível extrair credenciais Supabase de config.js")
        return
    base = m_url.group(1).rstrip("/")
    key = m_key.group(1)
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    # REST health — lista mínima de norma_chunks
    rest_url = f"{base}/rest/v1/norma_chunks?select=id&limit=1"
    req = Request(rest_url, headers={**headers, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as resp:
            body = resp.read()
            if resp.status == 200:
                shared.ok("Supabase REST norma_chunks acessível")
            else:
                shared.fail(f"Supabase REST status {resp.status}")
            if body.strip().startswith(b"["):
                shared.ok("Supabase retornou JSON array")
            else:
                shared.fail("Supabase resposta inesperada")
    except URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" in str(exc):
            proc = subprocess.run(
                [
                    "curl",
                    "-sS",
                    "-H",
                    f"apikey: {key}",
                    "-H",
                    f"Authorization: Bearer {key}",
                    rest_url,
                ],
                capture_output=True,
                timeout=TIMEOUT,
            )
            if proc.returncode == 0 and proc.stdout.strip().startswith(b"["):
                shared.ok("Supabase REST norma_chunks acessível (via curl)")
                shared.ok("Supabase retornou JSON array")
            else:
                shared.fail(f"Supabase REST via curl falhou: {proc.stderr.decode()[:120]}")
        elif isinstance(exc, HTTPError) or (exc.args and getattr(exc.args[0], "code", None)):
            code = getattr(exc.args[0], "code", None) if exc.args else None
            if code in (401, 403):
                shared.fail(f"Supabase REST negado: HTTP {code}")
            else:
                shared.fail(f"Supabase REST erro: {exc}")
        else:
            shared.fail(f"Supabase REST indisponível: {exc}")


def java_available() -> bool:
    import shutil

    if not shutil.which("java"):
        return False
    try:
        proc = subprocess.run(["java", "-version"], capture_output=True, timeout=10)
        return proc.returncode == 0 and bool(proc.stderr or proc.stdout)
    except (subprocess.TimeoutExpired, OSError):
        return False


def test_runtime_environment(android: Suite, ios: Suite) -> None:
    if java_available():
        android.ok("Java disponível para build Gradle")
    else:
        android.skip("Java/JDK não instalado — build Android impossível nesta máquina")

    if (Path("/Applications/Android Studio.app")).exists():
        android.ok("Android Studio instalado")
    else:
        android.skip("Android Studio não instalado — abrir projeto manualmente após instalar")

    gradlew = MOBILE / "android/gradlew"
    if gradlew.exists() and java_available():
        try:
            out = subprocess.run(
                [str(gradlew), "tasks", "--quiet"],
                cwd=MOBILE / "android",
                capture_output=True,
                text=True,
                timeout=120,
            )
            if out.returncode == 0:
                android.ok("gradlew tasks executou com sucesso")
            else:
                android.fail(f"gradlew falhou: {out.stderr.strip()[:200]}")
        except subprocess.TimeoutExpired:
            android.fail("gradlew timeout")
    elif not java_available():
        android.skip("gradlew não testado (sem Java/JDK)")

    if (Path("/Applications/Xcode.app")).exists():
        ios.ok("Xcode instalado")
    else:
        ios.fail("Xcode ausente")
        return

    try:
        out = subprocess.run(
            ["xcodebuild", "-version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out.returncode == 0 and "Xcode" in out.stdout:
            ios.ok(f"Xcode CLI: {out.stdout.strip().splitlines()[0]}")
        else:
            ios.fail("xcodebuild indisponível")
    except subprocess.TimeoutExpired:
        ios.fail("xcodebuild timeout")

    try:
        out = subprocess.run(
            [
                "xcodebuild",
                "-workspace",
                str(MOBILE / "ios/App/App.xcworkspace"),
                "-scheme",
                "App",
                "-showdestinations",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        combined = out.stdout + out.stderr
        if "iOS 26.5 is not installed" in combined or "CoreSimulator is out of date" in combined:
            ios.skip("Simulador iOS indisponível — instale iOS 26.5 em Xcode → Settings → Components")
        elif "platform:iOS Simulator" in combined:
            ios.ok("destino Simulador iOS disponível")
        elif "Ineligible destinations" in combined:
            ios.skip("nenhum destino iOS elegível — instale runtime iOS no Xcode")
        else:
            ios.ok("xcodebuild -showdestinations executou")
    except subprocess.TimeoutExpired:
        ios.skip("xcodebuild destinations timeout")


def print_suite(suite: Suite) -> None:
    print(f"\n=== {suite.name} ===")
    for msg in suite.passed:
        print(f"  ✓ {msg}")
    for msg in suite.skipped:
        print(f"  ○ {msg}")
    for msg in suite.failed:
        print(f"  ✗ {msg}")
    total = len(suite.passed) + len(suite.failed) + len(suite.skipped)
    print(f"  → {len(suite.passed)} ok, {len(suite.failed)} falha, {len(suite.skipped)} skip ({total} checks)")


def main() -> int:
    android = Suite("Android")
    ios = Suite("iOS")
    shared = Suite("Funcionalidades compartilhadas (web remota + assets)")

    print("NaIntegra Lex — smoke test mobile\n")
    test_project_structure(android, ios, shared)
    test_capacitor_config(shared)
    test_android_manifest(android)
    test_ios_config(ios)
    test_bundled_www(shared)
    test_assetlinks(shared)
    test_production_web(shared)
    test_supabase(shared)
    test_runtime_environment(android, ios)

    print_suite(android)
    print_suite(ios)
    print_suite(shared)

    failed = len(android.failed) + len(ios.failed) + len(shared.failed)
    skipped = len(android.skipped) + len(ios.skipped) + len(shared.skipped)
    print(f"\n{'=' * 50}")
    if failed:
        print(f"RESULTADO: {failed} falha(s), {skipped} skip(s)")
        return 1
    print(f"RESULTADO: todos os testes executáveis passaram ({skipped} skip(s) de ambiente)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
