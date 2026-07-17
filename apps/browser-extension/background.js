/* global chrome */
const api = typeof browser !== "undefined" ? browser : chrome;

const WW_URL_PATTERNS = [
  "https://www.woolworths.co.nz/*",
  "https://woolworths.co.nz/*",
  "https://*.woolworths.co.nz/*",
];

const STORAGE_KEY = "mealAgentConnect";

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
  // Domain filter fallback
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

async function connectWoolworths() {
  const ctx = await getConnectContext();
  if (!ctx?.sessionId || !ctx?.apiBase) {
    return {
      ok: false,
      message:
        "Open the Meal Agent site, go to Connect Woolworths, then click Connect in this extension.",
    };
  }

  const cookies = await collectWoolworthsCookies();
  if (!cookies.length) {
    return {
      ok: false,
      message: "No Woolworths cookies found — sign in at woolworths.co.nz in this browser first.",
    };
  }

  const headers = {
    "Content-Type": "application/json",
    "X-Session-Id": ctx.sessionId,
  };
  if (ctx.accessCode) headers["X-Access-Code"] = ctx.accessCode;

  const res = await fetch(`${ctx.apiBase.replace(/\/$/, "")}/api/session/woolworths/import-cookies`, {
    method: "POST",
    headers,
    body: JSON.stringify({ cookies }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    return { ok: false, message: data.detail || `Import failed (${res.status})` };
  }
  if (!data.connected) {
    return {
      ok: false,
      message: data.message || "Cookies saved but not verified — finish Woolworths sign-in and retry.",
    };
  }
  return { ok: true, message: "Connected to Woolworths NZ. Return to Meal Agent and continue." };
}

api.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "meal-agent-set-context") {
    setConnectContext({
      sessionId: msg.sessionId,
      accessCode: msg.accessCode || "",
      apiBase: msg.apiBase,
      updatedAt: Date.now(),
    }).then(() => sendResponse({ ok: true }));
    return true;
  }
  if (msg?.type === "meal-agent-get-context") {
    getConnectContext().then((ctx) => sendResponse({ ok: true, context: ctx }));
    return true;
  }
  if (msg?.type === "meal-agent-connect") {
    connectWoolworths()
      .then((result) => sendResponse(result))
      .catch((e) => sendResponse({ ok: false, message: String(e) }));
    return true;
  }
  return false;
});

// Keep WW_URL_PATTERNS referenced for documentation / future tab helpers.
void WW_URL_PATTERNS;
