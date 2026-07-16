import type { WoolworthsCookie } from "@meal-agent/app-core";

/** Injected into Woolworths WebView — reads document.cookie (Expo Go compatible). */
export const WOOLWORTHS_COOKIE_HARVEST_JS = `
(function () {
  try {
    window.ReactNativeWebView.postMessage(
      JSON.stringify({ type: "cookies", raw: document.cookie || "", url: location.href })
    );
  } catch (e) {
    window.ReactNativeWebView.postMessage(
      JSON.stringify({ type: "error", message: String(e) })
    );
  }
})();
true;
`;

/** On Woolworths homepage, try to open the sign-in / account flow. */
export const WOOLWORTHS_SIGN_IN_CLICK_JS = `
(function () {
  try {
    const path = (location.pathname || "").toLowerCase();
    if (path.includes("myaccount") || path.includes("signin") || path.includes("login")) return;
    const nodes = [...document.querySelectorAll("a, button, [role='button']")];
    const hit = nodes.find((el) => {
      const t = (el.textContent || el.getAttribute("aria-label") || "").trim().toLowerCase();
      return /sign in|log in|login|my account|account/.test(t);
    });
    if (hit) hit.click();
  } catch (e) { /* ignore */ }
})();
true;
`;

export function parseDocumentCookies(
  raw: string,
  domain = ".woolworths.co.nz",
): WoolworthsCookie[] {
  if (!raw.trim()) return [];
  return raw
    .split(";")
    .map((pair) => {
      const trimmed = pair.trim();
      if (!trimmed) return null;
      const eq = trimmed.indexOf("=");
      if (eq <= 0) return null;
      const name = trimmed.slice(0, eq).trim();
      const value = trimmed.slice(eq + 1);
      if (!name) return null;
      let decoded = value;
      try {
        decoded = decodeURIComponent(value);
      } catch {
        /* keep raw */
      }
      return {
        name,
        value: decoded,
        domain,
        path: "/",
        expires: -1,
        httpOnly: false,
        secure: true,
        sameSite: "Lax",
      } as WoolworthsCookie;
    })
    .filter((c): c is WoolworthsCookie => c !== null);
}

export type CookieHarvestMessage =
  | { type: "cookies"; raw: string; url: string }
  | { type: "error"; message: string };

export function parseCookieHarvestMessage(data: string): CookieHarvestMessage | null {
  try {
    const parsed = JSON.parse(data) as CookieHarvestMessage;
    if (parsed?.type === "cookies" || parsed?.type === "error") return parsed;
  } catch {
    /* ignore */
  }
  return null;
}
