/* global chrome */
(function () {
  const api = typeof browser !== "undefined" ? browser : chrome;

  function publish() {
    const ctx = globalThis.__MEAL_AGENT_CONNECT__;
    if (!ctx || !ctx.sessionId || !ctx.apiBase) return;
    api.runtime.sendMessage({
      type: "meal-agent-set-context",
      sessionId: ctx.sessionId,
      accessCode: ctx.accessCode || "",
      apiBase: ctx.apiBase,
    });
  }

  window.addEventListener("meal-agent-connect-context", publish);
  // Poll briefly — React may set context after script load.
  let n = 0;
  const t = setInterval(() => {
    publish();
    n += 1;
    if (n > 30) clearInterval(t);
  }, 1000);
  publish();
})();
