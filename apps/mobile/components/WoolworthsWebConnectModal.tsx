import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Linking,
  Modal,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { openWoolworthsSignIn, WOOLWORTHS_SIGN_IN_URL } from "@meal-agent/app-core";
import { Button } from "@/components/ui/Button";
import { theme } from "@/constants/theme";
import { api, getApiBaseUrl } from "@/lib/api";
import { isHostedApiUrl } from "@/lib/config";
import { browserLabel, detectBrowser, type DetectedBrowser } from "@/lib/detect-browser";
import {
  clearExtensionConnectContext,
  extensionDownloadUrl,
  publishExtensionConnectContext,
} from "@/lib/extension-connect";
import { sessionStore } from "@/lib/session-store";
import {
  buildWoolworthsCookieBookmarklet,
  parseCookiesFromRawHeader,
} from "@/lib/woolworths-web-bookmarklet";

function installSteps(browser: DetectedBrowser): string[] {
  switch (browser) {
    case "chrome":
      return [
        "Download the Chrome/Edge extension zip and unzip it.",
        "Open chrome://extensions and turn on Developer mode.",
        "Click Load unpacked and select the unzipped folder.",
        "Sign in on woolworths.co.nz, then click the Meal Agent extension → Connect Woolworths.",
      ];
    case "edge":
      return [
        "Download the Chrome/Edge extension zip and unzip it.",
        "Open edge://extensions and turn on Developer mode.",
        "Click Load unpacked and select the unzipped folder.",
        "Sign in on woolworths.co.nz, then click the Meal Agent extension → Connect Woolworths.",
      ];
    case "firefox":
      return [
        "Download the Firefox extension zip and unzip it.",
        "Open about:debugging#/runtime/this-firefox",
        "Click Load Temporary Add-on… and choose manifest.json in the unzipped folder.",
        "Sign in on woolworths.co.nz, then click the Meal Agent extension → Connect Woolworths.",
        "Note: Firefox temporary add-ons are removed when the browser restarts — reload after restart.",
      ];
    case "safari":
      return [
        "Safari needs a one-time Mac setup (Xcode). On a Mac, follow apps/browser-extension/safari/README.md in the repo.",
        "Run the Meal Agent Connect app from Xcode, then enable the extension in Safari → Settings → Extensions.",
        "Allow Unsigned Extensions under Safari → Develop if prompted.",
        "Sign in on woolworths.co.nz, then click the Meal Agent extension → Connect Woolworths.",
      ];
    default:
      return [
        "Use Chrome, Edge, or Firefox for the easiest install (download links below).",
        "Safari on Mac is supported via the Xcode wrapper in the repo.",
        "After installing, sign in on woolworths.co.nz and click Connect Woolworths in the extension.",
      ];
  }
}

/**
 * PC / Expo web Woolworths connect.
 * - Local API: open browser + server-side cookie import.
 * - Hosted API: browser extension (primary) + bookmarklet/paste advanced fallback.
 */
export function WoolworthsWebConnectModal({
  visible,
  onConnected,
  onError,
  onCancel,
}: {
  visible: boolean;
  onConnected: () => void;
  onError: (message: string) => void;
  onCancel: () => void;
}) {
  const hosted = isHostedApiUrl(getApiBaseUrl());
  const browser = useMemo(() => detectBrowser(), []);
  const [paste, setPaste] = useState("");
  const [busy, setBusy] = useState(false);
  const [bookmarkletHint, setBookmarkletHint] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showOtherBrowsers, setShowOtherBrowsers] = useState(false);
  const [waitingExtension, setWaitingExtension] = useState(false);

  useEffect(() => {
    if (!visible || !hosted || Platform.OS !== "web") return;
    let cancelled = false;
    const tick = async () => {
      try {
        await api.startSession().catch(() => undefined);
        if (!cancelled) await publishExtensionConnectContext();
      } catch {
        /* ignore */
      }
    };
    void tick();
    const publishTimer = setInterval(() => void tick(), 2000);
    return () => {
      cancelled = true;
      clearInterval(publishTimer);
      clearExtensionConnectContext();
    };
  }, [visible, hosted]);

  useEffect(() => {
    if (!visible || !hosted || !waitingExtension) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const status = await api.getWoolworthsStatus();
        if (!cancelled && status.connected) {
          setWaitingExtension(false);
          onConnected();
        }
      } catch {
        /* keep polling */
      }
    };
    void poll();
    const t = setInterval(() => void poll(), 2500);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [visible, hosted, waitingExtension, onConnected]);

  const runLocalLogin = useCallback(async () => {
    try {
      openWoolworthsSignIn();
      const res = await api.woolworthsLogin({ openBrowser: false });
      if (res.connected) {
        onConnected();
        return;
      }
      const status = await api.getWoolworthsStatus();
      if (status.connected) {
        onConnected();
        return;
      }
      onError("Sign-in finished but Woolworths is not connected yet — try again.");
    } catch (e) {
      onError(e instanceof Error ? e.message : "Woolworths sign-in failed");
    }
  }, [onConnected, onError]);

  const verifyLocal = useCallback(async () => {
    try {
      const res = await api.woolworthsSync();
      if (res.connected) {
        onConnected();
        return;
      }
      onError(res.message || "Not connected yet — complete Woolworths sign-in and try again.");
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not check Woolworths status");
    }
  }, [onConnected, onError]);

  const openDownload = useCallback(async (kind: "chromium" | "firefox") => {
    const url = extensionDownloadUrl(kind);
    try {
      await Linking.openURL(url);
    } catch {
      onError(`Could not open download link: ${url}`);
    }
  }, [onError]);

  const openWoolworthsAndWait = useCallback(async () => {
    setBusy(true);
    try {
      await api.startSession().catch(() => undefined);
      await publishExtensionConnectContext();
      openWoolworthsSignIn();
      setWaitingExtension(true);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not prepare connect");
    } finally {
      setBusy(false);
    }
  }, [onError]);

  const checkStatus = useCallback(async () => {
    setBusy(true);
    try {
      const status = await api.getWoolworthsStatus();
      if (status.connected) {
        onConnected();
        return;
      }
      onError(
        status.message ||
          "Not connected yet — finish Woolworths sign-in, then click Connect in the Meal Agent extension.",
      );
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not check Woolworths status");
    } finally {
      setBusy(false);
    }
  }, [onConnected, onError]);

  const copyBookmarklet = useCallback(async () => {
    setBusy(true);
    setBookmarkletHint("");
    try {
      let sessionId = await sessionStore.getSessionId();
      if (!sessionId) {
        await api.startSession();
        sessionId = await sessionStore.getSessionId();
      }
      if (!sessionId) {
        onError("No session yet — refresh and try again.");
        return;
      }
      const accessCode = sessionStore.getAccessCode
        ? await sessionStore.getAccessCode()
        : null;
      const href = buildWoolworthsCookieBookmarklet({ sessionId, accessCode });
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(href);
        setBookmarkletHint(
          "Bookmarklet copied. On woolworths.co.nz (after sign-in), paste it into the address bar and press Enter.",
        );
      } else {
        setBookmarkletHint(href);
      }
      openWoolworthsSignIn();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not build bookmarklet");
    } finally {
      setBusy(false);
    }
  }, [onError]);

  const importPasted = useCallback(async () => {
    setBusy(true);
    try {
      const list = parseCookiesFromRawHeader(paste);
      if (list.length < 1) {
        onError("Paste the Cookie header value from Woolworths DevTools (Application → Cookies).");
        return;
      }
      const res = await api.importWoolworthsCookies(list);
      if (!res.connected) {
        onError(res.message || "Import did not connect — check you pasted a signed-in session.");
        return;
      }
      onConnected();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Cookie import failed");
    } finally {
      setBusy(false);
    }
  }, [onConnected, onError, paste]);

  if (Platform.OS !== "web") return null;

  const steps = installSteps(browser);
  const label = browserLabel(browser);
  const primaryZip: "chromium" | "firefox" = browser === "firefox" ? "firefox" : "chromium";

  return (
    <Modal visible={visible} transparent animationType="fade">
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <ScrollView contentContainerStyle={styles.scroll}>
            <Text style={styles.title}>Connect Woolworths</Text>
            {hosted ? (
              <>
                <Text style={styles.message}>
                  Install the Meal Agent browser extension once, sign in to Woolworths, then connect
                  with one click.
                </Text>
                <Text style={styles.browserBadge}>Detected: {label}</Text>
                <Text style={styles.sectionTitle}>Set up in {label}</Text>
                {steps.map((step, i) => (
                  <Text key={step} style={styles.step}>
                    {i + 1}. {step}
                  </Text>
                ))}

                {browser === "safari" ? (
                  <Text style={styles.hint}>
                    Safari cannot use a simple zip install. Use the Mac/Xcode steps in the repo, or
                    switch to Chrome/Edge/Firefox for the quick path.
                  </Text>
                ) : (
                  <View style={styles.actions}>
                    <Button
                      title={
                        busy
                          ? "Working…"
                          : `Download extension for ${browser === "firefox" ? "Firefox" : "Chrome/Edge"}`
                      }
                      onPress={() => void openDownload(primaryZip)}
                      disabled={busy}
                    />
                  </View>
                )}

                <View style={styles.actions}>
                  <Button
                    title={busy ? "Working…" : "Open Woolworths sign-in"}
                    onPress={() => void openWoolworthsAndWait()}
                    disabled={busy}
                  />
                  <Button
                    title="I've clicked Connect in the extension"
                    variant="secondary"
                    onPress={() => void checkStatus()}
                    disabled={busy}
                  />
                  {waitingExtension ? (
                    <Text style={styles.hint}>
                      Waiting for the extension… keep this tab open after you click Connect.
                    </Text>
                  ) : null}
                  <Button title="Cancel" variant="ghost" onPress={onCancel} />
                </View>

                <Button
                  title={showOtherBrowsers ? "Hide other browsers" : "Other browsers"}
                  variant="ghost"
                  onPress={() => setShowOtherBrowsers((v) => !v)}
                />
                {showOtherBrowsers ? (
                  <View style={styles.advancedBox}>
                    <Text style={styles.step}>Chrome / Edge: download chromium zip → Load unpacked</Text>
                    <Button
                      title="Download Chrome/Edge zip"
                      variant="secondary"
                      onPress={() => void openDownload("chromium")}
                    />
                    <Text style={styles.step}>Firefox: download firefox zip → Load Temporary Add-on</Text>
                    <Button
                      title="Download Firefox zip"
                      variant="secondary"
                      onPress={() => void openDownload("firefox")}
                    />
                    <Text style={styles.step}>
                      Safari (Mac): see apps/browser-extension/safari/README.md in the GitHub repo
                    </Text>
                  </View>
                ) : null}

                <Button
                  title={showAdvanced ? "Hide advanced options" : "Advanced (bookmarklet / paste)"}
                  variant="ghost"
                  onPress={() => setShowAdvanced((v) => !v)}
                />
                {showAdvanced ? (
                  <View style={styles.advancedBox}>
                    <Text style={styles.alt}>
                      Sign-in: {WOOLWORTHS_SIGN_IN_URL}
                    </Text>
                    <Button
                      title={busy ? "Working…" : "Copy bookmarklet + open Woolworths"}
                      variant="secondary"
                      onPress={() => void copyBookmarklet()}
                      disabled={busy}
                    />
                    {bookmarkletHint ? <Text style={styles.hint}>{bookmarkletHint}</Text> : null}
                    <Text style={styles.alt}>Or paste Cookie header value:</Text>
                    <TextInput
                      style={styles.input}
                      value={paste}
                      onChangeText={setPaste}
                      placeholder="name=value; name2=value2; …"
                      placeholderTextColor={theme.textMuted}
                      multiline
                      autoCapitalize="none"
                      autoCorrect={false}
                    />
                    <Button
                      title="Import pasted cookies"
                      variant="secondary"
                      onPress={() => void importPasted()}
                      disabled={busy || !paste.trim()}
                    />
                  </View>
                ) : null}
              </>
            ) : (
              <>
                <Text style={styles.message}>
                  Sign in with your Woolworths NZ account in your browser so we can find real products
                  and prices — otherwise everything ends up in Manual.
                </Text>
                <Text style={styles.linkHint}>
                  If no tab opens, use this link: {WOOLWORTHS_SIGN_IN_URL}
                </Text>
                <View style={[styles.actions, styles.actionsRow]}>
                  <Button title="Open Woolworths sign-in" onPress={() => void runLocalLogin()} />
                  <Button title="I've signed in" variant="secondary" onPress={() => void verifyLocal()} />
                  <Button title="Cancel" variant="ghost" onPress={onCancel} />
                </View>
              </>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  card: {
    width: "100%",
    maxWidth: 520,
    backgroundColor: theme.white,
    borderRadius: 16,
    maxHeight: "92%",
    overflow: "hidden",
  },
  scroll: { padding: 24, paddingBottom: 32 },
  title: { fontSize: 20, fontWeight: "800", color: theme.text, marginBottom: 8, textAlign: "center" },
  message: {
    fontSize: 14,
    color: theme.textMuted,
    lineHeight: 20,
    marginBottom: 12,
    textAlign: "center",
  },
  browserBadge: {
    alignSelf: "center",
    fontSize: 12,
    fontWeight: "700",
    color: theme.text,
    backgroundColor: theme.border,
    overflow: "hidden",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: theme.text,
    marginBottom: 8,
  },
  step: {
    fontSize: 13,
    color: theme.textMuted,
    lineHeight: 19,
    marginBottom: 6,
  },
  linkHint: { fontSize: 11, color: theme.textMuted, marginBottom: 16, textAlign: "center" },
  actions: { gap: 10, marginTop: 12 },
  actionsRow: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center" },
  hint: { fontSize: 12, color: theme.textMuted, lineHeight: 18, marginTop: 4 },
  alt: { fontSize: 12, color: theme.textMuted, marginTop: 8 },
  advancedBox: { gap: 8, marginTop: 4, marginBottom: 8 },
  input: {
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 10,
    padding: 10,
    minHeight: 72,
    fontSize: 12,
    color: theme.text,
    textAlignVertical: "top",
  },
});
