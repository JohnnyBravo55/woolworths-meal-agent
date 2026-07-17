import { Platform } from "react-native";
import { getApiBaseUrl } from "./config";
import { sessionStore } from "./session-store";

export type MealAgentConnectContext = {
  sessionId: string;
  accessCode: string;
  apiBase: string;
};

declare global {
  interface Window {
    __MEAL_AGENT_CONNECT__?: MealAgentConnectContext;
  }
}

/** Publish session context for the browser-extension content script (web only). */
export async function publishExtensionConnectContext(): Promise<MealAgentConnectContext | null> {
  if (Platform.OS !== "web" || typeof window === "undefined") return null;

  let sessionId = await sessionStore.getSessionId();
  if (!sessionId) return null;

  const accessCode = sessionStore.getAccessCode ? (await sessionStore.getAccessCode()) || "" : "";
  const apiBase = getApiBaseUrl().replace(/\/$/, "");
  if (!apiBase) return null;

  const ctx: MealAgentConnectContext = { sessionId, accessCode, apiBase };
  window.__MEAL_AGENT_CONNECT__ = ctx;
  window.dispatchEvent(new CustomEvent("meal-agent-connect-context"));
  return ctx;
}

export function clearExtensionConnectContext(): void {
  if (Platform.OS !== "web" || typeof window === "undefined") return;
  delete window.__MEAL_AGENT_CONNECT__;
}

/** Public URL for packaged extension zips (served from Expo `public/extension`). */
export function extensionDownloadUrl(kind: "chromium" | "firefox"): string {
  const file =
    kind === "firefox"
      ? "meal-agent-connect-firefox.zip"
      : "meal-agent-connect-chromium.zip";
  if (typeof window === "undefined") return `/extension/${file}`;
  const base = (process.env.EXPO_PUBLIC_BASE_URL || "").replace(/\/$/, "");
  const origin = window.location.origin;
  return `${origin}${base}/extension/${file}`;
}
