/* global chrome */
const api = typeof browser !== "undefined" ? browser : chrome;

const statusEl = document.getElementById("status");
const btn = document.getElementById("connect");

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

function setStatus(text, kind) {
  statusEl.textContent = text;
  statusEl.dataset.kind = kind || "";
}

function sendMessage(msg) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const finish = (fn, value) => {
      if (settled) return;
      settled = true;
      fn(value);
    };
    try {
      const maybePromise = api.runtime.sendMessage(msg, (response) => {
        const err = api.runtime.lastError;
        if (err) {
          finish(reject, new Error(err.message));
          return;
        }
        finish(resolve, response);
      });
      if (maybePromise && typeof maybePromise.then === "function") {
        maybePromise.then((r) => finish(resolve, r)).catch((e) => finish(reject, e));
      }
    } catch (e) {
      finish(reject, e);
    }
  });
}

async function refreshContextHint() {
  try {
    const lastRes = await sendMessage({ type: "meal-agent-get-last-result" });
    if (lastRes?.last?.message) {
      setStatus(lastRes.last.message, lastRes.last.ok ? "ok" : "err");
      agentLog("H1", "popup.js:lastResult", "showing persisted last result", {
        ok: Boolean(lastRes.last.ok),
      });
      return;
    }
    const res = await sendMessage({ type: "meal-agent-get-context" });
    agentLog("H2", "popup.js:refreshContextHint", "get-context result", {
      hasContext: Boolean(res?.context?.sessionId),
      apiNs: typeof browser !== "undefined" ? "browser" : "chrome",
    });
    if (res?.context?.sessionId) {
      setStatus("Meal Agent session found. Sign in to Woolworths, then Connect.", "");
    } else {
      setStatus(
        "No Meal Agent session yet — open Connect Woolworths on the Meal Agent site, refresh that tab, then come back here.",
        "err",
      );
    }
  } catch (e) {
    agentLog("H1", "popup.js:refreshContextHint:error", "get-context failed", {
      error: String(e),
    });
    setStatus("Extension ready. Open Meal Agent Connect, then press Connect Woolworths.", "");
  }
}

btn.addEventListener("click", async () => {
  agentLog("H1", "popup.js:click", "Connect button clicked", {
    versionHint: "1.0.1",
  });
  btn.disabled = true;
  setStatus("Connecting… keep this popup open.", "");
  const timeoutMs = 25000;
  try {
    const result = await Promise.race([
      sendMessage({ type: "meal-agent-connect" }),
      new Promise((resolve) =>
        setTimeout(
          () =>
            resolve({
              ok: false,
              message:
                "Timed out — reload the temporary add-on, refresh the Meal Agent tab, and try Connect again.",
            }),
          timeoutMs,
        ),
      ),
    ]);
    agentLog("H1", "popup.js:click:result", "sendMessage resolved", {
      resultType: result === undefined ? "undefined" : typeof result,
      ok: result?.ok,
      messagePreview: result?.message ? String(result.message).slice(0, 160) : null,
    });
    setStatus(
      result?.message || (result?.ok ? "Connected." : "Failed — no details from background."),
      result?.ok ? "ok" : "err",
    );
  } catch (e) {
    agentLog("H1", "popup.js:click:error", "sendMessage rejected", { error: String(e) });
    setStatus(String(e), "err");
  } finally {
    btn.disabled = false;
  }
});

void refreshContextHint();
