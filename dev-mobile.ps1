# Start API + Expo for phone (LAN) or tunnel fallback
# From CMD use: dev-mobile.cmd   or   dev-mobile-tunnel.cmd
# From PowerShell use: .\dev-mobile.ps1   or   .\dev-mobile.ps1 -Tunnel
param(
    [switch]$Tunnel,
    [string]$ApiUrl = ""
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Mobile = Join-Path $Root "apps\mobile"

function Get-LanIp {
    $wifi = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike "127.*" -and
            $_.IPAddress -notlike "169.254.*" -and
            ($_.InterfaceAlias -match "Wi-Fi|Wireless|WLAN|Ethernet")
        } |
        Select-Object -First 1
    if ($wifi) { return $wifi.IPAddress }
    return $null
}

if (-not $ApiUrl) {
    $lanIp = Get-LanIp
    if ($lanIp) {
        $ApiUrl = "http://${lanIp}:8000"
    } else {
        $ApiUrl = "http://127.0.0.1:8000"
    }
}

$env:EXPO_PUBLIC_API_URL = $ApiUrl
$lanIp = Get-LanIp

if ($Tunnel) {
    Push-Location $Mobile
    npm install --legacy-peer-deps 2>$null
    if (-not (Test-Path "node_modules\@expo\ngrok")) {
        Write-Host "Installing @expo/ngrok (required for tunnel)..."
        npm install --save-dev @expo/ngrok@^4.1.0 --legacy-peer-deps
    }
    Pop-Location
}

$expoArgs = if ($Tunnel) { "npx expo start --tunnel -c" } else { "npx expo start --lan -c" }

$envFile = Join-Path $Root ".env"
if (Test-Path $envFile) {
    $hasOpenAi = Select-String -Path $envFile -Pattern '^\s*OPENAI_API_KEY=\S+' -Quiet
    if ($hasOpenAi) {
        Write-Host "OpenAI: configured in .env — phone uses this PC API (same key as desktop)"
    } else {
        Write-Host "OpenAI: OPENAI_API_KEY missing in .env — meal plans will use templates only"
    }
} else {
    Write-Host "OpenAI: copy .env.example to .env and add OPENAI_API_KEY on your PC"
}

Start-Process cmd -ArgumentList "/k", "cd /d `"$Root`" && pip install -e . -q && meal-agent-api"
Start-Sleep -Seconds 2
Start-Process cmd -ArgumentList "/k", "cd /d `"$Mobile`" && set EXPO_PUBLIC_API_URL=$ApiUrl && $expoArgs"

Write-Host ""
Write-Host "=== Meal Agent dev ==="
Write-Host "API URL:  $ApiUrl"
if ($lanIp) { Write-Host "PC IP:    $lanIp" }
Write-Host "Expo:     $(if ($Tunnel) { 'TUNNEL (wait 30-60s for QR URL)' } else { 'LAN — scan QR in Expo window' })"
Write-Host ""
if (-not $Tunnel) {
    Write-Host "iPhone checklist:"
    Write-Host "  1. Same Wi-Fi as PC"
    Write-Host "  2. Settings > Expo Go > Local Network = ON"
    Write-Host "  3. Test in Safari: http://${lanIp}:8081"
    Write-Host ""
    Write-Host "LAN still timing out? Run:  .\dev-mobile.ps1 -Tunnel"
} else {
    Write-Host "Tunnel: wait until Expo CMD shows a URL like https://xxxx.exp.direct"
    Write-Host "        Then scan the NEW QR code (not the old one)."
}
Write-Host ""
