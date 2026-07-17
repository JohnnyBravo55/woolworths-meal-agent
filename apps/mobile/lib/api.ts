import { createApiClient } from "@meal-agent/app-core";
import { Platform } from "react-native";
import { getApiBaseUrl, isHostedApiUrl } from "./config";
import { sessionStore } from "./session-store";

// Hosted Pages → Render is cross-origin; session uses X-Session-Id (not cookies).
// Avoid credentials:include on hosted — SameSite=Lax cookies from Render break in browsers.
export const api = createApiClient({
  baseUrl: getApiBaseUrl,
  sessionStore,
  useCredentials: Platform.OS === "web" && !isHostedApiUrl(getApiBaseUrl()),
});

export { getApiBaseUrl };
