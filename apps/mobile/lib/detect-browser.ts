export type DetectedBrowser = "chrome" | "edge" | "firefox" | "safari" | "other";

/** Best-effort UA detection for hosted connect install instructions (web only). */
export function detectBrowser(userAgent?: string): DetectedBrowser {
  const ua = userAgent ?? (typeof navigator !== "undefined" ? navigator.userAgent : "");
  if (!ua) return "other";
  if (/firefox|fxios/i.test(ua)) return "firefox";
  if (/edg\//i.test(ua)) return "edge";
  // iOS Chrome uses CriOS; desktop Chrome includes Chrome and not Safari-only.
  if (/chrome|chromium|crios/i.test(ua) && !/edg\//i.test(ua)) return "chrome";
  if (/safari/i.test(ua) && !/chrome|chromium|crios|android/i.test(ua)) return "safari";
  return "other";
}

export function browserLabel(browser: DetectedBrowser): string {
  switch (browser) {
    case "chrome":
      return "Chrome";
    case "edge":
      return "Edge";
    case "firefox":
      return "Firefox";
    case "safari":
      return "Safari";
    default:
      return "your browser";
  }
}
