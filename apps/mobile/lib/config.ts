import Constants from "expo-constants";
import { Platform } from "react-native";

function hostFromUri(uri: string): string | null {
  const cleaned = uri.replace(/^[a-z][a-z0-9+.-]*:\/\//i, "");
  const host = cleaned.split("/")[0]?.split(":")[0]?.trim();
  return host || null;
}

function isPrivateLanHost(host: string): boolean {
  return (
    /^192\.168\.\d{1,3}\.\d{1,3}$/.test(host) ||
    /^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(host) ||
    /^172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}$/.test(host)
  );
}

/** Dev-only: infer PC LAN IP from Expo Metro connection (Expo Go on phone). */
function getDevLanApiHost(): string | null {
  const uris: (string | undefined)[] = [
    Constants.expoConfig?.hostUri,
    Constants.expoGoConfig?.debuggerHost,
    (Constants.manifest as { debuggerHost?: string } | null)?.debuggerHost,
  ];
  for (const uri of uris) {
    if (!uri) continue;
    const host = hostFromUri(uri);
    if (host && isPrivateLanHost(host)) return host;
  }
  return null;
}

/** API port — defaults to 8000 (meal-agent-api). Expo Metro uses 8081/8082 separately. */
function getApiPort(): string {
  return process.env.EXPO_PUBLIC_API_PORT?.trim() || "8000";
}

/** True when the API URL points at a remote host (not this machine / LAN). */
export function isHostedApiUrl(url: string): boolean {
  try {
    const host = new URL(url).hostname;
    if (host === "localhost" || host === "127.0.0.1") return false;
    if (isPrivateLanHost(host)) return false;
    return true;
  } catch {
    return false;
  }
}

/** API base URL — EXPO_PUBLIC_API_URL, or auto LAN IP in Expo Go dev. */
export function getApiBaseUrl(): string {
  const port = getApiPort();
  const env = process.env.EXPO_PUBLIC_API_URL?.replace(/\/$/, "");

  // Hosted / production builds: always use the bake-in URL (never same-host:8000).
  if (env && isHostedApiUrl(env)) {
    return env;
  }

  if (Platform.OS === "web" && typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host === "localhost" || host === "127.0.0.1") {
      return env && !isHostedApiUrl(env) ? env : `http://127.0.0.1:${port}`;
    }
    // Non-local web without a hosted API URL — misconfigured deploy.
    if (env) return env;
    console.warn(
      "[meal-agent] EXPO_PUBLIC_API_URL missing on hosted web; falling back to relative origin (API will fail).",
    );
    return "";
  }

  const lanHost = getDevLanApiHost();
  if (lanHost) {
    return `http://${lanHost}:${port}`;
  }

  return env || `http://127.0.0.1:${port}`;
}

/** Woolworths NZ shop homepage — WebView loads this then auto-clicks Sign in. */
export const WOOLWORTHS_HOME = "https://www.woolworths.co.nz/";
/** @deprecated use WOOLWORTHS_ACCOUNT_URL from app-core */
export const WOOLWORTHS_MY_ACCOUNT = "https://account.woolworths.co.nz/";
export {
  WOOLWORTHS_ACCOUNT_URL,
  WOOLWORTHS_SIGN_IN_URL as WOOLWORTHS_SIGN_IN,
  WOOLWORTHS_WEBVIEW_URI,
} from "@meal-agent/app-core";

/** Mobile Safari UA — some sites block default WebView user agents. */
export const WOOLWORTHS_WEBVIEW_UA =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1";
