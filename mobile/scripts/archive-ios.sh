#!/usr/bin/env bash
# Archive + upload NaIntegra Lex para App Store Connect (requer conta Apple Developer paga).
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
IOS="$MOBILE/ios/App"
DIST="$MOBILE/dist"
TEAM_ID="${APPLE_TEAM_ID:-D7323783Z5}"

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
  -allowProvisioningUpdates

xcodebuild \
  -exportArchive \
  -archivePath "$ARCHIVE" \
  -exportPath "$EXPORT_DIR" \
  -exportOptionsPlist "$DIST/ExportOptions.plist" \
  -allowProvisioningUpdates \
  DEVELOPMENT_TEAM="$TEAM_ID"

echo ""
echo "IPA gerado em: $EXPORT_DIR"
echo "Se o upload automático falhar, use Xcode → Organizer → Distribute App."
