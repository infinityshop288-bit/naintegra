#!/usr/bin/env bash
# Abre as 3 telas da Play Console para concluir teste fechado.
DEV=5476168127224845991
PKG=br.com.naintegracursos.lex
BASE="https://play.google.com/console/u/0/developers/${DEV}/app/${PKG}"
open "${BASE}/tracks/closed-testing/countries"
sleep 1
open "${BASE}/tracks/closed-testing/testers"
sleep 1
open "${BASE}/tracks/closed-testing"
sleep 1
open "${BASE}/publishing/overview"
echo "Abertas: países, testadores, faixa teste fechado e painel de publicação."
