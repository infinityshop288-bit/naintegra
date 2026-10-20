from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .codex_client import DEFAULT_MODEL
from .loop import run_loop
from .scan import DEFAULT_OUT, DEFAULT_SRC, run
from .status import DEFAULT_STATUS


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(
        description=(
            "Varre questões objetivas e subjetivas de juiz, promotor, defensor e "
            "procurador de Estado (últimos 2 anos), cita o dispositivo integral "
            "e a jurisprudência do acervo e elabora a resposta da IA "
            "(Responses API em api.codexilimitado.com)."
        )
    )
    p.add_argument("--src", type=Path, default=DEFAULT_SRC)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument(
        "--ai",
        action="store_true",
        help="Elabora respostas via POST /v1/responses (Codex Ilimitado).",
    )
    p.add_argument("--ai-limit", type=int, default=80)
    p.add_argument("--ai-subjetivas", action="store_true", help="Só chama a IA nas discursivas.")
    p.add_argument("--model", default=DEFAULT_MODEL, help="gpt-5.6-sol | gpt-6-astra | gpt-6-sol | gpt-6-luna")
    p.add_argument("--resume", action="store_true", help="Atualiza o catálogo existente sem recomeçar a varredura.")
    p.add_argument("--save-every", type=int, default=1, help="Grava o JSON a cada N respostas de IA.")
    p.add_argument("--loop", action="store_true", help="Loop infinito: varre, elabora e espera novas questões.")
    p.add_argument("--idle-seconds", type=float, default=20.0)
    p.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    args = p.parse_args()
    if args.loop:
        run_loop(
            src=args.src,
            dest=args.out,
            status_path=args.status,
            model=args.model,
            idle_seconds=args.idle_seconds,
        )
        return
    run(
        src=args.src,
        dest=args.out,
        use_ai=args.ai,
        ai_limit=args.ai_limit,
        model=args.model,
        ai_only_subjetivas=args.ai_subjetivas,
        resume=args.resume,
        save_every=args.save_every,
    )


if __name__ == "__main__":
    main()
