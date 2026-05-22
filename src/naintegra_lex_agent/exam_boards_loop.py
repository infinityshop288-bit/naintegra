"""Loop só de scraping banca×cargo (salva em ``data/exam_scrape/inbox`` para organizar depois).

Agregadores **QConcurso** e **TecConcursos** costumam expor JSON na rede; o adaptador reconhece vários
formatos (incl. alternativas em chaves ``alternativa_*``, gabarito numérico, ``texto`` como enunciado).
Cada resposta HTTP etiqueta ``source_system`` pelo domínio da própria API.

Portais oficiais: ``LEX_AGENT_EXAM_SCRAPE_INCLUDE_OFFICIAL=true`` (homes em ``exam_scrape/targets.py``);
rendimento típico menor sem URLs de busca específicas.

Depois rode ``naintegra-questions-loop`` ou ``naintegra-organize-loop`` para fundir e normalizar.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading

from .exam_scrape.runner import run_exam_board_scrape_batch
from .settings import load_settings

logger = logging.getLogger("naintegra_lex_agent.exam_boards_loop")


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )


def main_sync() -> None:
    settings = load_settings()
    _configure_logging(settings.log_level)

    stop = threading.Event()

    def _stop(*_: object) -> None:
        logger.info("Encerrando exam-boards-loop (sinal)...")
        stop.set()

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    cycles = 0
    if settings.scrape_harvest_emit_mode != "all_with_gabarito":
        logger.warning(
            "LEX_AGENT_SCRAPE_HARVEST_EMIT_MODE=%s — para capturar gabaritos use all_with_gabarito.",
            settings.scrape_harvest_emit_mode,
        )
    logger.info(
        "exam-boards-loop — inbox=%s fontes=%s pares/ciclo=%s seg/URL=%s oficial=%s",
        settings.exam_scrape_inbox_path,
        settings.exam_scrape_sources,
        settings.exam_scrape_pairs_per_cycle,
        settings.exam_scrape_seconds_per_url,
        settings.exam_scrape_include_official,
    )

    while not stop.is_set():
        cycles += 1
        try:
            code, n = run_exam_board_scrape_batch(settings)
            logger.info("exam-boards ciclo %s — exit=%s registros=%s", cycles, code, n)
            if code != 0:
                logger.warning("Harvest retornou código %s (sessão/login/tempo?)", code)
        except Exception:
            logger.exception("exam-boards ciclo %s falhou", cycles)

        if stop.wait(timeout=float(settings.exam_boards_loop_interval_seconds)):
            break

    logger.info("exam-boards-loop encerrado (%s ciclos)", cycles)
    sys.exit(0)


def main() -> None:
    main_sync()


if __name__ == "__main__":
    main_sync()
