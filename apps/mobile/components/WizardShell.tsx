import { useRouter, useSegments } from "expo-router";
import { useEffect, useRef } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useApp } from "@/context/AppProvider";
import { Stepper } from "@/components/Stepper";
import { WoolworthsStatus } from "@/components/WoolworthsStatus";
import { theme } from "@/constants/theme";
import { webLayout } from "@/lib/web-layout";

export function WizardShell({ children }: { children: React.ReactNode }) {
  const isWeb = Platform.OS === "web";
  const router = useRouter();
  const segments = useSegments();
  const { error, setError, woolworthsKey } = useApp();
  const route = segments[segments.length - 1] ?? "discovery";
  const cartStep = route === "cart";
  const scrollRef = useRef<ScrollView>(null);

  useEffect(() => {
    // Reset scroll when changing wizard steps (e.g. plan → recipes).
    scrollRef.current?.scrollTo({ y: 0, animated: false });
  }, [route]);

  const onConnect = () => {
    if (isWeb) {
      router.push("/cart");
      return;
    }
    router.push({ pathname: "/connect-woolworths" });
  };

  return (
    <SafeAreaView style={styles.safe}>
      <View style={[styles.header, isWeb && webLayout?.header]}>
        <View style={isWeb ? webLayout?.page : undefined}>
          <Text style={[styles.title, isWeb && webLayout?.title]}>Woolworths Meal Agent</Text>
          {isWeb ? (
            <Text style={styles.hostedHint}>Supermarket cart fill — coming soon</Text>
          ) : (
            <WoolworthsStatus
              refreshKey={woolworthsKey}
              onConnect={onConnect}
              showConnectLink={cartStep}
            />
          )}
          <Stepper currentRoute={String(route)} />
        </View>
      </View>
      {error ? (
        <Pressable style={[styles.error, isWeb && styles.errorWeb]} onPress={() => setError("")}>
          <Text style={styles.errorText}>{error} — tap to dismiss</Text>
        </Pressable>
      ) : null}
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        keyboardVerticalOffset={Platform.OS === "ios" ? 8 : 0}
      >
        <ScrollView
          ref={scrollRef}
          style={styles.flex}
          contentContainerStyle={[styles.main, isWeb && webLayout?.main]}
          keyboardShouldPersistTaps="handled"
          automaticallyAdjustKeyboardInsets
          keyboardDismissMode="on-drag"
        >
          <View style={isWeb ? webLayout?.page : undefined}>{children}</View>
        </ScrollView>
      </KeyboardAvoidingView>
      <Text style={styles.footer}>
        {isWeb
          ? "Shop list is ready to review — filling a supermarket trolley is coming soon."
          : "Never auto-checkout — you review and pay on woolworths.co.nz"}
      </Text>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.bg },
  flex: { flex: 1 },
  header: {
    backgroundColor: theme.white,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 12,
  },
  title: { fontSize: 20, fontWeight: "800", color: theme.text },
  hostedHint: {
    fontSize: 12,
    color: theme.textMuted,
    fontWeight: "600",
    marginTop: 4,
    marginBottom: 2,
  },
  main: { padding: 16, paddingBottom: 160 },
  footer: {
    textAlign: "center",
    fontSize: 11,
    color: theme.textMuted,
    padding: 8,
    backgroundColor: theme.white,
    borderTopWidth: 1,
    borderTopColor: theme.border,
  },
  error: {
    margin: 12,
    marginBottom: 0,
    padding: 12,
    backgroundColor: "#fef2f2",
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#fecaca",
  },
  errorWeb: {
    alignSelf: "center",
    maxWidth: 560,
    width: "100%",
  },
  errorText: { color: theme.red, fontSize: 13 },
});
