"""Export público do pacote ``exam_scrape``."""

from .targets import EXAM_BOARDS, EXAM_CARGOS, OFFICIAL_BANK_HOME
from .url_plan import ExamScrapeNav, build_full_plan, slice_plan

__all__ = [
    "EXAM_BOARDS",
    "EXAM_CARGOS",
    "OFFICIAL_BANK_HOME",
    "ExamScrapeNav",
    "build_full_plan",
    "slice_plan",
]
