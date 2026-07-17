# Woolworths Connect Extension Implementation Plan

> **For agentic workers:** Implement task-by-task. Steps use checkbox syntax.

**Goal:** Ship a sideloadable browser extension (Chrome, Edge, Firefox, Safari macOS) plus hosted connect UI with browser-detected install instructions.

**Architecture:** Shared MV3 WebExtension posts Woolworths cookies to existing `import-cookies` API; Meal Agent page exposes session context via content script; Safari wraps the same bundle in Xcode converter output / instructions.

**Tech Stack:** Manifest V3, vanilla JS (no bundler required), Expo web UI (React Native Web), existing FastAPI import endpoint.

## Global Constraints

- No store publishing in v1
- Do not log or display raw cookie values in the UI
- Keep bookmarklet/paste as Advanced fallback
- Safari iOS out of scope

---

## Task 1: Shared extension core

- [ ] Create `apps/browser-extension/` with background, content script, popup, icons, manifests
- [ ] Cookie harvest + import-cookies POST
- [ ] README install steps

## Task 2: Hosted UI

- [ ] Browser detect helper
- [ ] Publish `__MEAL_AGENT_CONNECT__` context for content script
- [ ] Rewrite `WoolworthsWebConnectModal` hosted path

## Task 3: Safari + packaging

- [ ] Build script for chromium/firefox zips into `apps/mobile/public/extension/`
- [ ] Safari macOS converter instructions / wrapper notes
- [ ] Update root README hosted connect section
