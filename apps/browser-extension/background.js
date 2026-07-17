/* global chrome */
const api = typeof browser !== "undefined" ? browser : chrome;

const STORAGE_KEY = "mealAgentConnect";
const LAST_RESULT_KEY = "mealAgentLastConnect";

// #region agent log
function agentLog(hypothesisId, location, message, data) {
  fetch("http://127.0.0.1:7535/ingest/04349bd7-e622-4496-81f8-918b91f745d5", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Debug-Session-Id": "52f095",
    },
    body: JSON.stringify({
      sessionId: "52f095",
      runId: "connect-pre2",
      hypothesisId,
      location,
      message,
      data: data || {},
      timestamp: Date.now(),
    }),
  }).catch(() => {});
}
// #endregion

async function getConnectContext() {
  const data = await api.storage.session.get(STORAGE_KEY).catch(() => ({}));
  if (data?.[STORAGE_KEY]?.sessionId) return data[STORAGE_KEY];
  const local = await api.storage.local.get(STORAGE_KEY).catch(() => ({}));
  return local?.[STORAGE_KEY] || null;
}

async function setConnectContext(ctx) {
  const payload = { [STORAGE_KEY]: ctx };
  try {
    await api.storage.session.set(payload);
  } catch {
    /* Safari / older Firefox may lack session storage */
  }
  await api.storage.local.set(payload);
}

async function saveLastResult(result) {
  const entry = {
    ok: Boolean(result?.ok),
    message: result?.message || (result?.ok ? "Connected." : "Failed."),
    at: Date.now(),
  };
  await api.storage.local.set({ [LAST_RESULT_KEY]: entry }).catch(() => {});
  try {
    await api.action.setBadgeText({ text: entry.ok ? "OK" : "!" });
    await api.action.setBadgeBackgroundColor({ color: entry.ok ? "#16a34a" : "#dc2626" });
  } catch {
    /* badge optional */
  }
  return entry;
}

function cookieToImportShape(c) {
  return {
    name: c.name,
    value: c.value,
    domain: c.domain || ".woolworths.co.nz",
    path: c.path || "/",
    expires: typeof c.expirationDate === "number" ? c.expirationDate : -1,
    httpOnly: Boolean(c.httpOnly),
    secure: Boolean(c.secure),
    sameSite: c.sameSite === "no_restriction" ? "None" : c.sameSite === "strict" ? "Strict" : "Lax",
  };
}

async function collectWoolworthsCookies() {
  const seen = new Map();
  for (const url of [
    "https://www.woolworths.co.nz/",
    "https://woolworths.co.nz/",
    "https://account.woolworths.co.nz/",
  ]) {
    const list = await api.cookies.getAll({ url });
    for (const c of list || []) {
      const key = `${c.domain}|${c.name}|${c.path || "/"}`;
      seen.set(key, cookieToImportShape(c));
    }
  }
  try {
    const all = await api.cookies.getAll({ domain: "woolworths.co.nz" });
    for (const c of all || []) {
      const key = `${c.domain}|${c.name}|${c.path || "/"}`;
      seen.set(key, cookieToImportShape(c));
    }
  } catch {
    /* Firefox domain filter differences */
  }
  return [...seen.values()];
}

function isMealAgentUrl(url) {
  if (!url) return false;
  return /github\.io/i.test(url) || /localhost|127\.0\.0\.1/i.test(url);
}

async function harvestContextFromOpenTabs() {
  let tabs = [];
  try {
    tabs = await api.tabs.query({});
  } catch (e) {
    agentLog("H2", "background.js:harvest:tabsError", "tabs.query failed", { error: String(e) });
    return null;
  }
  const candidates = (tabs || []).filter((t) => isMealAgentUrl(t.url));
  agentLog("H2", "background.js:harvest:scan", "scanning Meal Agent tabs", {
    tabCount: candidates.length,
    urls: candidates.map((t) => String(t.url || "").slice(0, 120)),
  });

  for (const tab of candidates) {
    if (!tab.id) continue;

    try {
      const res = await api.tabs.sendMessage(tab.id, { type: "meal-agent-request-context" });
      if (res?.sessionId && res?.apiBase) {
        const ctx = {
          sessionId: res.sessionId,
          accessCode: res.accessCode || "",
          apiBase: res.apiBase,
          updatedAt: Date.now(),
        };
        await setConnectContext(ctx);
        agentLog("H2", "background.js:harvest:contentScript", "context from content script", {
          apiHost: String(ctx.apiBase).replace(/^https?:\/\//, "").split("/")[0],
        });
        return ctx;
      }
    } catch {
      /* content script not injected yet */
    }

    if (!api.scripting?.executeScript) continue;
    try {
      const injected = await api.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => {
          const ctx = globalThis.__MEAL_AGENT_CONNECT__;
          return ctx && ctx.sessionId && ctx.apiBase
            ? {
                sessionId: ctx.sessionId,
                accessCode: ctx.accessCode || "",
                apiBase: ctx.apiBase,
              }
            : null;
        },
      });
      const ctx = injected?.[0]?.result;
      if (ctx?.sessionId && ctx?.apiBase) {
        const stored = { ...ctx, updatedAt: Date.now() };
        await setConnectContext(stored);
        agentLog("H2", "background.js:harvest:executeScript", "context from page window", {
          apiHost: String(ctx.apiBase).replace(/^https?:\/\//, "").split("/")[0],
        });
        return stored;
      }
    } catch (e) {
      agentLog("H2", "background.js:harvest:injectError", "executeScript failed", {
        error: String(e),
        url: String(tab.url || "").slice(0, 120),
      });
    }
  }
  return null;
}

async function resolveConnectContext() {
  let ctx = await getConnectContext();
  if (ctx?.sessionId && ctx?.apiBase) return ctx;
  return harvestContextFromOpenTabs();
}

async function connectWoolworths() {
  agentLog("H2", "background.js:connectWoolworths:start", "connectWoolworths entered", {
    apiNs: typeof browser !== "undefined" ? "browser" : "chrome",
  });

  const ctx = await resolveConnectContext();
  agentLog("H2", "background.js:connectWoolworths:context", "connect context loaded", {
    hasSessionId: Boolean(ctx?.sessionId),
    hasApiBase: Boolean(ctx?.apiBase),
    apiHost: ctx?.apiBase ? String(ctx.apiBase).replace(/^https?:\/\//, "").split("/")[0] : null,
  });

  if (!ctx?.sessionId || !ctx?.apiBase) {
    return saveLastResult({
      ok: false,
      message:
        "No Meal Agent session found. Open Connect Woolworths on the Meal Agent tab, refresh that tab, then click Connect here again.",
    });
  }

  const cookies = await collectWoolworthsCookies();
  agentLog("H3", "background.js:connectWoolworths:cookies", "woolworths cookies collected", {
    cookieCount: cookies.length,
  });
  if (!cookies.length) {
    return saveLastResult({
      ok: false,
      message: "No Woolworths cookies found — sign in at woolworths.co.nz in this browser first.",
    });
  }

  const headers = {
    "Content-Type": "application/json",
    "X-Session-Id": ctx.sessionId,
  };
  if (ctx.accessCode) headers["X-Access-Code"] = ctx.accessCode;

  const url = `${ctx.apiBase.replace(/\/$/, "")}/api/session/woolworths/import-cookies`;
  let res;
  try {
    res = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ cookies }),
    });
  } catch (e) {
    agentLog("H4", "background.js:connectWoolworths:fetchError", "import-cookies fetch threw", {
      error: String(e),
    });
    return saveLastResult({
      ok: false,
      message: `Could not reach Meal Agent API: ${e}`,
    });
  }

  const data = await res.json().catch(() => ({}));
  agentLog("H4", "background.js:connectWoolworths:response", "import-cookies response", {
    status: res.status,
    ok: res.ok,
    connected: Boolean(data?.connected),
    detailType: typeof data?.detail,
  });

  if (!res.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : data.detail
          ? JSON.stringify(data.detail)
          : `Import failed (${res.status})`;
    return saveLastResult({ ok: false, message: detail });
  }
  if (!data.connected) {
    return saveLastResult({
      ok: false,
      message:
        data.message ||
        "Cookies saved but not verified — finish Woolworths sign-in and retry.",
    });
  }
  return saveLastResult({
    ok: true,
    message: "Connected to Woolworths NZ. Return to Meal Agent and continue.",
  });
}

// Return Promises so Firefox browser.runtime.sendMessage resolves.
api.runtime.onMessage.addListener((msg) => {
  agentLog("H1", "background.js:onMessage", "message received", {
    type: msg?.type || null,
  });
  if (msg?.type === "meal-agent-set-context") {
    return setConnectContext({
      sessionId: msg.sessionId,
      accessCode: msg.accessCode || "",
      apiBase: msg.apiBase,
      updatedAt: Date.now(),
    }).then(() => ({ ok: true }));
  }
  if (msg?.type === "meal-agent-get-context") {
    return getConnectContext().then((ctx) => ({ ok: true, context: ctx }));
  }
  if (msg?.type === "meal-agent-get-last-result") {
    return api.storage.local.get(LAST_RESULT_KEY).then((data) => ({
      ok: true,
      last: data?.[LAST_RESULT_KEY] || null,
    }));
  }
  if (msg?.type === "meal-agent-connect") {
    return connectWoolworths()
      .then((result) => {
        agentLog("H1", "background.js:connect:reply", "returning connect result", {
          ok: Boolean(result?.ok),
          hasMessage: Boolean(result?.message),
        });
        return result;
      })
      .catch(async (e) =>
        saveLastResult({ ok: false, message: String(e) }),
      );
  }
  return undefined;
});
