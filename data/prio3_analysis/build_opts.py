"""Baixa o COTAHIST anual da B3 e filtra as series de OPCOES de cada root do
universo para /tmp/opts_<ROOT>.txt (insumo do multi_options.py).

Assim, todo o pipeline de opcoes cobre TODOS os segmentos automaticamente: basta
adicionar o ticker em universe.py que suas opcoes passam a ser extraidas aqui.

- Fonte: https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A<ANO>.ZIP
- Mantem so os registros de mercado de opcoes (TPMERC 070=CALL / 080=PUT) cujo
  codigo de negociacao comeca pelo root da opcao (ex.: PRIO, WEGE, CYRE...).
- O ZIP fica em cache em /tmp e so e rebaixado se ausente ou desatualizado.

Uso:  python build_opts.py            -> ano corrente, todos os roots do universo
      python build_opts.py 2025       -> outro ano
"""
from __future__ import annotations

import io
import ssl
import sys
import time
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

from universe import UNIVERSE

try:  # usa certificados do certifi; senao, contexto sem verificacao (como no live_server)
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    _SSL = ssl._create_unverified_context()

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else date.today().year
URL = f"https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{YEAR}.ZIP"
ZIP_PATH = Path(f"/tmp/COTAHIST_A{YEAR}.ZIP")
MAX_AGE_H = 12  # rebaixa se o cache tiver mais que isso
UA = "Mozilla/5.0 (research; prio3-analysis)"

# TPMERC de opcoes no COTAHIST
OPT_MKT = {"070", "080"}


def download() -> None:
    fresh = (ZIP_PATH.exists()
             and ZIP_PATH.stat().st_size > 1_000_000
             and (time.time() - ZIP_PATH.stat().st_mtime) < MAX_AGE_H * 3600)
    if fresh:
        print(f"cache OK: {ZIP_PATH} ({ZIP_PATH.stat().st_size/1e6:.0f} MB)")
        return
    print(f"baixando {URL} ...")
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120, context=_SSL) as r, ZIP_PATH.open("wb") as fh:
        total = int(r.headers.get("Content-Length") or 0)
        got = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            got += len(chunk)
            if total:
                print(f"\r  {got/1e6:6.1f}/{total/1e6:.1f} MB", end="", flush=True)
    print(f"\n  salvo {ZIP_PATH} ({ZIP_PATH.stat().st_size/1e6:.0f} MB)")


def filter_roots() -> dict:
    roots = sorted({root for _, (_, _, root) in UNIVERSE.items()})
    buffers: dict[str, list[bytes]] = {rt: [] for rt in roots}
    # index por primeiro caractere p/ reduzir comparacoes
    by_first: dict[str, list[str]] = {}
    for rt in roots:
        by_first.setdefault(rt[0], []).append(rt)

    n_lines = n_opt = 0
    with zipfile.ZipFile(ZIP_PATH) as z:
        member = next(m for m in z.namelist() if m.upper().endswith(".TXT"))
        with z.open(member) as fh:
            for raw in io.BufferedReader(fh, buffer_size=1 << 20):
                if len(raw) < 210:
                    continue
                n_lines += 1
                if raw[24:27].decode("latin-1") not in OPT_MKT:
                    continue
                cod = raw[12:24].decode("latin-1").strip()
                cands = by_first.get(cod[:1])
                if not cands:
                    continue
                for rt in cands:
                    if cod.startswith(rt):
                        buffers[rt].append(raw)
                        n_opt += 1
                        break

    counts = {}
    for rt in roots:
        out = Path(f"/tmp/opts_{rt}.txt")
        with out.open("wb") as fh:
            fh.writelines(buffers[rt])
        counts[rt] = len(buffers[rt])
    print(f"\nlinhas lidas: {n_lines:,} | registros de opcao gravados: {n_opt:,}")
    return counts


def main() -> None:
    download()
    counts = filter_roots()
    print("\nregistros de opcao por root (ativo):")
    tick_by_root = {root: t for t, (_, _, root) in UNIVERSE.items()}
    for rt, n in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
        flag = "" if n else "  <-- SEM OPCOES (verificar root)"
        print(f"  {tick_by_root.get(rt, '?'):<7} {rt:<6} {n:>8,}{flag}")


if __name__ == "__main__":
    main()
