"""Varredura de provas de juiz, promotor, defensor e procurador de Estado."""

from .careers import PROVA_CAREERS, PROVA_YEARS, career_tags
from .loop import run_loop
from .scan import run

__all__ = ["PROVA_CAREERS", "PROVA_YEARS", "career_tags", "run", "run_loop"]
