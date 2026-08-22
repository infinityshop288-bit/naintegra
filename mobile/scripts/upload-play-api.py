#!/usr/bin/env python3
"""Upload NaIntegra Lex para Google Play (teste interno) via Android Publisher API."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MOBILE = ROOT / "mobile"
ASSETS = MOBILE / "store-assets" / "generated"
SHOTS = ASSETS / "phone"
AAB = MOBILE / "dist" / "naintegra-lex-release.aab"
PACKAGE = "br.com.naintegracursos.lex"
LANG = "pt-BR"
SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]

STORE = {
    "title": "NaIntegra Lex",
    "shortDescription": "Lei seca, súmulas, flashcards e questões para concursos públicos.",
    "fullDescription": (
        "Você se prepara para concurso público — fiscal, tribunais, jurídico, administrativo, MP, "
        "Defensoria ou carreiras policiais? O NaIntegra Lex reúne legislação, jurisprudência, "
        "flashcards e questões em um só lugar, com material atualizado semanalmente.\n\n"
        "Ideal para estudar durante o deslocamento no transporte público — ônibus, metrô, trem ou van.\n\n"
        "• Lei seca — leitura artigo por artigo, com progresso e busca por tema\n"
        "• Jurisprudência — súmulas, temas e julgados dos principais tribunais\n"
        "• Flashcards — revisão espaçada\n"
        "• Questões — banco integrado ao NaIntegra Cursos\n"
        "• Ouvir — narração por voz dos dispositivos legais (ideal no transporte público)\n"
        "• Anotações e grifos — salvas na sua conta\n"
        "• Conteúdo atualizado toda semana\n\n"
        "Requer assinatura NaIntegra Lex para acesso ao acervo completo.\n\n"
        "Desenvolvido por NaIntegra Cursos."
    ),
}


def ensure_deps() -> None:
    try:
        from google.oauth2 import service_account  # noqa: F401
        from googleapiclient.discovery import build  # noqa: F401
        from googleapiclient.http import MediaFileUpload  # noqa: F401
    except ImportError:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "google-api-python-client", "google-auth", "-q"],
            check=True,
        )


def find_service_account(explicit: str | None) -> Path:
    candidates = [
        Path(explicit) if explicit else None,
        Path(os.environ.get("PLAY_SERVICE_ACCOUNT_JSON", "")) if os.environ.get("PLAY_SERVICE_ACCOUNT_JSON") else None,
        MOBILE / "android" / "play-service-account.json",
        MOBILE / "play-service-account.json",
        ROOT / "play-service-account.json",
    ]
    for c in candidates:
        if c and c.is_file():
            return c
    raise FileNotFoundError(
        "Service account JSON não encontrado.\n"
        "1. Play Console → Configuração → Acesso à API → Criar conta de serviço\n"
        "2. Conceda permissão 'Admin' (ou Release) à conta\n"
        "3. Baixe a chave JSON para mobile/android/play-service-account.json\n"
        "4. Rode novamente este script"
    )


def get_service(creds_path: Path):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
    return build("androidpublisher", "v3", credentials=creds, cache_discovery=False)


def upload_images(service, package: str, edit_id: str) -> None:
    from googleapiclient.http import MediaFileUpload

    mapping = [
        ("icon", ASSETS / "icon-512-play-store.png"),
        ("featureGraphic", ASSETS / "feature-graphic-1024x500.png"),
    ]
    for image_type, path in mapping:
        if not path.exists():
            print(f"  skip {image_type}: {path.name} ausente")
            continue
        service.edits().images().upload(
            packageName=package,
            editId=edit_id,
            language=LANG,
            imageType=image_type,
            media_body=MediaFileUpload(str(path), mimetype="image/png"),
        ).execute()
        print(f"  imagem: {image_type}")

    for shot in sorted(SHOTS.glob("screenshot-*.png"))[:8]:
        service.edits().images().upload(
            packageName=package,
            editId=edit_id,
            language=LANG,
            imageType="phoneScreenshots",
            media_body=MediaFileUpload(str(shot), mimetype="image/png"),
        ).execute()
        print(f"  captura: {shot.name}")


def fetch_play_sha256(service, package: str) -> str | None:
    """Tenta obter SHA-256 do certificado de assinatura do app (Play App Signing)."""
    import re

    try:
        # Endpoint disponível após Play App Signing ativo
        resp = (
            service.applications()
            .getAppSigningInfo(packageName=package)
            .execute()
        )
        for cert in resp.get("signingCertificates", []):
            fp = cert.get("certificateSha256Hash") or cert.get("sha256")
            if fp:
                raw = re.sub(r"[^0-9a-fA-F]", "", fp)
                return ":".join(raw[i : i + 2].upper() for i in range(0, 64, 2))
    except Exception as exc:
        print(f"  SHA-256 via API indisponível ainda ({exc})")
    return None


def apply_sha256(sha: str) -> None:
    subprocess.run(
        ["bash", str(MOBILE / "scripts" / "add-play-sha256.sh"), sha],
        check=True,
        cwd=str(ROOT),
    )


def main() -> int:
    import os

    parser = argparse.ArgumentParser(description="Upload Play Store (teste interno) via API")
    parser.add_argument("--service-account", help="Caminho do JSON da service account")
    parser.add_argument("--track", default="internal", choices=["internal", "alpha", "beta", "production"])
    parser.add_argument("--countries", default="BR", help="Países ISO (ex: BR ou BR,PT)")
    parser.add_argument("--testers", default="", help="E-mails testadores (vírgula)")
    parser.add_argument("--skip-listing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ensure_deps()
    if not AAB.exists():
        subprocess.run(["bash", str(MOBILE / "scripts" / "build-release-aab.sh")], check=True)
    if not SHOTS.exists() or not list(SHOTS.glob("screenshot-*.png")):
        subprocess.run([sys.executable, str(MOBILE / "scripts" / "export-play-screenshots.py"), "--device", "phone"], check=True)
    subprocess.run([sys.executable, str(MOBILE / "scripts" / "generate-store-assets.py")], check=True)

    creds_path = find_service_account(args.service_account)
    print(f"Service account: {creds_path}")

    if args.dry_run:
        print("Dry-run OK — credenciais e AAB encontrados.")
        return 0

    from googleapiclient.http import MediaFileUpload

    service = get_service(creds_path)
    package = PACKAGE

    print("\n==> Passo 2: Ficha da loja (API)")
    edit = service.edits().insert(packageName=package, body={}).execute()
    edit_id = edit["id"]
    print(f"  edit_id: {edit_id}")

    if not args.skip_listing:
        service.edits().listings().update(
            packageName=package,
            editId=edit_id,
            language=LANG,
            body={
                "title": STORE["title"],
                "shortDescription": STORE["shortDescription"],
                "fullDescription": STORE["fullDescription"],
            },
        ).execute()
        print("  textos pt-BR")
        upload_images(service, package, edit_id)

    print("\n==> Passo 3: Upload AAB →", args.track)
    bundle = (
        service.edits()
        .bundles()
        .upload(
            packageName=package,
            editId=edit_id,
            media_body=MediaFileUpload(str(AAB), mimetype="application/octet-stream", resumable=True),
        )
        .execute()
    )
    version_code = int(bundle["versionCode"])
    print(f"  versionCode: {version_code}")

    countries = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
    track_body: dict = {
        "releases": [
            {
                "versionCodes": [str(version_code)],
                "status": "completed",
            }
        ],
    }
    if countries and args.track in ("alpha", "beta", "production"):
        track_body["countryTargeting"] = {
            "countries": countries,
            "includeRestOfWorld": False,
        }
        print(f"  países: {', '.join(countries)}")

    service.edits().tracks().update(
        packageName=package,
        editId=edit_id,
        track=args.track,
        body=track_body,
    ).execute()
    print(f"  track: {args.track}")

    tester_emails = [
        e.strip()
        for e in (args.testers or os.environ.get("PLAY_TESTER_EMAILS", "")).split(",")
        if e.strip() and "@" in e
    ]
    if tester_emails and args.track in ("internal", "alpha"):
        service.edits().testers().update(
            packageName=package,
            editId=edit_id,
            track=args.track,
            body={"googleGroups": [], "licenseTesters": tester_emails},
        ).execute()
        print(f"  testadores: {', '.join(tester_emails)}")

    service.edits().commit(packageName=package, editId=edit_id).execute()
    print("  commit OK — versão publicada no trilho", args.track)

    print("\n==> Passo 4: assetlinks (SHA Play App Signing)")
    time.sleep(5)
    sha = fetch_play_sha256(service, package)
    if sha:
        apply_sha256(sha)
        print("  assetlinks atualizado e sync iniciado.")
    else:
        print(
            "  Copie o SHA-256 em Play Console → Integridade do app → Certificado de assinatura do app\n"
            "  Depois rode: bash mobile/scripts/add-play-sha256.sh \"SHA256\""
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
