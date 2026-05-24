#!/usr/bin/env bash
# Gera Android App Bundle (.aab) release assinado (requer JDK 17+).
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
ANDROID="$MOBILE/android"
AAB="$ANDROID/app/build/outputs/bundle/release/app-release.aab"

find_java() {
  if [[ -n "${JAVA_HOME:-}" ]] && [[ -x "$JAVA_HOME/bin/java" ]]; then
    return 0
  fi
  local candidates=(
    "/Applications/Android Studio.app/Contents/jbr/Contents/Home"
    "/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
    "/usr/local/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home"
  )
  for c in "${candidates[@]}"; do
    if [[ -x "$c/bin/java" ]]; then
      export JAVA_HOME="$c"
      export PATH="$JAVA_HOME/bin:$PATH"
      return 0
    fi
  done
  if command -v java >/dev/null 2>&1 && java -version >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

if ! find_java; then
  echo "JDK 17+ não encontrado. Instale Android Studio ou OpenJDK 17." >&2
  exit 1
fi

if [[ ! -f "$ANDROID/keystore.properties" ]]; then
  echo "keystore.properties ausente — rode: bash mobile/scripts/setup-android-signing.sh" >&2
  exit 1
fi

echo "Java: $(java -version 2>&1 | head -1)"
cd "$ANDROID"
chmod +x gradlew
./gradlew bundleRelease --no-daemon

if [[ -f "$AAB" ]]; then
  echo ""
  echo "AAB: $AAB"
  ls -lh "$AAB"
  cp "$AAB" "$MOBILE/dist/naintegra-lex-release.aab" 2>/dev/null || mkdir -p "$MOBILE/dist" && cp "$AAB" "$MOBILE/dist/naintegra-lex-release.aab"
  echo "Cópia: $MOBILE/dist/naintegra-lex-release.aab"
else
  echo "AAB não encontrado após build" >&2
  exit 1
fi
