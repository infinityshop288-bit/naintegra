"""Configuração do fluxo Concursos × estudo por IA (variáveis próprias, .env opcional)."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class QConcursoStudySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="QC_STUDY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    #: JSON/JSONL depositados pelo crawl ou export manual (site alvo típico: qconcursos.com).
    qconcurso_inbox_path: Path = Field(default=Path("./data/qconcurso/inbox"))
    qconcurso_glob: str = Field(default="*.jsonl")

    consolidated_path: Path = Field(default=Path("./data/qconcurso/wrong_consolidated.jsonl"))
    studies_dir: Path = Field(default=Path("./data/qconcurso/studies"))
    review_html_path: Path = Field(default=Path("./data/qconcurso/revisao_erradas.html"))

    #: Base do site para Playwright (start-url padrão).
    qconcurso_base_url: str = Field(default="https://www.qconcursos.com/")
    #: Estado gravado com subcomando playwright-save-state (cookies/sessão).
    playwright_storage_state_path: Path = Field(default=Path(".qc_study/playwright-qconcurso.json"))

    ai_provider: Literal["anthropic", "openai", "openai_compatible", "ollama"] = "anthropic"

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    #: Base URL estilo OpenAI: Ollama ``http://127.0.0.1:11434/v1``, LM Studio ``http://localhost:1234/v1``.
    openai_compatible_base_url: str | None = Field(default=None)
    #: Opcional (Ollama aceita Bearer fictício, ex.: ``ollama``).
    openai_compatible_api_key: str | None = Field(default=None)
    ai_model: str = ""
    ai_timeout_seconds: float = 120.0
    ai_max_input_chars: int = 16000
    ai_calls_delay_seconds: float = 0.5

    studies_cache_sqlite: Path = Field(default=Path(".qc_study/ai_cache.sqlite"))

    #: Máximo de novas chamadas IA por execução (proteção de custo).
    study_max_batches: int = 200

    #: exam_prep = prompt atual (sem citações legislativas extensas). cited_solution = solução com lei e jurisprudência.
    study_prompt_profile: Literal["exam_prep", "cited_solution"] = Field(default="exam_prep")

    def resolved_openai_compatible_base_url(self) -> str | None:
        raw = (self.openai_compatible_base_url or "").strip()
        if self.ai_provider == "ollama":
            return raw or "http://127.0.0.1:11434/v1"
        if self.ai_provider == "openai_compatible":
            return raw or None
        return None


def load_qc_study_settings() -> QConcursoStudySettings:
    return QConcursoStudySettings()
