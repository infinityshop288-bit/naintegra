#!/usr/bin/env bash
# Gera keystore de release para assinar o .aab (guarde backup e senhas).
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
KEYSTORE="$MOBILE/android/release.keystore"
PROPS="$MOBILE/android/keystore.properties.example"

if ! command -v keytool >/dev/null 2>&1; then
  echo "Instale JDK 17+ (Android Studio inclui)." >&2
  exit 1
fi

if [[ -f "$KEYSTORE" ]]; then
  echo "Keystore já existe: $KEYSTORE" >&2
  exit 1
fi

read -r -p "Senha do keystore (guarde em local seguro): " STOREPASS
read -r -p "CN (ex: NaIntegra Cursos): " CN
CN="${CN:-NaIntegra Cursos}"

keytool -genkeypair -v \
  -keystore "$KEYSTORE" \
  -alias naintegra-lex \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -storepass "$STOREPASS" -keypass "$STOREPASS" \
  -dname "CN=$CN, OU=Mobile, O=NaIntegra Cursos, L=BR"

echo ""
echo "Keystore criado: $KEYSTORE"
echo "Extraia SHA-256 para assetlinks:"
echo "  python3 mobile/scripts/update-assetlinks.py --from-keystore $KEYSTORE --storepass '***'"
echo ""
echo "Copie keystore.properties.example → keystore.properties e preencha (não commite)."

cat > "$PROPS" <<EOF
storeFile=release.keystore
storePassword=SUA_SENHA
keyAlias=naintegra-lex
keyPassword=SUA_SENHA
EOF
