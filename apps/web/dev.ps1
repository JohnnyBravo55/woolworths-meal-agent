@echo off
REM Legacy: Start API + Vite web UI. Prefer dev-mobile.ps1 (Expo) for new development.
start "meal-agent-api" cmd /k "cd /d %~dp0..\.. && pip install -e . -q && meal-agent-api"
timeout /t 2 /nobreak >nul
start "meal-agent-web" cmd /k "cd /d %~dp0 && npm run dev"
echo API: http://127.0.0.1:8000
echo Web (legacy Vite): http://localhost:5173
echo Prefer Expo: run dev-mobile.ps1 from repo root
