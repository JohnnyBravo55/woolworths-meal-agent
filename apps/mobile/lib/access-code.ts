import { Platform } from "react-native";
import { sessionStore } from "./session-store";

/** Hosted builds may bake a hint; the real gate is API MEAL_AGENT_ACCESS_CODE. */
export function accessGateEnabled(): boolean {
  if (Platform.OS !== "web") return false;
  const flag = process.env.EXPO_PUBLIC_ACCESS_GATE?.trim();
  if (flag === "0" || flag === "false") return false;
  if (flag === "1" || flag === "true") return true;
  // Auto-enable on non-local web hosts (GitHub Pages / Cloudflare Pages).
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  return host !== "localhost" && host !== "127.0.0.1";
}

export async function hasAccessCode(): Promise<boolean> {
  const code = sessionStore.getAccessCode ? await sessionStore.getAccessCode() : null;
  return Boolean(code?.trim());
}

export async function unlockAccessCode(code: string): Promise<void> {
  const trimmed = code.trim();
  if (!trimmed) throw new Error("Enter the access code");
  if (!sessionStore.setAccessCode) throw new Error("Access code storage unavailable");
  await sessionStore.setAccessCode(trimmed);
}
