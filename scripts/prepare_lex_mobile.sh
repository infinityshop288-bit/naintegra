#!/usr/bin/env bash
# Atalho na raiz do repo → mobile/scripts/prepare-native-projects.sh
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$ROOT/mobile/scripts/prepare-native-projects.sh" "$@"
