#!/usr/bin/env python3
"""Monta o bundle estático do dashboard PRIO3 para publicação em /xxx/."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "data" / "prio3_analysis"
DEFAULT_OUT = REPO / "xxx"

JSON_FILES = (
    "macro.json",
    "multi_analysis.json",
    "multi_options.json",
    "fundamentals_multi.json",
    "fatos_relevantes_multi.json",
    "oil_routes.json",
    "oil_peers_compare.json",
    "radar.json",
    "ai_patterns.json",
    "analysis.json",
    "technical.json",
    "fundamentals.json",
    "fair_value.json",
    "intraday_volume.json",
    "b3_options.json",
    "b3_options_brav.json",
    "brav_analysis.json",
    "triggers.json",
    "triggers_put.json",
    "stats_prices.json",
    "operational_series.json",
)

HTML_FILES = ("painel.html", "mercado.html", "fiis.html", "opcoes.html", "radar.html", "patterns.html")
SKIP_NAMES = {".DS_Store", ".venv", "__pycache__"}


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def htpasswd_line(user: str, password: str) -> str:
    import shutil

    if shutil.which("htpasswd"):
        out = subprocess.check_output(
            ["htpasswd", "-nbB", user, password], text=True, stderr=subprocess.DEVNULL
        ).strip()
        return out + "\n"
    out = subprocess.check_output(
        ["openssl", "passwd", "-apr1", password], text=True, stderr=subprocess.DEVNULL
    ).strip()
    return f"{user}:{out}\n"


def write_htaccess(out: Path, cfg: dict[str, str]) -> None:
    abs_pw = cfg.get("HTPASSWD_ABS_PATH", "").strip()
    if not abs_pw:
        # Mesmo diretório do .htaccess (public/xxx/ no Hostinger)
        abs_pw = ".htpasswd"
    tpl = f"""# NaIntegra — dashboard protegido (Hostinger / Apache)
<IfModule mod_auth_basic.c>
  AuthType Basic
  AuthName "NaIntegra Dashboard"
  AuthUserFile "{abs_pw}"
  Require valid-user
</IfModule>

DirectoryIndex painel.html index.html

<IfModule mod_headers.c>
  Header set Cache-Control "no-store, no-cache, must-revalidate"
</IfModule>
"""
    (out / ".htaccess").write_text(tpl, encoding="utf-8")


def write_index(out: Path) -> None:
    (out / "index.html").write_text(
        """<!DOCTYPE html>
<html lang="pt-BR"><head>
<meta charset="UTF-8" />
<meta http-equiv="refresh" content="0;url=painel.html" />
<title>NaIntegra Dashboard</title>
</head><body><p><a href="painel.html">Painel PRIO3</a></p></body></html>
""",
        encoding="utf-8",
    )


def run_refresh() -> None:
    py = SRC / ".venv" / "bin" / "python"
    if not py.is_file():
        py = Path(sys.executable)
    subprocess.run(["bash", str(SRC / "refresh_market.sh")], check=True, cwd=SRC)
    subprocess.run([str(py), str(REPO / "scripts" / "export_prio3_snapshots.py")], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build bundle /xxx/ do dashboard PRIO3")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Pasta de saída (default: xxx/)")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Atualiza macro/análise/opções e exporta snapshots de API antes do build",
    )
    parser.add_argument(
        "--skip-snapshots",
        action="store_true",
        help="Não regenera api/*.json (usa os já existentes em data/prio3_analysis/api/)",
    )
    args = parser.parse_args()

    out = Path(args.out).expanduser().resolve()
    cfg = load_env(REPO / ".env.deploy")
    for key in ("DASHBOARD_USER", "DASHBOARD_PASSWORD", "HTPASSWD_ABS_PATH"):
        if os.environ.get(key):
            cfg[key] = os.environ[key]

    if args.refresh:
        print("Atualizando dados de mercado + snapshots...", flush=True)
        run_refresh()
    elif not args.skip_snapshots:
        py = SRC / ".venv" / "bin" / "python"
        if not py.is_file():
            py = Path(sys.executable)
        print("Exportando snapshots de API...", flush=True)
        subprocess.run([str(py), str(REPO / "scripts" / "export_prio3_snapshots.py")], check=True)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    for html in HTML_FILES:
        shutil.copy2(SRC / html, out / html)
    shutil.copy2(SRC / "dash-api.js", out / "dash-api.js")

    for name in JSON_FILES:
        src = SRC / name
        if src.is_file():
            shutil.copy2(src, out / name)

    api_src = SRC / "api"
    if api_src.is_dir():
        shutil.copytree(api_src, out / "api")

    write_index(out)
    write_htaccess(out, cfg)

    user = cfg.get("DASHBOARD_USER", "infinity.shop288@gmail.com")
    password = cfg.get("DASHBOARD_PASSWORD", "").strip()
    if password:
        (out / ".htpasswd").write_text(htpasswd_line(user, password), encoding="utf-8")
        print(f"Autenticação: usuário {user!r} (.htpasswd gerado)", flush=True)
    else:
        print(
            "AVISO: DASHBOARD_PASSWORD não definido — .htpasswd não gerado.\n"
            "  Defina em .env.deploy antes do deploy para exigir login.",
            flush=True,
        )

    n = sum(1 for _ in out.rglob("*") if _.is_file())
    print(f"\n[OK] Bundle em {out} ({n} arquivos)", flush=True)
    print("URL: https://www.naintegracursos.com.br/xxx/painel.html", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
