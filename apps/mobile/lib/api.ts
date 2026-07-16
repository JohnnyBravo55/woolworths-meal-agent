import { createApiClient } from "@meal-agent/app-core";
import { Platform } from "react-native";
import { getApiBaseUrl } from "./config";
import { sessionStore } from "./session-store";

export const api = createApiClient({
  baseUrl: getApiBaseUrl,
  sessionStore,
  useCredentials: Platform.OS === "web",
});

export { getApiBaseUrl };
