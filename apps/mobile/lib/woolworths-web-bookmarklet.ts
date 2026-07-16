import type { WoolworthsCookie } from "@meal-agent/app-core";
import { getApiBaseUrl } from "./config";

/**
 * Build a bookmarklet that runs on woolworths.co.nz (same origin as document.cookie)
 * and POSTs harvested cookies to our API. Used when Expo web cannot read iframe cookies.
 */
export function buildWoolworthsCookieBookmarklet(opts: {
  sessionId: string;
  accessCode?: string | null;
}): string {
  const apiBase = getApiBaseUrl().replace(/\/$/, "");
  const payload = JSON.stringify({
    apiBase,
    sessionId: opts.sessionId,
    accessCode: opts.accessCode || "",
  });

  const body = `
(async function(){
  var cfg = ${payload};
  if (!/woolworths\\.co\\.nz$/i.test(location.hostname) && location.hostname.indexOf("woolworths.co.nz") < 0) {
    alert("Open this bookmarklet on woolworths.co.nz after you sign in.");
    return;
  }
  var raw = document.cookie || "";
  if (!raw.trim()) {
    alert("No cookies found — finish signing in on Woolworths, then try again.");
    return;
  }
  var cookies = raw.split(";").map(function(pair){
    var t = pair.trim();
    var eq = t.indexOf("=");
    if (eq <= 0) return null;
    return {
      name: t.slice(0, eq).trim(),
      value: decodeURIComponent(t.slice(eq + 1)),
      domain: ".woolworths.co.nz",
      path: "/",
      expires: -1,
      httpOnly: false,
      secure: true,
      sameSite: "Lax"
    };
  }).filter(Boolean);
  var headers = {
    "Content-Type": "application/json",
    "X-Session-Id": cfg.sessionId
  };
  if (cfg.accessCode) headers["X-Access-Code"] = cfg.accessCode;
  try {
    var res = await fetch(cfg.apiBase + "/api/session/woolworths/import-cookies", {
      method: "POST",
      headers: headers,
      body: JSON.stringify({ cookies: cookies })
    });
    var data = await res.json().catch(function(){ return {}; });
    if (!res.ok) {
      alert(data.detail || ("Import failed (" + res.status + ")"));
      return;
    }
    if (data.connected) {
      alert("Connected — return to the Meal Agent tab and continue.");
    } else {
      alert(data.message || "Not connected yet — finish sign-in and retry.");
    }
  } catch (e) {
    alert("Could not reach Meal Agent API: " + e);
  }
})();
`.replace(/\s+/g, " ").trim();

  return `javascript:${encodeURIComponent(body)}`;
}

export function parseCookiesFromRawHeader(
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
