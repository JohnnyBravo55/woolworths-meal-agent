import { useCallback, useState } from "react";
import {
  Modal,
  Platform,
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
import { sessionStore } from "@/lib/session-store";
import {
  buildWoolworthsCookieBookmarklet,
  parseCookiesFromRawHeader,
} from "@/lib/woolworths-web-bookmarklet";

/**
 * PC / Expo web Woolworths connect.
 * - Local API: open browser + server-side cookie import (existing path).
 * - Hosted API: bookmarklet / paste cookies (server has no local browser).
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
  const [paste, setPaste] = useState("");
  const [busy, setBusy] = useState(false);
  const [bookmarkletHint, setBookmarkletHint] = useState("");

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
          "Bookmarklet copied. On woolworths.co.nz (after sign-in), paste it into the address bar and press Enter — or save it as a bookmark first.",
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

  const checkStatus = useCallback(async () => {
    setBusy(true);
    try {
      const status = await api.getWoolworthsStatus();
      if (status.connected) {
        onConnected();
        return;
      }
      onError("Not connected yet — run the bookmarklet on woolworths.co.nz after signing in.");
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not check Woolworths status");
    } finally {
      setBusy(false);
    }
  }, [onConnected, onError]);

  if (Platform.OS !== "web") return null;

  return (
    <Modal visible={visible} transparent animationType="fade">
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.title}>Connect Woolworths</Text>
          {hosted ? (
            <>
              <Text style={styles.message}>
                Sign in on woolworths.co.nz, then transfer cookies to this app (the hosted API
                cannot read your PC browser cookies).
              </Text>
              <Text style={styles.linkHint}>Sign-in: {WOOLWORTHS_SIGN_IN_URL}</Text>
              <View style={styles.actions}>
                <Button
                  title={busy ? "Working…" : "1. Copy connect bookmarklet + open Woolworths"}
                  onPress={() => void copyBookmarklet()}
                  disabled={busy}
                />
                <Button
                  title="2. I've run the bookmarklet"
                  variant="secondary"
                  onPress={() => void checkStatus()}
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
                <Button title="Cancel" variant="ghost" onPress={onCancel} />
              </View>
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
    maxWidth: 480,
    backgroundColor: theme.white,
    borderRadius: 16,
    padding: 24,
    maxHeight: "90%",
  },
  title: { fontSize: 20, fontWeight: "800", color: theme.text, marginBottom: 8, textAlign: "center" },
  message: {
    fontSize: 14,
    color: theme.textMuted,
    lineHeight: 20,
    marginBottom: 12,
    textAlign: "center",
  },
  linkHint: { fontSize: 11, color: theme.textMuted, marginBottom: 16, textAlign: "center" },
  actions: { gap: 10 },
  actionsRow: { flexDirection: "row", flexWrap: "wrap", justifyContent: "center" },
  hint: { fontSize: 12, color: theme.textMuted, lineHeight: 18 },
  alt: { fontSize: 12, color: theme.textMuted, marginTop: 8 },
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
