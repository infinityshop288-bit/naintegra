#!/usr/bin/env bash
# Publica NaIntegra Lex na Play (loop) e tenta App Store.
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$MOBILE/.." && pwd)"
LOG="$MOBILE/dist/publish-loop.log"
MAX_PLAY="${PUBLISH_MAX_ATTEMPTS:-5}"

mkdir -p "$MOBILE/dist"
exec > >(tee -a "$LOG") 2>&1

echo "══════════════════════════════════════════════"
echo " NaIntegra Lex — publish loop $(date -Iseconds)"
echo "══════════════════════════════════════════════"

echo ""
echo "==> Build AAB (versionCode atual)"
if ! bash "$MOBILE/scripts/build-release-aab.sh"; then
  echo "[ERRO] AAB falhou" >&2
  exit 1
fi

play_ok=0
for i in $(seq 1 "$MAX_PLAY"); do
  echo ""
  echo "==> Play Console tentativa $i/$MAX_PLAY"
  if python3 "$MOBILE/scripts/publish-play-full.py"; then
    play_ok=1
    break
  fi
  echo "[WARN] Play tentativa $i falhou — aguardando 15s"
  sleep 15
done

echo ""
echo "==> App Store (iOS archive + upload)"
ios_ok=0
if bash "$MOBILE/scripts/archive-ios.sh"; then
  ios_ok=1
  echo "[OK] iOS archive/upload"
else
  echo "[BLOQUEIO iOS] Verifique:"
  echo "  • Apple Developer Program ativo (US\$ 99/ano)"
  echo "  • Xcode → Settings → Accounts → Download Manual Profiles"
  echo "  • developer.apple.com → Identifiers → br.com.naintegracursos.lex"
  echo "  • Ou conecte um iPhone e registre como dispositivo de desenvolvimento"
fi

echo ""
echo "══════════════════════════════════════════════"
echo " Resultado: Play=$play_ok iOS=$ios_ok"
echo " Log: $LOG"
echo "══════════════════════════════════════════════"

if [[ "$play_ok" -eq 1 ]]; then
  exit 0
fi
exit 1
