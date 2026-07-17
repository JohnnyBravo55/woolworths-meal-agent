# Meal Agent — Woolworths Connect (browser extension)

One-click Woolworths NZ session transfer for the **hosted** Meal Agent site (GitHub Pages → Render API).

## Build packages

From repo root (PowerShell):

```powershell
.\apps\browser-extension\scripts\build-packages.ps1
```

Writes:

- `apps/mobile/public/extension/meal-agent-connect-chromium.zip` (Chrome + Edge)
- `apps/mobile/public/extension/meal-agent-connect-firefox.zip`

## Install

### Chrome

1. Download **chromium** zip and unzip.
2. Open `chrome://extensions`
3. Enable **Developer mode**
4. **Load unpacked** → select the unzipped folder

### Edge

1. Same chromium zip / folder as Chrome
2. Open `edge://extensions`
3. Enable **Developer mode**
4. **Load unpacked**

### Firefox

1. Download **firefox** zip and unzip
2. Open `about:debugging#/runtime/this-firefox`
3. **Load Temporary Add-on…** → pick `manifest.json` inside the folder  
   (Temporary add-ons are removed when Firefox restarts — reload after restart.)

### Safari (macOS)

Safari needs an Xcode wrapper (not a simple zip sideload):

```bash
# On a Mac with Xcode installed, from apps/browser-extension:
cp manifest.chromium.json manifest.json
xcrun safari-web-extension-converter . --project-location ./safari --app-name "Meal Agent Connect"
open ./safari/*.xcodeproj
```

Then in Safari: **Develop → Allow Unsigned Extensions**, run the app from Xcode, enable the extension in Safari Settings → Extensions.

See `safari/README.md` for tester-facing steps.

## How it works

1. Meal Agent Connect page publishes `{ sessionId, accessCode, apiBase }` for the content script.
2. You sign into woolworths.co.nz in the same browser.
3. Extension popup → **Connect Woolworths** reads cookies (including HttpOnly) and POSTs to `/api/session/woolworths/import-cookies`.
