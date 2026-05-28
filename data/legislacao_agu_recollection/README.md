# Legislação AGU — re-coleta Planalto (backup)

Pasta **separada** de `data/legislacao_agu/` para facilitar backup e versionamento
(em repositório git próprio, se desejar).

## Conteúdo

- `runs/<timestamp>/legislacao_agu_recollection.jsonl` — normas re-coletadas com encoding ISO-8859-1
- `runs/<timestamp>/report.json` — relatório da execução
- `manifest.json` — último run e totais
- `state.json` — URLs já re-coletadas com sucesso

## Gerar

```bash
python3 scripts/recollect_agu_planalto_legislacao.py
```

## Ingerir no Lex (opcional)

```bash
export AGU_LEGIS_INPUT_DIR="$(pwd)/data/legislacao_agu_recollection/runs/<timestamp>"
python3 scripts/ingest_agu_legislacao_from_scraper.py --force
```
