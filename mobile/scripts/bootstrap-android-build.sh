#!/usr/bin/env bash
# Instala JDK 17 + Android SDK (cmdline-tools) em mobile/.tools para build local do .aab
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$MOBILE/.tools"
JDK="$TOOLS/jdk-21"
SDK="$TOOLS/android-sdk"
ARCH="$(uname -m)"
ADOPT_ARCH="$ARCH"
[[ "$ARCH" == "arm64" ]] && ADOPT_ARCH="aarch64"

mkdir -p "$TOOLS"

if [[ ! -x "$TOOLS/jdk-home/bin/java" ]]; then
  echo "==> Baixando JDK 21 (Temurin)..."
  TMP="$(mktemp -d)"
  curl -fsSL "https://api.adoptium.net/v3/binary/latest/21/ga/mac/${ADOPT_ARCH}/jdk/hotspot/normal/eclipse?project=jdk" \
    -o "$TMP/jdk.tar.gz"
  rm -rf "$JDK"
  mkdir -p "$JDK"
  tar -xzf "$TMP/jdk.tar.gz" -C "$JDK" --strip-components=1
  rm -rf "$TMP"
  if [[ -x "$JDK/Contents/Home/bin/java" ]]; then
    ln -sfn "$JDK/Contents/Home" "$TOOLS/jdk-home"
  elif [[ -x "$JDK/bin/java" ]]; then
    ln -sfn "$JDK" "$TOOLS/jdk-home"
  else
    echo "JDK extraído em formato inesperado em $JDK" >&2
    exit 1
  fi
  echo "JDK: $("$TOOLS/jdk-home/bin/java" -version 2>&1 | head -1)"
else
  echo "JDK OK: $("$TOOLS/jdk-home/bin/java" -version 2>&1 | head -1)"
fi

export JAVA_HOME="$TOOLS/jdk-home"
export PATH="$JAVA_HOME/bin:$PATH"

CMD="$SDK/cmdline-tools/latest/bin/sdkmanager"
if [[ ! -x "$CMD" ]]; then
  echo "==> Baixando Android command-line tools..."
  TMP="$(mktemp -d)"
  curl -fsSL "https://dl.google.com/android/repository/commandlinetools-mac-${ARCH/_/-}-11076708_latest.zip" \
    -o "$TMP/cmdline.zip" 2>/dev/null || \
  curl -fsSL "https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip" \
    -o "$TMP/cmdline.zip"
  rm -rf "$SDK/cmdline-tools"
  mkdir -p "$SDK/cmdline-tools/latest"
  unzip -q "$TMP/cmdline.zip" -d "$TMP/unz"
  mv "$TMP/unz/cmdline-tools/"* "$SDK/cmdline-tools/latest/"
  rm -rf "$TMP"
fi

export ANDROID_HOME="$SDK"
export ANDROID_SDK_ROOT="$SDK"
yes | "$CMD" --sdk_root="$SDK" --licenses >/dev/null 2>&1 || true
"$CMD" --sdk_root="$SDK" "platform-tools" "platforms;android-35" "build-tools;35.0.0"

cat > "$MOBILE/android/local.properties" <<EOF
sdk.dir=$SDK
EOF

echo ""
echo "Pronto: JAVA_HOME=$JAVA_HOME"
echo "         ANDROID_HOME=$ANDROID_HOME"
