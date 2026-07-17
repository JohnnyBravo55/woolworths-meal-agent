# Woolworths connect browser extension (hosted)

**Date:** 2026-07-17  
**Status:** Approved for implementation

## Goal

Let hosted Meal Agent testers connect their Woolworths NZ session with **one click** after a one-time extension install, instead of bookmarklet/cookie paste.

## Browsers (v1)

| Browser | Packaging | Tester install |
|---------|-----------|----------------|
| Chrome | MV3 WebExtension zip / folder | Load unpacked |
| Edge | Same as Chrome | Load unpacked |
| Firefox | MV3 WebExtension (+ gecko id) | Load temporary add-on / from file |
| Safari (macOS) | Same JS + Xcode Safari Web Extension wrapper | Allow Unsigned Extensions / run app |
| Safari iOS | Out of scope | App Store later |

## Architecture

1. Shared extension under `apps/browser-extension/`.
2. Content script on Meal Agent origins publishes `{ sessionId, accessCode, apiBase }` into extension storage while the connect UI is open.
3. Toolbar action / popup **Connect** reads `*.woolworths.co.nz` cookies via the `cookies` API (includes HttpOnly).
4. Background POSTs to existing `POST /api/session/woolworths/import-cookies` with `X-Session-Id` + `X-Access-Code`.
5. Hosted UI polls `/api/session/woolworths/status` until connected.

## Hosted UI

- Detect browser (Chrome / Edge / Firefox / Safari / other).
- Show **only that browser’s** install steps by default; link to “Other browsers”.
- Primary CTA: download extension package + Connect instructions.
- Bookmarklet / paste remain under **Advanced**.

## Non-goals (v1)

- Chrome Web Store / AMO / Mac App Store listing
- Auto-connect with zero toolbar click
- Changing local PC `browser_cookie3` flow
- iOS Safari

## Acceptance

1. Fresh Chrome/Edge/Firefox (and Safari on Mac) can install from repo instructions.
2. Hosted connect page shows correct browser-specific steps.
3. After sign-in on Woolworths + one extension Connect click, Meal Agent shows Connected.
4. Paste/bookmarklet still work as fallback.
