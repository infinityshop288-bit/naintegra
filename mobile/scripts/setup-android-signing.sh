#!/usr/bin/env bash
# Gera keystore PKCS12 (OpenSSL), atualiza assetlinks.json e publica no site.
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$MOBILE/.." && pwd)"
ANDROID="$MOBILE/android"
KEYSTORE="$ANDROID/release.keystore"
CERT_PEM="$ANDROID/release-cert.pem"
SIGNING_ENV="$ANDROID/.signing-local"
ALIAS="naintegra-lex"
VALID_DAYS=10000

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl não encontrado" >&2
  exit 1
fi

mkdir -p "$ANDROID"

if [[ -f "$SIGNING_ENV" ]]; then
  # shellcheck disable=SC1090
  source "$SIGNING_ENV"
fi

if [[ ! -f "$KEYSTORE" ]]; then
  if [[ -z "${STOREPASS:-}" ]]; then
    STOREPASS="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 24)"
  fi
  KEYPASS="${KEYPASS:-$STOREPASS}"
  echo "Gerando keystore: $KEYSTORE"
  TMP="$(mktemp -d)"
  openssl req -x509 -newkey rsa:2048 \
    -keyout "$TMP/key.pem" -out "$TMP/cert.pem" \
    -days "$VALID_DAYS" -nodes \
    -subj "/CN=NaIntegra Lex/OU=Mobile/O=NaIntegra Cursos/C=BR" 2>/dev/null
  openssl pkcs12 -export \
    -in "$TMP/cert.pem" -inkey "$TMP/key.pem" \
    -out "$KEYSTORE" -name "$ALIAS" \
    -passout "pass:$STOREPASS" 2>/dev/null
  cp "$TMP/cert.pem" "$CERT_PEM"
  rm -rf "$TMP"
  cat > "$SIGNING_ENV" <<EOF
# Gerado por setup-android-signing.sh — NÃO COMMITAR
STOREPASS=$STOREPASS
KEYPASS=$KEYPASS
KEY_ALIAS=$ALIAS
EOF
  chmod 600 "$SIGNING_ENV"
  echo "Senhas salvas em $SIGNING_ENV (gitignored)"
  cat > "$ANDROID/keystore.properties" <<EOF
storeFile=release.keystore
storePassword=$STOREPASS
keyAlias=$ALIAS
keyPassword=$KEYPASS
EOF
  chmod 600 "$ANDROID/keystore.properties"
else
  echo "Keystore existente: $KEYSTORE"
  if [[ -z "${STOREPASS:-}" ]] && [[ -f "$SIGNING_ENV" ]]; then
    source "$SIGNING_ENV"
  fi
  if [[ ! -f "$CERT_PEM" ]]; then
    openssl pkcs12 -in "$KEYSTORE" -clcerts -nokeys -passin "pass:${STOREPASS:?}" -out "$CERT_PEM" 2>/dev/null
  fi
  if [[ ! -f "$ANDROID/keystore.properties" ]] && [[ -n "${STOREPASS:-}" ]]; then
    cat > "$ANDROID/keystore.properties" <<EOF
storeFile=release.keystore
storePassword=$STOREPASS
keyAlias=${KEY_ALIAS:-$ALIAS}
keyPassword=${KEYPASS:-$STOREPASS}
EOF
    chmod 600 "$ANDROID/keystore.properties"
    echo "keystore.properties recriado"
  fi
fi

FP_LINE="$(openssl x509 -in "$CERT_PEM" -noout -fingerprint -sha256 2>/dev/null)"
SHA256="${FP_LINE#SHA256 Fingerprint=}"
SHA256="${SHA256#sha256 Fingerprint=}"
echo "SHA-256: $SHA256"

python3 "$MOBILE/scripts/update-assetlinks.py" --add "$SHA256"

# keystore.properties.example (sem senhas reais)
cat > "$ANDROID/keystore.properties.example" <<EOF
storeFile=release.keystore
storePassword=SUA_SENHA
keyAlias=$ALIAS
keyPassword=SUA_SENHA
EOF

# Gradle signing config snippet reference
if ! grep -q "signingConfigs" "$ANDROID/app/build.gradle" 2>/dev/null; then
  echo ""
  echo "Para assinar release no Gradle, adicione signingConfigs em android/app/build.gradle"
  echo "e copie keystore.properties.example → keystore.properties"
fi

echo ""
echo "==> Publicando assetlinks.json no site"
python3 "$ROOT/scripts/sync_site_root_to_cursos.py" --push || echo "[AVISO] sync site-root ignorado (sem mudanças ou push falhou)"

echo ""
echo "Pronto."
echo "  Keystore: $KEYSTORE"
echo "  Fingerprint: $SHA256"
echo "  URL: https://www.naintegracursos.com.br/.well-known/assetlinks.json"
echo ""
echo "IMPORTANTE: Se usar Play App Signing, após o 1º upload adicione também o SHA-256"
echo "  do Play Console (Integridade do app) com:"
echo "  python3 mobile/scripts/update-assetlinks.py --add \"SHA256_DO_PLAY\""
