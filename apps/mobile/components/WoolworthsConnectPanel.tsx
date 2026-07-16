import { useCallback, useRef, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { WebView, type WebViewMessageEvent } from "react-native-webview";
import { Button } from "@/components/ui/Button";
import { theme } from "@/constants/theme";
import {
  WOOLWORTHS_HOME,
  WOOLWORTHS_SIGN_IN,
  WOOLWORTHS_WEBVIEW_URI,
  WOOLWORTHS_WEBVIEW_UA,
} from "@/lib/config";
import { api, getApiBaseUrl } from "@/lib/api";
import { setMobileWoolworthsLinked } from "@/lib/woolworths-mobile";
import {
  parseCookieHarvestMessage,
  parseDocumentCookies,
  WOOLWORTHS_COOKIE_HARVEST_JS,
  WOOLWORTHS_SIGN_IN_CLICK_JS,
} from "@/lib/woolworths-cookies";

function isErrorUrl(url: string): boolean {
  const u = url.toLowerCase();
  return (
    u.includes("/404") ||
    u.includes("page-not-found") ||
    u.includes("/error") ||
    u.includes("/shop/myaccount")
  );
}

export function WoolworthsConnectPanel({
  title = "Sign in to Woolworths",
  hint = "While you wait, sign in on woolworths.co.nz — then tap “I've signed in”.",
  onLinked,
  onError,
  compact,
  autoHarvest = false,
}: {
  title?: string;
  hint?: string;
  onLinked: () => void;
  onError?: (message: string) => void;
  compact?: boolean;
  /** When false, only harvest cookies after user taps I've signed in (recommended). */
  autoHarvest?: boolean;
}) {
  const webRef = useRef<WebView>(null);
  const [webUri, setWebUri] = useState(WOOLWORTHS_WEBVIEW_URI);
  const [importing, setImporting] = useState(false);
  const [status, setStatus] = useState(hint);
  const imported = useRef(false);
  const lastHarvestAt = useRef(0);

  const reportError = useCallback(
    (message: string) => {
      onError?.(message);
    },
    [onError],
  );

  const requestCookiesFromWebView = useCallback(() => {
    if (imported.current || importing) return;
    setImporting(true);
    setStatus("Checking sign-in…");
    webRef.current?.injectJavaScript(WOOLWORTHS_COOKIE_HARVEST_JS);
  }, [importing]);

  const openSignInPage = useCallback(() => {
    setWebUri(WOOLWORTHS_SIGN_IN);
    setStatus("Use the Woolworths sign-in form below, then tap “I've signed in”.");
  }, []);

  const onWebViewMessage = useCallback(
    async (event: WebViewMessageEvent) => {
      if (imported.current) return;
      const msg = parseCookieHarvestMessage(event.nativeEvent.data);
      if (!msg) return;

      if (msg.type === "error") {
        reportError(msg.message);
        setStatus("Could not read cookies — try again.");
        setImporting(false);
        return;
      }

      const list = parseDocumentCookies(msg.raw);
      if (list.length < 1) {
        setStatus("Complete sign-in on Woolworths, then tap “I've signed in”.");
        setImporting(false);
        return;
      }

      try {
        const res = await api.importWoolworthsCookies(list);
        if (!res.connected) {
          setStatus(res.message);
          setImporting(false);
          return;
        }
        imported.current = true;
        await setMobileWoolworthsLinked(true);
        setStatus("Connected — product search will use your Woolworths account.");
        onLinked();
      } catch (e) {
        const message = e instanceof Error ? e.message : "Could not connect Woolworths";
        reportError(message);
        if (message.includes("port 8000") || message.includes("Cannot reach PC API")) {
          setStatus(`${message} Meal plans use the same API — if those work, tap I've signed in to retry.`);
        } else {
          setStatus("Connection failed — finish sign-in, then tap “I've signed in” to retry.");
        }
      } finally {
        setImporting(false);
      }
    },
    [onLinked, reportError],
  );

  const onLoadEnd = useCallback(
    (url: string) => {
      const u = url.toLowerCase();
      if (u.includes("/shop/myaccount")) {
        setWebUri(WOOLWORTHS_WEBVIEW_URI);
        setStatus("That page is unavailable — use Sign in page or the homepage below.");
        return;
      }
      if (isErrorUrl(url)) return;
      if (u === WOOLWORTHS_HOME || u.endsWith("woolworths.co.nz") || u.endsWith("woolworths.co.nz/")) {
        webRef.current?.injectJavaScript(WOOLWORTHS_SIGN_IN_CLICK_JS);
      }
      if (!autoHarvest || imported.current || importing) return;
      const now = Date.now();
      if (now - lastHarvestAt.current < 4000) return;
      lastHarvestAt.current = now;
      requestCookiesFromWebView();
    },
    [autoHarvest, importing, requestCookiesFromWebView],
  );

  return (
    <View style={[styles.wrap, compact && styles.wrapCompact]}>
      <View style={[styles.toolbar, compact && styles.toolbarCompact]}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.status}>{status}</Text>
        <Text style={styles.apiHint}>PC API: {getApiBaseUrl()}</Text>
        <View style={styles.toolbarActions}>
          <Button title="Sign in page" variant="secondary" onPress={openSignInPage} />
          <Button
            title="Reload"
            variant="secondary"
            onPress={() => {
              setWebUri(WOOLWORTHS_WEBVIEW_URI);
              webRef.current?.reload();
            }}
          />
          <Button title="I've signed in" onPress={requestCookiesFromWebView} loading={importing} />
        </View>
      </View>
      {importing && <ActivityIndicator style={styles.spinner} color={theme.green} />}
      <WebView
        ref={webRef}
        source={{ uri: webUri }}
        userAgent={WOOLWORTHS_WEBVIEW_UA}
        sharedCookiesEnabled
        thirdPartyCookiesEnabled
        javaScriptEnabled
        domStorageEnabled
        onMessage={onWebViewMessage}
        onLoadEnd={(e) => onLoadEnd(e.nativeEvent.url)}
        onHttpError={(e) => {
          if (e.nativeEvent.statusCode >= 400) {
            setStatus(
              `Woolworths returned ${e.nativeEvent.statusCode} — tap Sign in page or Reload.`,
            );
          }
        }}
        style={styles.webview}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: theme.white },
  wrapCompact: { minHeight: 280 },
  toolbar: { padding: 12, borderBottomWidth: 1, borderBottomColor: theme.border },
  toolbarCompact: { paddingVertical: 8, paddingHorizontal: 10 },
  title: { fontSize: 16, fontWeight: "700", color: theme.text },
  status: { fontSize: 12, color: theme.textMuted, marginTop: 4, marginBottom: 4 },
  apiHint: { fontSize: 10, color: theme.textMuted, marginBottom: 6 },
  toolbarActions: { flexDirection: "row", flexWrap: "wrap", gap: 8, justifyContent: "flex-end" },
  spinner: { marginVertical: 4 },
  webview: { flex: 1, minHeight: 200 },
});
