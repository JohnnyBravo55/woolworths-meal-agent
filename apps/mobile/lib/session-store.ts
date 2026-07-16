import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
import type { SessionStore } from "@meal-agent/app-core";
import { createMemorySessionStore, createWebSessionStore } from "@meal-agent/app-core";

const SESSION_KEY = "meal_agent_session";
const AUTH_KEY = "meal_agent_auth";

export function createNativeSessionStore(): SessionStore {
  if (Platform.OS === "web") {
    return createWebSessionStore();
  }
  return {
    async getSessionId() {
      return SecureStore.getItemAsync(SESSION_KEY);
    },
    async setSessionId(id) {
      await SecureStore.setItemAsync(SESSION_KEY, id);
    },
    async getAuthToken() {
      return SecureStore.getItemAsync(AUTH_KEY);
    },
    async setAuthToken(token) {
      await SecureStore.setItemAsync(AUTH_KEY, token);
    },
    async clearAuthToken() {
      await SecureStore.deleteItemAsync(AUTH_KEY);
    },
    async getAccessCode() {
      return null;
    },
    async setAccessCode() {
      /* native builds do not use the web access gate */
    },
    async clearAccessCode() {
      /* no-op */
    },
  };
}

export const sessionStore = createNativeSessionStore() ?? createMemorySessionStore();
