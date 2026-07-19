import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { NdaGate } from "@/components/NdaGate";
import { Button } from "@/components/ui/Button";
import { hasAcceptedNda } from "@/constants/nda";
import { theme } from "@/constants/theme";
import {
  accessGateEnabled,
  hasAccessCode,
  unlockAccessCode,
} from "@/lib/access-code";
import { api } from "@/lib/api";
import { sessionStore } from "@/lib/session-store";

export function AccessCodeGate({ children }: { children: React.ReactNode }) {
  const [checking, setChecking] = useState(true);
  const [codeUnlocked, setCodeUnlocked] = useState(false);
  const [ndaAccepted, setNdaAccepted] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!accessGateEnabled()) {
        if (!cancelled) {
          setCodeUnlocked(true);
          setNdaAccepted(true);
          setChecking(false);
        }
        return;
      }
      const ok = await hasAccessCode();
      if (!cancelled) {
        setCodeUnlocked(ok);
        setNdaAccepted(ok ? hasAcceptedNda() : false);
        setChecking(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onSubmit = useCallback(async () => {
    setError("");
    setSubmitting(true);
    try {
      await unlockAccessCode(code);
      // Probe a gated endpoint so bad codes fail before entering the app.
      await api.startSession();
      setCodeUnlocked(true);
      setNdaAccepted(hasAcceptedNda());
    } catch (e) {
      const message = e instanceof Error ? e.message : "Invalid access code";
      setError(message);
      await sessionStore.clearAccessCode?.();
    } finally {
      setSubmitting(false);
    }
  }, [code]);

  if (checking) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={theme.green} />
      </View>
    );
  }

  if (codeUnlocked && ndaAccepted) {
    return <>{children}</>;
  }

  if (codeUnlocked && !ndaAccepted) {
    return <NdaGate onAccepted={() => setNdaAccepted(true)} />;
  }

  return (
    <View style={styles.center}>
      <View style={styles.card}>
        <Text style={styles.title}>Woolworths Meal Agent</Text>
        <Text style={styles.subtitle}>Enter the tester access code to continue.</Text>
        <TextInput
          style={styles.input}
          value={code}
          onChangeText={setCode}
          placeholder="Access code"
          placeholderTextColor={theme.textMuted}
          autoCapitalize="none"
          autoCorrect={false}
          secureTextEntry
          testID="access-code-input"
          accessibilityLabel="Access code"
          onSubmitEditing={() => void onSubmit()}
        />
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <Button
          title={submitting ? "Checking…" : "Continue"}
          onPress={() => void onSubmit()}
          disabled={submitting || !code.trim()}
          testID="access-code-continue"
        />
        <Text style={styles.hint}>
          First visit after idle may take up to a minute while the free API wakes up.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    backgroundColor: theme.bg,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  card: {
    width: "100%",
    maxWidth: 400,
    backgroundColor: theme.white,
    borderRadius: 16,
    padding: 24,
    borderWidth: 1,
    borderColor: theme.border,
    gap: 12,
  },
  title: { fontSize: 22, fontWeight: "800", color: theme.text, textAlign: "center" },
  subtitle: { fontSize: 14, color: theme.textMuted, textAlign: "center", marginBottom: 4 },
  input: {
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: theme.text,
    backgroundColor: theme.white,
  },
  error: { color: theme.red, fontSize: 13, textAlign: "center" },
  hint: { fontSize: 12, color: theme.textMuted, textAlign: "center", marginTop: 4 },
});
