#!/usr/bin/env bash
# Wrapper CocoaPods (Ruby 2.6 macOS exige -rlogger antes do ActiveSupport).
set -euo pipefail
MOBILE="$(cd "$(dirname "$0")/.." && pwd)"
export RUBYOPT="-rlogger ${RUBYOPT:-}"
cd "$MOBILE"
exec bundle exec pod "$@"
