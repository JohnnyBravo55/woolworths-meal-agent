# Agent handoff — Woolworths Meal Agent (Expo mobile)

**Repo:** `C:\Users\marku\Projects\woolworths-meal-agent`  
**User:** Marku, Windows 10, testing on **PC (Expo web)** and **iPhone (Expo Go SDK 54)**  
**Last updated:** June 2026 (from multi-session chat)

Use this file when starting a **new Cursor agent** on this project. Attach or paste it at the start of the chat.

---

## What this project is

Cross-platform meal-planning wizard that:

1. Collects household preferences  
2. Generates AI meal plans (OpenAI via PC API)  
3. Resolves ingredients to **Woolworths NZ** products  
4. Builds a shop list and adds to Woolworths cart  

**Monorepo layout:**

| Path | Role |
|------|------|
| `apps/mobile/` | **Primary UI** — Expo Router, SDK 54, React Native Web + Expo Go |
| `packages/app-core/` | Shared types, API client, SSE helpers |
| `apps/api/` | FastAPI (`meal-agent-api`) on **port 8000** |
| `packages/woolworths/` | Woolworths adapter, login, cart |
| `apps/web/` | Legacy Vite UI (deprecated; PC testing uses Expo `--web`) |

Wizard flow: **Preferences → Chef → Meal Plan → Recipes → Shop List → Cart**

---

## How to run (Windows)

### PC browser (localhost web)

**Terminal 1 — API:**
```powershell
cd C:\Users\marku\Projects\woolworths-meal-agent
pip install -e ".[dev]"
meal-agent-api
```

**Terminal 2 — Expo web:**
```powershell
cd C:\Users\marku\Projects\woolworths-meal-agent\apps\mobile
$env:EXPO_PUBLIC_API_URL="http://127.0.0.1:8000"
npx expo start --web
```

### Phone (Expo Go, same Wi‑Fi)

```cmd
cd C:\Users\marku\Projects\woolworths-meal-agent
dev-mobile.cmd
```

Or PowerShell: `.\dev-mobile.ps1` — opens two CMD windows (API + Expo with LAN QR).  
**Do not** double-click `.ps1` (opens Notepad); use `.cmd` from CMD.

Tunnel if LAN fails: `dev-mobile-tunnel.cmd` or `.\dev-mobile.ps1 -Tunnel`

### Port confusion (common user issue)

| Service | Port |
|---------|------|
| **meal-agent-api** | **8000** |
| **Expo Metro** | **8081** (or **8082** if busy) |

Phone loads JS from Metro; **all API calls** go to port **8000**.  
Set explicitly if needed: `$env:EXPO_PUBLIC_API_URL="http://192.168.x.x:8000"`

OpenAI key lives in repo root `.env` on the **PC** — phone does not need its own key.

---

## Architecture decisions (do not regress)

1. **Shared logic** in `@meal-agent/app-core` — import statically, never `await import("@meal-agent/app-core")` (breaks Metro web).
2. **SSE on React Native** uses XHR in `packages/app-core/src/api/sse.ts` (fetch streaming broken on iOS).
3. **Metro monorepo** — `apps/mobile/metro.config.js` maps `@meal-agent/app-core` to `packages/app-core`.
4. **No `@react-native-cookies/cookies`** — breaks Expo Go; mobile Woolworths uses WebView + `document.cookie` harvest.
5. **Woolworths sign-in URL:** `https://account.woolworths.co.nz/` for PC browser; WebView starts at homepage with sign-in click — `/shop/myaccount` 404s in browser/WebView.
6. **Web vs mobile styling:** `Platform.OS === "web"` only in `lib/web-layout.ts`, `ActionBar`, `WizardShell`, `Button.btnWeb` — **do not change native phone layouts** when fixing PC web unless user asks.
7. **Do not edit** `.cursor/plans/expo_cross-platform_app_5ce847c7.plan.md` (user rule).

---

## Woolworths connection flows

### PC / Expo web

- Header **Connect** → `api.woolworthsLogin()` → opens default browser, server imports cookies.
- **Before shop list build** (`recipes.tsx`): `WoolworthsWebConnectModal` if not connected (`needsWoolworthsSignInBeforeShop()`).
- Without connection, shop resolve runs in **offline mode** → all items `sku: "OFFLINE"` → **Manual** tab only.

CLI fallback on PC: `woolies login` or `meal-agent login`

### Mobile (Expo Go)

- **During meal plan generation** (`chef.tsx`): `ParallelLoadingModal` + `WoolworthsConnectPanel` WebView **in parallel** with OpenAI SSE (do not navigate away — kills SSE).
- Modal **stays open** after plan completes until user finishes sign-in or taps **Continue without Woolworths**.
- **Before shop list** (`recipes.tsx`): waits for WebView sign-in on mobile, then starts resolve SSE.
- **Add to cart** (`cart.tsx`): fallback connect if `isMobileWoolworthsLinked()` false (SecureStore flag set after successful `import-cookies`).
- PC API having cookies ≠ phone linked — mobile tracks `meal_agent_woolworths_mobile_linked` in SecureStore.

Cookie import: `POST /api/session/woolworths/import-cookies`  
- Saves cookies even if live check fails; returns `{ connected: false }` with message (no longer HTTP 400).  
- Mobile only sets linked flag when `connected: true`.

**Known limitation:** WebView `document.cookie` may miss HttpOnly session cookies → user may need multiple **I've signed in** attempts or PC browser login for reliable `is_live()`.

---

## UI work completed in chat

### Progress / loading

- `LoadingOverlay` — full-screen modal for long operations  
- `ParallelLoadingModal` — meal plan progress + Woolworths WebView (mobile)  
- SSE progress flushed with `requestAnimationFrame` on RN (`sse.ts`)

### Web layout (PC only)

- `lib/web-layout.ts` — max-width 560px centered column  
- `WizardShell` — centered header + content on web  
- `ActionBar` — centered actions on web; `row` prop for horizontal button groups  
- `StepNavBar` — duplicate nav at **top and bottom** on plan, recipes, shop  

### Navigation (latest)

- **Plan, recipes, shop:** back/forward buttons top **and** bottom  
- **Recipes:** Back + Build shop list **side by side** (`ActionBar row`)  
- **Shop back** → `/recipes` (not `/plan`)

### Bugs fixed

- Saved profile click: replaced dynamic import with static `profileToAnswers` import in `discovery.tsx`  
- Shop empty "Will add" tab: auto-switch to Manual when all OFFLINE; banners explain estimated items  
- Woolworths modal closing before sign-in done when meal plan finished — fixed via separate `woolworthsOpen` / `generating` state in `chef.tsx`

---

## Key files reference

```
apps/mobile/
  app/
    discovery.tsx    # Preferences, saved profiles
    chef.tsx         # Chef pick + generate plan + parallel WW login (mobile)
    plan.tsx         # Meal plan grid, approve
    recipes.tsx      # Recipes, build shop list, WW connect (web modal / mobile WebView)
    shop.tsx         # Shop list tabs: Will add / Blocked / Manual
    cart.tsx         # Add to cart
    connect-woolworths.tsx  # Full-screen WebView (mobile)
  components/
    WizardShell.tsx
    ParallelLoadingModal.tsx
    WoolworthsConnectPanel.tsx   # WebView + cookie harvest
    WoolworthsWebConnectModal.tsx  # PC browser login prompt
    StepNavBar.tsx
    ActionBar.tsx
    LoadingOverlay.tsx
  lib/
    config.ts              # getApiBaseUrl(), Woolworths URLs
    woolworths-mobile.ts   # needsWoolworthsSignInBeforeShop(), SecureStore linked flag
    woolworths-cookies.ts  # WOOLWORTHS_COOKIE_HARVEST_JS
    web-layout.ts          # Web-only centering
  metro.config.js
  context/AppProvider.tsx

packages/app-core/src/api/
  client.ts   # API client, import-cookies 60s timeout, clearer network errors
  sse.ts      # XHR SSE for React Native

apps/api/src/meal_agent_api/main.py
  POST /api/session/woolworths/import-cookies  # soft-fail if not live
  GET  /api/health
  CORS includes localhost:8081, 19006
```

---

## API / env

```powershell
# Optional override
$env:EXPO_PUBLIC_API_URL="http://127.0.0.1:8000"
$env:EXPO_PUBLIC_API_PORT="8000"   # used when inferring LAN URL in config.ts
```

Health check: `curl http://127.0.0.1:8000/api/health`

---

## Testing checklist

- [ ] API running on 8000, Expo on 8081/8082  
- [ ] PC web: centered layout, step nav top+bottom  
- [ ] PC web: Build shop list → Woolworths connect modal → browser login → items in **Will add**  
- [ ] Phone: Generate plan → Woolworths WebView stays open after plan ready  
- [ ] Phone: Build shop list after WW linked → live products  
- [ ] Saved profile tap loads without Metro module error  
- [ ] Add to cart opens connect if not linked  

---

## Likely next work / open issues

1. **HttpOnly cookies on mobile WebView** — may need dev client + native CookieManager for reliable mobile WW session, or proxy auth through API differently.  
2. **Chef step on PC web** — no parallel Woolworths prompt during plan gen on web (only at recipes); user may want browser connect during plan on web too.  
3. **Woolworths auto-harvest** disabled (`autoHarvest={false}`) — user must tap **I've signed in**; intentional to avoid premature failures.  
4. **`test_woolworths_smoke`** fails without live WW session — expected in CI without login.  
5. User sometimes runs API on non-default setup — always confirm `PC API:` line in Woolworths panel or `getApiBaseUrl()`.

---

## User preferences (from rules)

- **Do not commit** unless explicitly asked.  
- **Minimize scope** — match existing patterns; web-only changes via `Platform.OS === "web"`.  
- **PC testing** prefers Expo web or terminal QR flow, not opening browser unnecessarily when user wants terminal/Expo Go.  
- Clear error messages distinguishing API port 8000 vs Expo 8081/8082.

---

## Prompt template for new agent

```
I'm continuing work on woolworths-meal-agent (Expo mobile + FastAPI).
Read docs/AGENT_HANDOFF.md in the repo root for full context.
Repo path: C:\Users\marku\Projects\woolworths-meal-agent

Current focus: [describe your task]

Platform: [PC web / iPhone Expo Go / both]
```

---

## Chat transcript

Full JSONL transcript (if needed for deep context):  
`C:\Users\marku\.cursor\projects\c-Users-marku-Projects-globe-travel\agent-transcripts\c94d032e-9814-4fff-9ee1-76193bff79c2\c94d032e-9814-4fff-9ee1-76193bff79c2.jsonl`

Search keywords: `woolworths`, `ParallelLoadingModal`, `import-cookies`, `8080`, `shop list`, `manual`, `profileToAnswers`.
