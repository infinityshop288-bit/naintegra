from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LEX_AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    crawl_inbox_path: Path = Field(
        default=Path("./data/crawl_inbox"),
        description="Diretório onde o naintegra-crawl deposita JSON/JSONL.",
    )
    crawl_glob: str = "*.jsonl"
    also_scan_json: bool = True

    poll_interval_seconds: int = 300
    max_records_per_cycle: int = 500
    batch_size: int = 50

    dry_run: bool = False
    run_once: bool = False

    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    lex_schema: str = "lex"
    lex_table: str = "ingested_documents"

    state_db_path: Path = Field(default=Path(".lex_agent/state.sqlite"))

    log_level: str = "INFO"

    # Pastas separadas: material bruto imutável vs. análise derivada
    raw_preserved_path: Path = Field(
        default=Path("./data/raw_preserved"),
        description="Cópias byte-a-byte dos arquivos coletados (o agente não escreve na inbox).",
    )
    organized_output_path: Path = Field(
        default=Path("./data/organized"),
        description="Somente organização/classificação e metadados derivados.",
    )
    preserve_inbox_files: bool = True
    write_organized_manifest: bool = True

    #: Fundir examples/crawl e raw_preserved (etc.) no corpus antes de cada ciclo.
    material_merge_before_cycle: bool = Field(default=False)
    #: Lista separada por vírgula de diretórios com JSONL adicionais para a fusão.
    material_merge_extra_roots: str = Field(default="examples/crawl,data/raw_preserved")
    corpus_output_name: str = Field(default="corpus.jsonl")

    #: Pasta do pipeline Trilhante Informativo (jurisprudência, súmulas, legislação em JSONL); acrescentada à fusão automaticamente.
    trilhante_informativo_root: Path | None = Field(
        default=None,
        description="Ex.: output_trilhante_informativo — todos os **/*.jsonl são fundidos no corpus antes do ciclo.",
    )
    #: Se true, upsert Supabase ignora dedupe local (.lex_agent/state) e reenvia todos os registros do ciclo.
    publish_ignore_state: bool = Field(default=False)

    #: Subpasta fixa em organized/ (ex.: latest). Vazio → timestamp UTC por ciclo.
    organized_batch_id: str | None = Field(default=None)
    #: Após o ciclo, copiar manifest para o preview HTML (loop / integração local).
    sync_preview_manifest: bool = Field(default=False)
    preview_manifest_path: Path = Field(default=Path("./preview/demo-manifest.jsonl"))

    #: Histórico por ciclo (organize/questions-loop) + HTML autocontido com curva e tabela.
    preview_evolution_enabled: bool = Field(default=True)
    preview_evolution_jsonl_path: Path = Field(default=Path("./preview/organize_evolution.jsonl"))
    preview_evolution_html_path: Path = Field(default=Path("./preview/evolucao-organizacao.html"))
    preview_completion_note_path: Path = Field(default=Path("./preview/terminei.txt"))
    #: Ao encerrar **sem interrupção por sinal**, sem erro no último ciclo e sem truncagem por
    #: ``max_records_per_cycle``, grava ``preview_completion_note_path`` e abre editor (macOS: TextEdit).
    #: Interrupção (Ctrl+C / SIGTERM) nunca abre o aviso «terminei».
    preview_open_note_on_exit: bool = Field(default=True)

    #: organize-loop: após N ciclos seguidos com 0 documentos normalizados e sem erro, encerra com «fila vazia»
    #: (permite concluir o loop sem Ctrl+C e então abrir «terminei»). 0 = desativado.
    organize_loop_idle_cycles_before_exit: int = Field(default=0, ge=0, le=10_000)

    #: Corpus já normalizado (mesmo payload que Supabase), mesclado por ``external_id`` neste arquivo Git no projeto.
    repository_corpus_enabled: bool = Field(default=False)
    repository_corpus_path: Path = Field(default=Path("./repository/lex_corpus.jsonl"))

    #: Cópia do manifesto analisado/categorizado em pasta dedicada (mesmo formato que ``data/organized``).
    analyzed_output_enabled: bool = Field(default=False)
    analyzed_output_path: Path = Field(default=Path("./data/analyzed"))

    # IA opcional: classificar/registrar organização; cache SQLite replica decisões sem novo custo.
    ai_enabled: bool = False
    ai_mode: Literal["off", "fallback", "enrich", "full"] = "fallback"
    ai_provider: Literal["anthropic", "openai", "openai_compatible", "ollama"] = "anthropic"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    #: Ollama ``http://127.0.0.1:11434/v1``, LM Studio ``http://localhost:1234/v1``.
    openai_compatible_base_url: str | None = None
    #: Opcional para servidores locais que exijam Bearer (Ollama aceita valor fictício).
    openai_compatible_api_key: str | None = None
    ai_model: str = ""
    ai_timeout_seconds: float = 90.0
    ai_max_input_chars: int = 12000
    ai_max_calls_per_cycle: int = 40
    ai_min_confidence: float = 0.35
    ai_full_doc_override_threshold: float = 0.62
    ai_cache_path: Path = Field(default=Path(".lex_agent/ai_cache.sqlite"))

    # --- Loop de scraping (monitor em data/scrape_status.json; opcional Playwright QConcurso)
    scrape_loop_mode: Literal["off", "shell", "playwright_harvest"] = Field(
        default="shell",
        description="shell: LEX_AGENT_SCRAPE_LOOP_SHELL_COMMAND; playwright_harvest: QConcurso (requer [playwright]).",
    )
    scrape_loop_interval_seconds: int = Field(default=300, ge=5)
    scrape_status_path: Path = Field(default=Path("./data/scrape_status.json"))
    scrape_job_name: str = Field(default="naintegra-scrape-loop")
    #: Comando shell por ciclo (ex.: crawler externo ou curl). Ignorado se modo ≠ shell.
    scrape_loop_shell_command: str = Field(default="true")
    scrape_loop_shell_timeout_seconds: int = Field(default=3600, ge=1)
    #: Parâmetros do harvest (QC_STUDY_* para URLs, inbox e estado de sessão).
    scrape_harvest_seconds: float = Field(default=90.0, ge=1.0)
    scrape_harvest_headed: bool = False
    scrape_harvest_url_substring: str = ""
    scrape_harvest_out: str | None = Field(
        default=None,
        description="Arquivo JSONL de saída relativo ao inbox ou caminho absoluto; vazio = timestamp.",
    )
    scrape_harvest_append: bool = True
    scrape_harvest_emit_unknown_wrong: bool = Field(
        default=False,
        description="Repasse para emit_if_wrong_unknown no harvest (mais registros, mais ruído).",
    )
    #: wrong_only: só questões marcadas como erradas na sessão (fluxo legado “erradas”). Default Lex: all_with_gabarito.
    scrape_harvest_emit_mode: Literal["wrong_only", "all_with_gabarito"] = Field(
        default="all_with_gabarito",
        description="Modo de extração no playwright-harvest (Lex / inbox QConcurso).",
    )
    #: URL inicial do harvest (lista erradas, busca, etc.). Vazio → QC_STUDY_QCONCURSO_BASE_URL.
    scrape_harvest_start_url: str | None = Field(
        default=None,
        description="Playwright goto inicial no modo playwright_harvest (ex.: …/questoes?my_questions=wrong).",
    )

    #: Intervalo do loop unificado scrape→organize (`naintegra-questions-loop`).
    questions_loop_interval_seconds: int = Field(default=120, ge=5)
    #: Um ciclo scrape+collect e encerra (smoke / diagnóstico).
    questions_loop_run_once: bool = Field(default=False)
    #: questions-loop: igual a ``organize_loop_idle_cycles_before_exit`` (fila de normalize vazia).
    questions_loop_idle_cycles_before_exit: int = Field(default=0, ge=0, le=10_000)

    # --- Scraping direcionado banca × cargo (FGV/FCC/CEBRASPE/VUNESP × cargos jurídicos)
    exam_scrape_inbox_path: Path = Field(
        default=Path("./data/exam_scrape/inbox"),
        description="JSONL particionados por banca/cargo antes do Lex.",
    )
    exam_scrape_state_dir: Path = Field(
        default=Path(".lex_agent"),
        description="Estado do índice rotativo do plano de URLs.",
    )
    #: Ordem de eficiência sugerida: agregadores primeiro (JSON na rede); ``official`` é portal bruto.
    exam_scrape_sources: str = Field(default="qconcurso,techconcursos")
    exam_scrape_pairs_per_cycle: int = Field(
        default=6,
        ge=1,
        le=500,
        description="Quantos pares URL (banca×cargo×fonte) visitar por ciclo do exam-boards-loop.",
    )
    exam_scrape_seconds_per_url: float = Field(default=45.0, ge=5.0)
    exam_scrape_include_official: bool = Field(
        default=False,
        description="Inclui homepages das bancas × cargos (pouco JSON; use se precisar de rede própria).",
    )
    exam_scrape_headed: bool = Field(default=False)
    exam_scrape_url_substring: str = Field(
        default="",
        description="Filtra respostas JSON por substring na URL (vazio = todas parseáveis).",
    )
    exam_boards_loop_interval_seconds: int = Field(default=600, ge=30)

    #: Loop norma-consolidate: pastas markdown adicionais (output_legislacao, etc.)
    norma_markdown_roots: str = Field(
        default="",
        description="Vírgula: pastas .md para consolidar em norma_chunks.",
    )
    norma_ai_format_enabled: bool = Field(
        default=False,
        description="Formata texto jurídico via Ollama antes do upsert (limpa crawl).",
    )
    norma_ai_format_mode: Literal["off", "fallback", "always"] = Field(default="fallback")
    norma_consolidate_loop_idle_cycles_before_exit: int = Field(default=0, ge=0, le=10_000)
    norma_consolidate_state_db_path: Path = Field(default=Path(".lex_agent/norma_consolidate.sqlite"))
    norma_consolidate_enrich_catalog: bool = Field(default=True)

    #: --- Pipeline semanal LEXML → crawl_inbox → promoção Planalto (Lex web/apps)
    lexml_crawl_command: str = Field(
        default="",
        description="Comando shell opcional (naintegra-crawl externo) antes da busca LEXML.",
    )
    lexml_crawl_timeout_seconds: int = Field(default=3600, ge=60)
    lexml_lookback_days: int = Field(
        default=8,
        ge=1,
        le=90,
        description="Janela de datas na 1ª execução ou sem last_run em data/lexml_weekly_state.json.",
    )
    lexml_search_sleep_seconds: float = Field(default=0.25, ge=0.0, le=5.0)

    def resolved_openai_compatible_base_url(self) -> str | None:
        """API estilo OpenAI (``…/v1``): Ollama local usa default se a URL estiver vazia."""

        raw = (self.openai_compatible_base_url or "").strip()
        if self.ai_provider == "ollama":
            return raw or "http://127.0.0.1:11434/v1"
        if self.ai_provider == "openai_compatible":
            return raw or None
        return None

    def has_supabase_credentials(self) -> bool:
        """URL e service role preenchidos (não vazios)."""

        return bool((self.supabase_url or "").strip() and (self.supabase_service_role_key or "").strip())


def load_settings() -> Settings:
    return Settings()
