/* global chrome */
const api = typeof browser !== "undefined" ? browser : chrome;

const statusEl = document.getElementById("status");
const btn = document.getElementById("connect");

async function refreshContextHint() {
  try {
    const res = await api.runtime.sendMessage({ type: "meal-agent-get-context" });
    if (res?.context?.sessionId) {
      statusEl.textContent = "Meal Agent session found. Sign in to Woolworths, then Connect.";
    } else {
      statusEl.textContent =
        "No Meal Agent session yet — open Connect Woolworths on the Meal Agent site first.";
    }
  } catch {
    statusEl.textContent = "Extension ready.";
  }
}

btn.addEventListener("click", async () => {
  btn.disabled = true;
  statusEl.textContent = "Connecting…";
  try {
    const result = await api.runtime.sendMessage({ type: "meal-agent-connect" });
    statusEl.textContent = result?.message || (result?.ok ? "Connected." : "Failed.");
  } catch (e) {
    statusEl.textContent = String(e);
  } finally {
    btn.disabled = false;
  }
});

void refreshContextHint();
