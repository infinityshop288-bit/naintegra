from __future__ import annotations

import argparse
import logging

from naintegra_lex_agent.provas_juridicas.codex_client import DEFAULT_MODEL

from .loop import run_loop


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(
        description=(
            "Varre e atualiza legislação (Planalto/LEXML), jurisprudência e doutrina "
            "com a Responses API do Codex Ilimitado."
        )
    )
    p.add_argument("--loop", action="store_true", default=True)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--idle-seconds", type=float, default=30.0)
    p.add_argument("--planalto-per-cycle", type=int, default=8)
    args = p.parse_args()
    run_loop(
        model=args.model,
        idle_seconds=args.idle_seconds,
        planalto_per_cycle=args.planalto_per_cycle,
    )


if __name__ == "__main__":
    main()
