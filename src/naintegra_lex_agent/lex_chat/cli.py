from __future__ import annotations

import argparse
import logging

from .server import PORT, serve


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Servidor do chat Lex (pesquisa, documentos e skills).")
    p.add_argument("--port", type=int, default=PORT)
    args = p.parse_args()
    serve(args.port)


if __name__ == "__main__":
    main()
