# Build Chromium + Firefox zip packages into apps/mobile/public/extension/
$ErrorActionPreference = "Stop"
# scripts/ -> browser-extension/ -> apps/ -> repo root
$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$ext = Join-Path $root "apps\browser-extension"
$out = Join-Path $root "apps\mobile\public\extension"
New-Item -ItemType Directory -Force -Path $out | Out-Null

$files = @(
  "background.js",
  "content-script.js",
  "popup.html",
  "popup.css",
  "popup.js",
  "icons"
)

function New-ExtZip([string]$manifestSrc, [string]$zipName) {
  $stage = Join-Path $env:TEMP ("meal-agent-ext-" + [guid]::NewGuid().ToString("n"))
  New-Item -ItemType Directory -Force -Path $stage | Out-Null
  try {
    Copy-Item (Join-Path $ext $manifestSrc) (Join-Path $stage "manifest.json")
    foreach ($f in $files) {
      Copy-Item (Join-Path $ext $f) (Join-Path $stage $f) -Recurse -Force
    }
    $zipPath = Join-Path $out $zipName
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath -Force
    Write-Host "Wrote $zipPath"
  } finally {
    Remove-Item $stage -Recurse -Force -ErrorAction SilentlyContinue
  }
}

New-ExtZip "manifest.chromium.json" "meal-agent-connect-chromium.zip"
New-ExtZip "manifest.firefox.json" "meal-agent-connect-firefox.zip"
Write-Host "Done."
