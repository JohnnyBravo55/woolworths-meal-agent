#!/usr/bin/env bash
# Build Chromium + Firefox zip packages into apps/mobile/public/extension/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
EXT="$ROOT/apps/browser-extension"
OUT="$ROOT/apps/mobile/public/extension"
mkdir -p "$OUT"

pack() {
  local manifest_src="$1"
  local zip_name="$2"
  local stage
  stage="$(mktemp -d)"
  cp "$EXT/$manifest_src" "$stage/manifest.json"
  cp "$EXT/background.js" "$EXT/content-script.js" "$EXT/popup.html" "$EXT/popup.css" "$EXT/popup.js" "$stage/"
  cp -R "$EXT/icons" "$stage/icons"
  (cd "$stage" && zip -qr "$OUT/$zip_name" .)
  rm -rf "$stage"
  echo "Wrote $OUT/$zip_name"
}

pack manifest.chromium.json meal-agent-connect-chromium.zip
pack manifest.firefox.json meal-agent-connect-firefox.zip
echo Done.
