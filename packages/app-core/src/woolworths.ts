/** Woolworths NZ shop homepage — sign in via header link for full shop session. */
export const WOOLWORTHS_HOME_URL = "https://www.woolworths.co.nz/";

/** Direct account portal (alternate if homepage sign-in is awkward). */
export const WOOLWORTHS_ACCOUNT_URL = "https://account.woolworths.co.nz/";

/** Opens the shop homepage — user clicks Sign in (best cookie flow for trolley API). */
export const WOOLWORTHS_SIGN_IN_URL = WOOLWORTHS_HOME_URL;

export const WOOLWORTHS_WEBVIEW_URI = WOOLWORTHS_HOME_URL;

export function openWoolworthsSignIn(): Window | null {
  if (typeof window === "undefined") return null;
  return window.open(WOOLWORTHS_SIGN_IN_URL, "_blank", "noopener,noreferrer");
}

export function openWoolworthsAccount(): Window | null {
  if (typeof window === "undefined") return null;
  return window.open(WOOLWORTHS_ACCOUNT_URL, "_blank", "noopener,noreferrer");
}
