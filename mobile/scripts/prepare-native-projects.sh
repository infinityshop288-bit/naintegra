#!/usr/bin/env bash
# Prepara projetos Android (Android Studio) e iOS (Xcode) via Capacitor.
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$MOBILE"

# Ruby 2.6 (macOS): ActiveSupport exige stdlib Logger carregado antes do pod.
export RUBYOPT="-rlogger ${RUBYOPT:-}"

echo "==> Sincronizando web/lex → mobile/www"
bash scripts/sync-lex-www.sh

if [[ ! -d node_modules ]]; then
  echo "==> npm install"
  npm install
fi

if [[ "$(uname -s)" == "Darwin" ]] && [[ ! -x vendor/bundle/ruby/2.6.0/bin/pod ]]; then
  echo "==> bundle install (CocoaPods)"
  bundle config set --local path vendor/bundle 2>/dev/null || true
  bundle install --path vendor/bundle
fi

if [[ ! -d android ]]; then
  echo "==> Criando projeto Android"
  npx cap add android
fi

if [[ "$(uname -s)" == "Darwin" ]] && [[ ! -d ios ]]; then
  echo "==> Criando projeto iOS"
  npx cap add ios || echo "[AVISO] cap add ios falhou — rode: cd mobile/ios/App && RUBYOPT=-rlogger bundle exec pod install"
fi

echo "==> Branding (ícones Lex)"
bash scripts/apply-mobile-branding.sh

echo "==> cap sync"
npx cap sync

if [[ -d ios/App ]] && [[ -x vendor/bundle/ruby/2.6.0/bin/pod ]]; then
  echo "==> pod install (iOS)"
  (cd ios/App && bundle exec pod install) || true
fi

echo ""
echo "Pronto."
echo "  Android Studio: cd mobile && npm run android"
echo "  Xcode:          cd mobile && npm run ios"
