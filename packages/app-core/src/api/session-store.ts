/** Pluggable session/auth token storage (SecureStore on native, memory/localStorage on web). */

export interface SessionStore {
  getSessionId(): Promise<string | null>;
  setSessionId(id: string): Promise<void>;
  getAuthToken(): Promise<string | null>;
  setAuthToken(token: string): Promise<void>;
  clearAuthToken(): Promise<void>;
  /** Shared tester access code (optional; sent as X-Access-Code when set). */
  getAccessCode?(): Promise<string | null>;
  setAccessCode?(code: string): Promise<void>;
  clearAccessCode?(): Promise<void>;
}

let memorySessionId: string | null = null;
let memoryAuthToken: string | null = null;
let memoryAccessCode: string | null = null;

export function createMemorySessionStore(): SessionStore {
  return {
    async getSessionId() {
      return memorySessionId;
    },
    async setSessionId(id) {
      memorySessionId = id;
    },
    async getAuthToken() {
      return memoryAuthToken;
    },
    async setAuthToken(token) {
      memoryAuthToken = token;
    },
    async clearAuthToken() {
      memoryAuthToken = null;
    },
    async getAccessCode() {
      return memoryAccessCode;
    },
    async setAccessCode(code) {
      memoryAccessCode = code;
    },
    async clearAccessCode() {
      memoryAccessCode = null;
    },
  };
}

const SESSION_KEY = "meal_agent_session";
const AUTH_KEY = "meal_agent_auth";
/** Tab-scoped so closing the tab clears the tester unlock. */
const ACCESS_CODE_KEY = "meal_agent_access_code";

export function createWebSessionStore(): SessionStore {
  return {
    async getSessionId() {
      if (typeof localStorage === "undefined") return memorySessionId;
      return localStorage.getItem(SESSION_KEY) ?? memorySessionId;
    },
    async setSessionId(id) {
      memorySessionId = id;
      if (typeof localStorage !== "undefined") localStorage.setItem(SESSION_KEY, id);
    },
    async getAuthToken() {
      if (typeof localStorage === "undefined") return memoryAuthToken;
      return localStorage.getItem(AUTH_KEY) ?? memoryAuthToken;
    },
    async setAuthToken(token) {
      memoryAuthToken = token;
      if (typeof localStorage !== "undefined") localStorage.setItem(AUTH_KEY, token);
    },
    async clearAuthToken() {
      memoryAuthToken = null;
      if (typeof localStorage !== "undefined") localStorage.removeItem(AUTH_KEY);
    },
    async getAccessCode() {
      if (typeof sessionStorage !== "undefined") {
        return sessionStorage.getItem(ACCESS_CODE_KEY) ?? memoryAccessCode;
      }
      return memoryAccessCode;
    },
    async setAccessCode(code) {
      memoryAccessCode = code;
      if (typeof sessionStorage !== "undefined") {
        sessionStorage.setItem(ACCESS_CODE_KEY, code);
      }
    },
    async clearAccessCode() {
      memoryAccessCode = null;
      if (typeof sessionStorage !== "undefined") {
        sessionStorage.removeItem(ACCESS_CODE_KEY);
      }
    },
  };
}
