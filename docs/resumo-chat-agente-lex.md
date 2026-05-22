# Resumo do chat — NaIntegra Lex Agent (organização, preview, Supabase)

Documento gerado a partir da conversa no Cursor sobre o agente Lex (`naintegra-lex-agent`): loops locais, preview de evolução, publicação Supabase, pastas de material e esclarecimentos.

**Repositório:** `naintegra`  
**Ano de referência:** 2026  

---

## 1. Visão geral

O trabalho no chat concentrou-se em:

- Garantir **fusão → normalização → manifestos em disco** quando **não há** (ou não se usa) Supabase no momento.
- **Loops** (`organize-loop`, `questions-loop`) sem upsert obrigatório no organize-loop.
- **Preview** da evolução ciclo a ciclo (`preview/evolucao-organizacao.html` + `preview/organize_evolution.jsonl`).
- Regra para abrir o bloco de notas **`terminei`** só quando o encerramento indica **material da volta processado por completo** (sem Ctrl+C, sem erro no último ciclo, sem atingir `MAX_RECORDS_PER_CYCLE`).
- **Supabase:** credenciais no `.env`, instalação `[supabase]`, comando `lex_publish`; erro **PGRST106** se o schema `lex` não estiver exposto na API do projeto.
- **Esclarecimento:** neste chat **não** foram criados scrapers dedicados a **Vademecum** nem download automático do site **Informativo Trilhante**; existe apenas **fusão** de JSONL se `LEX_AGENT_TRILHANTE_INFORMATIVO_ROOT` apontar para uma pasta populada por outro meio.

---

## 2. Alterações principais no código (Python)

| Área | Descrição |
|------|-----------|
| `supabase_sink.py` | `upsert_batches` retorna `bool`; sem credenciais **não** levanta erro — aviso em log e retorno `False`. |
| `agent.py` | `process_single_cycle` só marca estado local após upsert bem-sucedido (ou dry-run). |
| `lex_publish.py` | Respeita retorno do upsert; não marca estado se skip; `return 0` quando `pending` vazio. |
| `settings.py` | `has_supabase_credentials()`; campos de preview (`preview_evolution_*`, `preview_completion_note_*`, `preview_open_note_on_exit`); `organize_loop_idle_cycles_before_exit`, `questions_loop_idle_cycles_before_exit`. |
| `organize_loop.py` | `apply_loop_defaults`: sem Supabase → `analyzed_output_enabled=True`; `run_once` suportado; preview por ciclo; `maybe_open_terminei_completion_note`; idle exit opcional. |
| `questions_loop.py` | Mesmo preview + regras do `terminei`; idle opcional. |
| `preview_evolution.py` | Append JSONL + HTML autocontido; `completion_note_skip_reason` / `maybe_open_terminei_completion_note`; `write_terminei_note_and_open`. |
| `preview/index.html` / `serve_preview.py` | Link e URL para página de evolução. |
| `.env.example` | Supabase, preview, idle cycles, nota sobre expor schema `lex`. |
| Testes | `test_preview_evolution.py`, `test_supabase_sink.py`, ajustes em `test_trilhante_publish.py`. |

---

## 3. Comandos úteis

```bash
# Na raiz do repositório (ou com pacote instalado)

# Loop só disco (fusão + organize + analyzed conforme .env)
PYTHONPATH=src python3 -m naintegra_lex_agent.organize_loop

# Um ciclo e sair
LEX_AGENT_RUN_ONCE=true PYTHONPATH=src python3 -m naintegra_lex_agent.organize_loop

# Scrape (Playwright) + organize
PYTHONPATH=src python3 -m naintegra_lex_agent.questions_loop

# Publicar no Supabase (após schema/tabela e API)
python3 -m pip install -e '.[supabase]'
PYTHONPATH=src python3 -m naintegra_lex_agent.lex_publish --force-all

# Servir previews HTTP
python3 preview/serve_preview.py
```

Scripts de entrada em `pyproject.toml`: `naintegra-organize-loop`, `naintegra-questions-loop`, `naintegra-trilhante-publish`, `naintegra-lex-agent`, etc.

---

## 4. Pastas — coleta vs organizado

### Entrada / fusão (material coletado ou gerado por outros pipelines)

- `data/crawl_inbox/` — inbox Lex + `corpus.jsonl` após fusão (`LEX_AGENT_CRAWL_INBOX_PATH`).
- `data/qconcurso/inbox/` — harvest QConcurso (`QC_STUDY_QCONCURSO_INBOX_PATH`).
- `data/exam_scrape/inbox/` — raspagem banca×cargo.
- `data/raw_preserved/` — cópias preservadas (`LEX_AGENT_RAW_PRESERVED_PATH`).
- `examples/crawl/` — default em `material_merge_extra_roots`.
- Opcional: pasta em **`LEX_AGENT_TRILHANTE_INFORMATIVO_ROOT`** (ex.: `output_trilhante_informativo/`) — deve conter `**/*.jsonl` produzidos **fora** deste fluxo se quiser fundir Trilhante aqui.

Legislação, jurisprudência e súmulas **não** ficam em subpastas separadas por tipo na origem; o tipo aparece nos registros/manifestos.

### Saída organizada / analisada

- `data/organized/<batch_id>/manifest.jsonl` — típico `latest/`.
- `data/analyzed/<batch_id>/manifest.jsonl` — se `LEX_AGENT_ANALYZED_OUTPUT_ENABLED=true`.

### Preview

- `preview/organize_evolution.jsonl` — histórico por ciclo.
- `preview/evolucao-organizacao.html` — gráfico + tabela (funciona em `file://`).
- `preview/terminei.txt` — texto ao encerrar (quando as regras permitem abrir o editor).

### Opcional Git

- `repository/lex_corpus.jsonl` — se `LEX_AGENT_REPOSITORY_CORPUS_ENABLED=true`.

---

## 5. Supabase

1. Aplicar SQL: `sql/lex_ingested_documents.sql` (schema `lex`, tabela `ingested_documents`, `unique(external_id)`).
2. No painel Supabase: **Project Settings → Data API → Exposed schemas** — incluir **`lex`** (evita `PGRST106`).
3. `.env`: `LEX_AGENT_SUPABASE_URL`, `LEX_AGENT_SUPABASE_SERVICE_ROLE_KEY` preenchidos (não commitar).
4. `pip install -e '.[supabase]'` e rodar `lex_publish` ou agente principal para upsert.

`organize-loop` **não** envia ao Supabase; use `naintegra-trilhante-publish` / `lex_publish` ou `naintegra-lex-agent`.

---

## 6. Bloco de notas «terminei»

Abre **somente** se:

- `LEX_AGENT_PREVIEW_OPEN_NOTE_ON_EXIT=true`, e  
- encerramento **sem** interrupção por sinal (Ctrl+C / SIGTERM), e  
- último ciclo **sem erro**, e  
- último ciclo com `len(rows) < LEX_AGENT_MAX_RECORDS_PER_CYCLE` (evita marcar “concluído” com possível truncagem).

Opcional: encerrar após fila vazia sem Ctrl+C — `LEX_AGENT_ORGANIZE_LOOP_IDLE_CYCLES_BEFORE_EXIT` / `LEX_AGENT_QUESTIONS_LOOP_IDLE_CYCLES_BEFORE_EXIT` (> 0).

---

## 7. Como obter este arquivo (download)

O Markdown está versionado em:

**`docs/resumo-chat-agente-lex.md`**

No Cursor ou no Finder: abra o arquivo e use **Save As…**, ou no terminal na raiz do repo:

```bash
cp docs/resumo-chat-agente-lex.md ~/Downloads/
```

No GitHub (após push): visualize o arquivo no repositório e use **Raw** → salvar como `.md`.

---

## 8. Estado observado na sessão (referência)

- Corpus fundido com **4 registros únicos** (demonstrações / exemplos), manifests com **4** linhas em `organized/latest` e `analyzed/latest` quando `analyzed` habilitado.
- `organize-loop` em background em alguns momentos (PID mudava ao reiniciar após alteração do `.env`).
- Tentativa de `lex_publish --force-all` encontrou API sem schema `lex` exposto até correção no painel.

---

*Fim do resumo. Ajuste este arquivo se o fluxo ou os defaults mudarem no código.*
