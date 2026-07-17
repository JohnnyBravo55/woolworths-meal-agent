/* global chrome */
(function () {
  const api = typeof browser !== "undefined" ? browser : chrome;

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
  agentLog("H2", "content-script.js:boot", "content script loaded", {
    href: String(location.href || "").slice(0, 160),
  });
  // #endregion

  function readContext() {
    const ctx = globalThis.__MEAL_AGENT_CONNECT__;
    if (!ctx || !ctx.sessionId || !ctx.apiBase) return null;
    return {
      sessionId: ctx.sessionId,
      accessCode: ctx.accessCode || "",
      apiBase: ctx.apiBase,
    };
  }

  function publish() {
    const ctx = readContext();
    if (!ctx) return;
    agentLog("H2", "content-script.js:publish", "publishing connect context", {
      hasSessionId: true,
      apiHost: String(ctx.apiBase).replace(/^https?:\/\//, "").split("/")[0],
    });
    api.runtime.sendMessage({
      type: "meal-agent-set-context",
      sessionId: ctx.sessionId,
      accessCode: ctx.accessCode || "",
      apiBase: ctx.apiBase,
    });
  }

  api.runtime.onMessage.addListener((msg) => {
    if (msg?.type === "meal-agent-request-context") {
      const ctx = readContext();
      agentLog("H2", "content-script.js:request-context", "context requested", {
        hasContext: Boolean(ctx),
      });
      return Promise.resolve(ctx);
    }
    return undefined;
  });

  window.addEventListener("meal-agent-connect-context", publish);
  // Poll while the page may still be setting React context.
  let n = 0;
  const t = setInterval(() => {
    publish();
    n += 1;
    if (n > 60) clearInterval(t);
  }, 1000);
  publish();
})();
