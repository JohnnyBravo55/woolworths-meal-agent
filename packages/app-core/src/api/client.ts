import type {
  AppState,
  CartResult,
  ChefPersona,
  DiscoveryAnswers,
  MealPlan,
  ResolvedGroceryList,
  WoolworthsCookie,
} from "../types";
import type { SessionStore } from "./session-store";
import { isReactNative, streamSSEViaFetch, streamSSEViaXHR, type SSEHandler } from "./sse";

export type { SSEHandler };

export interface ApiClientConfig {
  baseUrl: string | (() => string);
  sessionStore: SessionStore;
  /** When true, also send cookies (web with same-origin proxy). */
  useCredentials?: boolean;
}

function parseApiError(body: unknown, statusText: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === "object" && item && "msg" in item
            ? String((item as { msg: string }).msg)
            : String(item),
        )
        .join("; ");
    }
  }
  return statusText;
}

function isHostedHttpUrl(url: string): boolean {
  try {
    const host = new URL(url).hostname;
    return host !== "localhost" && host !== "127.0.0.1" && !/^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host);
  } catch {
    return false;
  }
}

function unreachableApiMessage(url: string, kind: "timeout" | "network"): string {
  if (isHostedHttpUrl(url)) {
    return kind === "timeout"
      ? `Hosted API at ${url} timed out — Render free tier can take 30–60s to wake. Wait and retry.`
      : `Cannot reach hosted API at ${url} — check the Render service is live, then refresh and retry.`;
  }
  return kind === "timeout"
    ? `PC API not responding at ${url} — start meal-agent-api on port 8000 (Expo Metro uses 8081/8082, not the API).`
    : `Cannot reach PC API at ${url} — same Wi-Fi as your PC, API on port 8000.`;
}

export function createApiClient(config: ApiClientConfig) {
  const { baseUrl, sessionStore, useCredentials = false } = config;
  const base = () => {
    const url = typeof baseUrl === "function" ? baseUrl() : baseUrl;
    return url.replace(/\/$/, "");
  };

  async function authHeaders(): Promise<Record<string, string>> {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const sessionId = await sessionStore.getSessionId();
    if (sessionId) headers["X-Session-Id"] = sessionId;
    const authToken = await sessionStore.getAuthToken();
    if (authToken) headers["X-Auth-Token"] = authToken;
    const accessCode = sessionStore.getAccessCode
      ? await sessionStore.getAccessCode()
      : null;
    if (accessCode) headers["X-Access-Code"] = accessCode;
    return headers;
  }

  async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const controller = new AbortController();
    const url = base();
    // Render free cold-starts often exceed 15s; local stays snappy.
    const timeoutMs = isHostedHttpUrl(url) ? 60_000 : 15_000;
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const headers = await authHeaders();
      const res = await fetch(`${url}${path}`, {
        credentials: useCredentials ? "include" : "omit",
        headers: { ...headers, ...(init?.headers || {}) },
        ...init,
        signal: init?.signal ?? controller.signal,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(parseApiError(err, res.statusText));
      }
      return res.json();
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        throw new Error(unreachableApiMessage(url, "timeout"));
      }
      const msg = err instanceof Error ? err.message.toLowerCase() : "";
      if (
        err instanceof TypeError &&
        (msg.includes("network") || msg.includes("failed to fetch") || msg.includes("load failed"))
      ) {
        throw new Error(unreachableApiMessage(url, "network"));
      }
      throw err;
    } finally {
      clearTimeout(timeout);
    }
  }

  async function streamSSE(path: string, onEvent: SSEHandler, init?: RequestInit): Promise<void> {
    const headers = await authHeaders();
    const url = `${base()}${path}`;
    const mergedHeaders: Record<string, string> = {
      Accept: "text/event-stream",
      ...headers,
      ...(init?.headers as Record<string, string> | undefined),
    };

    if (isReactNative()) {
      await streamSSEViaXHR(url, mergedHeaders, onEvent, init?.body ?? null);
      return;
    }

    await streamSSEViaFetch(url, mergedHeaders, onEvent, {
      credentials: useCredentials ? "include" : "omit",
      ...init,
    });
  }

  return {
    getBaseUrl: () => base(),

    async startSession() {
      const res = await jsonFetch<{ session_id: string }>("/api/session/start", { method: "POST" });
      await sessionStore.setSessionId(res.session_id);
      return res;
    },

    getState: () => jsonFetch<AppState>("/api/session/state"),

    getHealth: () =>
      jsonFetch<{ status: string; openai_configured: boolean; openai_model: string }>(
        "/api/health",
      ),

    getWoolworthsStatus: () =>
      jsonFetch<{ connected: boolean; message: string }>("/api/session/woolworths/status"),

    listChefs: () =>
      jsonFetch<{ chefs: ChefPersona[]; premium_unlocked: boolean }>("/api/chefs"),

    getAuthMe: () =>
      jsonFetch<{
        authenticated: boolean;
        is_subscriber?: boolean;
        premium_unlocked?: boolean;
        email?: string;
      }>("/api/auth/me"),

    woolworthsLogin: async (opts?: { openBrowser?: boolean; timeoutSeconds?: number }) => {
      const controller = new AbortController();
      const timeoutMs = Math.max(30_000, ((opts?.timeoutSeconds ?? 300) + 30) * 1000);
      const timeout = setTimeout(() => controller.abort(), timeoutMs);
      try {
        return await jsonFetch<{ connected: boolean; message: string }>(
          "/api/session/woolworths/login",
          {
            method: "POST",
            body: JSON.stringify({
              open_browser: opts?.openBrowser ?? true,
              timeout_seconds: opts?.timeoutSeconds ?? 300,
            }),
            signal: controller.signal,
          },
        );
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          throw new Error("Connect timed out — complete sign-in on woolworths.co.nz and try again.");
        }
        throw err;
      } finally {
        clearTimeout(timeout);
      }
    },

    woolworthsSync: async () => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 45_000);
      try {
        return await jsonFetch<{ connected: boolean; message: string }>(
          "/api/session/woolworths/sync",
          {
            method: "POST",
            signal: controller.signal,
          },
        );
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          throw new Error(
            isHostedHttpUrl(base())
              ? "Checking Woolworths sign-in timed out — retry in a moment (hosted API may be waking)."
              : "Checking sign-in timed out — make sure meal-agent-api is running on port 8000.",
          );
        }
        throw err;
      } finally {
        clearTimeout(timeout);
      }
    },

    importWoolworthsCookies: async (cookies: WoolworthsCookie[]) => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 60_000);
      try {
        const headers = await authHeaders();
        const res = await fetch(`${base()}/api/session/woolworths/import-cookies`, {
          method: "POST",
          credentials: useCredentials ? "include" : "omit",
          headers,
          body: JSON.stringify({ cookies }),
          signal: controller.signal,
        });
        if (!res.ok) {
          const err = await res.json().catch(() => null);
          throw new Error(parseApiError(err, res.statusText));
        }
        return res.json() as Promise<{ connected: boolean; message: string }>;
      } catch (err) {
        if (err instanceof Error && err.name === "AbortError") {
          throw new Error(unreachableApiMessage(base(), "timeout"));
        }
        throw err;
      } finally {
        clearTimeout(timeout);
      }
    },

    woolworthsDisconnect: () =>
      jsonFetch<{ connected: boolean; message: string }>("/api/session/woolworths/disconnect", {
        method: "POST",
      }),

    listProfiles: () => jsonFetch<{ profiles: { id: string; name: string }[] }>("/api/profiles"),

    loadProfile: (id: string) => jsonFetch<Record<string, unknown>>(`/api/profiles/${id}`),

    saveProfile: (name: string, answers: DiscoveryAnswers) =>
      jsonFetch("/api/profiles", {
        method: "POST",
        body: JSON.stringify({ name, answers }),
      }),

    setProfile: (answers: DiscoveryAnswers) =>
      jsonFetch("/api/profile", {
        method: "POST",
        body: JSON.stringify(answers),
      }),

    getPlan: () => jsonFetch<{ meal_plan: MealPlan }>("/api/plan"),

    approvePlan: () =>
      jsonFetch<{ meals: unknown[]; dinners: unknown[]; state: AppState }>("/api/plan/approve", {
        method: "POST",
      }),

    swapMeal: (mealIndex: number) =>
      jsonFetch<{ meal_plan: MealPlan; state: AppState }>("/api/plan/swap", {
        method: "POST",
        body: JSON.stringify({ meal_index: mealIndex }),
      }),

    regeneratePlan: () =>
      jsonFetch<{ meal_plan: MealPlan; state: AppState }>("/api/plan/regenerate", {
        method: "POST",
      }),

    approveShop: () => jsonFetch<{ state: AppState }>("/api/shop/approve", { method: "POST" }),

    addToCart: (opts: { allow_over_budget?: boolean; export_only?: boolean }) =>
      jsonFetch<CartResult>("/api/cart/add-after-approve", {
        method: "POST",
        body: JSON.stringify({
          allow_over_budget: opts.allow_over_budget ?? false,
          export_only: opts.export_only ?? false,
        }),
      }),

    retryCart: () => jsonFetch<CartResult>("/api/cart/retry", { method: "POST" }),

    getCartUrl: () => jsonFetch<{ url: string; url_alt?: string }>("/api/cart/url"),

    authRegister: (email: string, password: string) =>
      jsonFetch("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),

    authLogin: async (email: string, password: string) => {
      const res = await jsonFetch<{ token?: string }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      if (res.token) await sessionStore.setAuthToken(res.token);
      return res;
    },

    authLogout: async () => {
      await jsonFetch("/api/auth/logout", { method: "POST" });
      await sessionStore.clearAuthToken();
    },

    acceptNda: (opts: { full_name: string; agreed: boolean; nda_version: string }) =>
      jsonFetch<{
        ok: boolean;
        id: string;
        full_name: string;
        nda_version: string;
        accepted_at: string;
      }>("/api/nda/accept", {
        method: "POST",
        body: JSON.stringify({
          full_name: opts.full_name,
          agreed: opts.agreed,
          nda_version: opts.nda_version,
        }),
      }),

    submitFeedback: (opts: {
      meal_plan_useful: string;
      most_valuable: string;
      use_again: string;
      if_never_public: string;
      premium_subscribe: string;
      improve?: string;
      session_id?: string;
    }) =>
      jsonFetch<{
        ok: boolean;
        id: string;
        submitted_at: string;
      }>("/api/feedback/submit", {
        method: "POST",
        body: JSON.stringify({
          meal_plan_useful: opts.meal_plan_useful,
          most_valuable: opts.most_valuable,
          use_again: opts.use_again,
          if_never_public: opts.if_never_public,
          premium_subscribe: opts.premium_subscribe,
          improve: opts.improve ?? "",
          session_id: opts.session_id ?? "",
        }),
      }),

    exportCsvUrl: () => `${base()}/api/export/csv`,
    exportMarkdownUrl: () => `${base()}/api/export/markdown`,

    async downloadRecipes(platform: "web" | "native" = "web") {
      const headers = await authHeaders();
      const res = await fetch(`${base()}/api/plan/recipes/download`, {
        credentials: useCredentials ? "include" : "omit",
        headers,
      });
      if (!res.ok) throw new Error(`Download failed: ${res.statusText}`);
      const blob = await res.blob();
      if (platform === "web" && typeof document !== "undefined") {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "recipes.md";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        return;
      }
      return blob;
    },

    streamSSE,
    streamCartAdd: (onEvent: SSEHandler, opts: { allow_over_budget?: boolean } = {}) =>
      streamSSE(
        "/api/cart/add-stream",
        onEvent,
        {
          method: "POST",
          body: JSON.stringify({
            allow_over_budget: opts.allow_over_budget ?? false,
            export_only: false,
          }),
        },
      ),

    computeAddableTotal(list: ResolvedGroceryList): number {
      return list.items
        .filter((i) => i.sku !== "OFFLINE" && i.in_stock && !i.cart_blocked)
        .reduce((s, i) => s + i.line_total, 0);
    },

    computeOfflineTotal(list: ResolvedGroceryList): number {
      return list.items
        .filter((i) => i.sku === "OFFLINE")
        .reduce((s, i) => s + i.line_total, 0);
    },
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;
