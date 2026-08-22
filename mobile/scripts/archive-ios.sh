#!/usr/bin/env bash
# Archive + upload NaIntegra Lex para App Store Connect (requer conta Apple Developer paga).
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
IOS="$MOBILE/ios/App"
DIST="$MOBILE/dist"
TEAM_ID="${APPLE_TEAM_ID:-D7323783Z5}"

auth_args=()
if [[ -n "${APPLE_API_KEY_ID:-}" && -n "${APPLE_API_ISSUER_ID:-}" ]]; then
  KEY_PATH="${APPLE_API_KEY_PATH:-$HOME/.appstoreconnect/private_keys/AuthKey_${APPLE_API_KEY_ID}.p8}"
  if [[ -f "$KEY_PATH" ]]; then
    auth_args=(
      -authenticationKeyID "$APPLE_API_KEY_ID"
      -authenticationKeyIssuerID "$APPLE_API_ISSUER_ID"
      -authenticationKeyPath "$KEY_PATH"
    )
    echo "[OK] App Store Connect API key: $APPLE_API_KEY_ID"
  fi
fi

cd "$MOBILE"
npm run build

mkdir -p "$DIST"
ARCHIVE="$DIST/App.xcarchive"
EXPORT_DIR="$DIST/appstore"

xcodebuild \
  -workspace "$IOS/App.xcworkspace" \
  -scheme App \
  -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath "$ARCHIVE" \
  archive \
  DEVELOPMENT_TEAM="$TEAM_ID" \
  CODE_SIGN_STYLE=Automatic \
  -allowProvisioningUpdates \
  ${auth_args[@]+"${auth_args[@]}"}

xcodebuild \
  -exportArchive \
  -archivePath "$ARCHIVE" \
  -exportPath "$EXPORT_DIR" \
  -exportOptionsPlist "$DIST/ExportOptions.plist" \
  -allowProvisioningUpdates \
  DEVELOPMENT_TEAM="$TEAM_ID" \
  ${auth_args[@]+"${auth_args[@]}"}

TEAM_IN_ARCHIVE=$(plutil -extract ApplicationProperties.Team raw "$ARCHIVE/Info.plist" 2>/dev/null || echo "")
if [[ -z "$TEAM_IN_ARCHIVE" ]]; then
  echo ""
  echo "[ERRO] Archive sem Team — abra mobile/ios/App no Xcode:"
  echo "  Target App → Signing & Capabilities → Team: D7323783Z5"
  echo "  Product → Archive (não use archive antigo no Organizer)"
  exit 1
fi
echo "[OK] Archive assinado — Team: $TEAM_IN_ARCHIVE"

echo ""
echo "IPA / upload em: $EXPORT_DIR"
if [[ ${#auth_args[@]} -eq 0 ]]; then
  echo "Sem API key: use Xcode → Settings → Accounts → infinity.shop288@gmail.com → Download Manual Profiles"
  echo "Ou defina APPLE_API_KEY_ID, APPLE_API_ISSUER_ID e APPLE_API_KEY_PATH."
fi
