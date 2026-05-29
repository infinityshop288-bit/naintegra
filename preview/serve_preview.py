#!/usr/bin/env python3
"""Serve o repositório pela raiz para os previews poderem usar fetch() em data/ e preview/."""

from __future__ import annotations

import argparse
import os
import socketserver
import sys
import webbrowser
from http.server import SimpleHTTPRequestHandler
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    os.chdir(repo_root)

    p = argparse.ArgumentParser(description="HTTP estático na raiz do naintegra (previews Lex).")
    p.add_argument("--port", "-p", type=int, default=8765, help="Porta inicial (default 8765)")
    p.add_argument("--bind", default="127.0.0.1", help="Host (default 127.0.0.1)")
    p.add_argument(
        "--all-interfaces",
        action="store_true",
        help="Escuta em 0.0.0.0 (útil em VM/WSL; depois use http://IP:porta/).",
    )
    p.add_argument(
        "--open",
        choices=("hub", "lex", "none"),
        default="lex",
        help="Abre o navegador ao iniciar (default: lex). Use none para não abrir.",
    )
    args = p.parse_args()

    bind = "0.0.0.0" if args.all_interfaces else args.bind

    handler = SimpleHTTPRequestHandler

    class QuietHandler(handler):  # type: ignore[misc, valid-type]
        def log_message(self, fmt: str, *args_: object) -> None:
            if "/favicon" in str(args_):
                return
            super().log_message(fmt, *args_)

        def end_headers(self) -> None:
            path = self.path.split("?", 1)[0]
            if path.startswith(("/web/", "/preview/")) or path.endswith(
                (".html", ".js", ".css", ".json")
            ):
                self.send_header("Cache-Control", "no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
            super().end_headers()

    socketserver.TCPServer.allow_reuse_address = True

    ports = list(range(args.port, args.port + 15))
    httpd: socketserver.TCPServer | None = None
    chosen: int | None = None
    last_err: OSError | None = None
    for candidate in ports:
        try:
            httpd = socketserver.TCPServer((bind, candidate), QuietHandler)
            chosen = candidate
            break
        except OSError as e:
            last_err = e
            continue

    if httpd is None or chosen is None:
        print(f"Erro: nenhuma porta livre entre {ports[0]} e {ports[-1]} ({last_err}).", file=sys.stderr)
        sys.exit(1)

    display_host = "127.0.0.1" if bind in ("127.0.0.1", "0.0.0.0") else bind
    base = f"http://{display_host}:{chosen}"
    urls = {
        "hub": f"{base}/preview/index.html",
        "lex": f"{base}/web/lex/index.html",
    }

    port_file = repo_root / "preview" / ".server-url"
    port_file.write_text(f"{base}\n{urls['lex']}\n", encoding="utf-8")

    print(f"Diretório: {repo_root}")
    print(f"Servidor:  {bind}:{chosen}")
    if chosen != args.port:
        print(f"  (porta {args.port} ocupada — usando {chosen})")
    print()
    print("Abra no navegador:")
    print(f"  · Lex app:  {urls['lex']}")
    print(f"  · Plano:    {urls['lex']}#/plano-estudos")
    print(f"  · Demo:     {urls['lex']}?promo=1")
    print(f"  · Hub:      {urls['hub']}")
    print(f"  · Raiz:     {base}/")
    if bind == "0.0.0.0":
        print("  (modo rede: use o IP desta máquina no lugar de 127.0.0.1)")
    print()
    print("Ctrl+C para encerrar.")

    if args.open != "none":
        webbrowser.open(urls[args.open])

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")


if __name__ == "__main__":
    main()
