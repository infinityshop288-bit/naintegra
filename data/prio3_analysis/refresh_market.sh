#!/usr/bin/env bash
# Atualiza todos os dados do Panorama de Mercado (rodar 1x/dia, apos o fechamento).
#   - macro.json          (BCB + FRED + Yahoo)
#   - multi_analysis.json  (tecnicos + vies + analistas + Ibovespa de todo o universo)
#   - /tmp/opts_<ROOT>.txt  (opcoes filtradas do COTAHIST anual da B3, todos os roots)
#   - multi_options.json   (opcoes por acao + oportunidades do dia)
#   - fatos_relevantes_multi.json (fatos + resultados via CVM)
# build_opts.py baixa o COTAHIST automaticamente: nao requer arquivos manuais.
set -uo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python

echo "[1/5] macro..."         && $PY macro.py            >/dev/null && echo "  ok"
echo "[2/5] analise..."       && $PY multi_analysis.py   >/dev/null && echo "  ok"
echo "[3/5] opcoes (COTAHIST)..." && $PY build_opts.py   >/dev/null && echo "  ok"
echo "[4/5] opcoes (agrega)..."   && $PY multi_options.py >/dev/null && echo "  ok"
echo "[5/7] fatos/result..."  && $PY scrape_fatos_multi.py >/dev/null && echo "  ok"
echo "[6/7] fundamentos..."   && $PY fundamentals_multi.py >/dev/null && echo "  ok"
echo "[7/8] rotas petróleo..." && $PY oil_routes.py        >/dev/null && echo "  ok"
echo "[8/8] peers vs Brent..." && $PY oil_peers_compare.py >/dev/null && echo "  ok"
# reprocessa a analise p/ incorporar o Put/Call Ratio recem-gerado (fluxo por ativo)
$PY multi_analysis.py >/dev/null
echo "Concluido. Recarregue mercado.html / opcoes.html."
