"""Planejamento de URLs por banca × cargo × fonte."""

from __future__ import annotations

from dataclasses import dataclass

from .targets import (
    EXAM_BOARDS,
    EXAM_CARGOS,
    OFFICIAL_BANK_HOME,
    qconcurso_search_url,
    techconcursos_search_url,
)


@dataclass(frozen=True)
class ExamScrapeNav:
    url: str
    tags: dict[str, str]


def build_full_plan(*, include_official: bool, sources: tuple[str, ...]) -> list[ExamScrapeNav]:
    """Fontes: ``qconcurso``, ``techconcursos``, ``official``."""

    plan: list[ExamScrapeNav] = []
    src_norm = {s.strip().lower() for s in sources if s.strip()}

    for board in EXAM_BOARDS:
        for cargo in EXAM_CARGOS:
            if "qconcurso" in src_norm:
                plan.append(
                    ExamScrapeNav(
                        url=qconcurso_search_url(board, cargo),
                        tags={
                            "banca": board,
                            "cargo": cargo,
                            "cargo_alvo": cargo,
                            "fonte": "qconcursos.com",
                            "tipo_fonte": "agregador",
                        },
                    )
                )
            if "techconcursos" in src_norm:
                plan.append(
                    ExamScrapeNav(
                        url=techconcursos_search_url(board, cargo),
                        tags={
                            "banca": board,
                            "cargo": cargo,
                            "cargo_alvo": cargo,
                            "fonte": "tecconcursos.com.br",
                            "tipo_fonte": "agregador",
                        },
                    )
                )

    if include_official and "official" in src_norm:
        for board, home in OFFICIAL_BANK_HOME.items():
            for cargo in EXAM_CARGOS:
                plan.append(
                    ExamScrapeNav(
                        url=home,
                        tags={
                            "banca": board,
                            "cargo": cargo,
                            "cargo_alvo": cargo,
                            "fonte": f"oficial_{board.lower()}",
                            "tipo_fonte": "portal_oficial",
                        },
                    )
                )

    return plan


def slice_plan(plan: list[ExamScrapeNav], *, offset: int, limit: int) -> list[ExamScrapeNav]:
    if not plan or limit <= 0:
        return []
    n = len(plan)
    start = offset % n
    out: list[ExamScrapeNav] = []
    for i in range(limit):
        out.append(plan[(start + i) % n])
    return out
