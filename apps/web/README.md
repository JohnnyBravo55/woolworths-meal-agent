# Legacy Vite web UI

This app is kept during the Expo migration. **Prefer the Expo app for day-to-day development:**

```powershell
# From repo root
.\dev-mobile.ps1
# Press w in the Expo terminal for PC browser testing
```

Or manually:

```powershell
meal-agent-api
cd apps/mobile
$env:EXPO_PUBLIC_API_URL="http://127.0.0.1:8000"
npx expo start --web
```

The Vite UI at `http://localhost:5173` remains available via `apps/web/dev.ps1` until feature parity is confirmed, then it will be removed.
