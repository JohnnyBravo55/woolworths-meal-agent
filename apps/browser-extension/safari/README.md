# Safari (macOS) wrapper

Safari does not load unpacked WebExtensions like Chrome/Firefox. On a Mac:

1. Copy `manifest.chromium.json` to `manifest.json` in `apps/browser-extension/`.
2. Run:

```bash
cd apps/browser-extension
xcrun safari-web-extension-converter . \
  --project-location ./safari/MealAgentConnect \
  --app-name "Meal Agent Connect" \
  --bundle-identifier "local.mealagent.connect" \
  --force
```

3. Open the generated `.xcodeproj` in Xcode, select the macOS app target, Run (⌘R).
4. Safari → Settings → Extensions → enable **Meal Agent Connect**.
5. If needed: Safari → Develop → Allow Unsigned Extensions.

iOS Safari is out of scope for v1 (App Store packaging required).
