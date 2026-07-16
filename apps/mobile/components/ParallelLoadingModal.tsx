import { ActivityIndicator, Modal, SafeAreaView, StyleSheet, Text, View } from "react-native";
import { theme } from "@/constants/theme";
import { WoolworthsConnectPanel } from "@/components/WoolworthsConnectPanel";
import { Button } from "@/components/ui/Button";

export function ParallelLoadingModal({
  visible,
  title,
  message,
  done,
  total,
  ingredient,
  showWoolworths,
  woolworthsOnly,
  woolworthsTitle,
  woolworthsHint,
  planReady,
  onWoolworthsLinked,
  onWoolworthsError,
  onContinueWithoutWoolworths,
  onCancelWoolworths,
}: {
  visible: boolean;
  title: string;
  message: string;
  done: number;
  total: number;
  ingredient?: string;
  showWoolworths: boolean;
  /** Woolworths sign-in must finish before any background work starts (e.g. shop list build). */
  woolworthsOnly?: boolean;
  woolworthsTitle?: string;
  woolworthsHint?: string;
  planReady?: boolean;
  onWoolworthsLinked: () => void;
  onWoolworthsError?: (message: string) => void;
  onContinueWithoutWoolworths?: () => void;
  onCancelWoolworths?: () => void;
}) {
  const pct = total > 0 ? Math.min(100, (done / total) * 100) : null;

  if (!visible) return null;

  if (showWoolworths) {
    const connectTitle = woolworthsTitle ?? "Connect to Woolworths";
    const connectHint =
      woolworthsHint ??
      "Sign in to Woolworths so we can find real products and add them to your cart.";

    return (
      <Modal visible animationType="slide" presentationStyle="fullScreen" statusBarTranslucent>
        <SafeAreaView style={styles.fullScreen}>
          {woolworthsOnly ? (
            <View style={styles.connectHeader}>
              <Text style={styles.progressTitle}>{connectTitle}</Text>
              <Text style={styles.progressMessage}>{connectHint}</Text>
              {onCancelWoolworths && (
                <Button title="Cancel" variant="ghost" onPress={onCancelWoolworths} />
              )}
            </View>
          ) : (
            <View style={styles.progressHeader}>
              <Text style={styles.progressTitle}>{planReady ? "Meal plan ready" : title}</Text>
              <Text style={styles.progressMessage} numberOfLines={4}>
                {planReady
                  ? "Finish Woolworths sign-in for live product prices, or continue without."
                  : message}
                {!planReady && total > 0 ? ` · ${done}/${total}` : ""}
                {ingredient ? ` · ${ingredient}` : ""}
              </Text>
              {!planReady && (
                <>
                  <View style={styles.barBg}>
                    {pct !== null ? (
                      <View style={[styles.barFill, { width: `${pct}%` }]} />
                    ) : (
                      <View style={styles.indeterminate} />
                    )}
                  </View>
                  {pct === null && <ActivityIndicator style={styles.headerSpinner} color={theme.green} />}
                </>
              )}
              {planReady && onContinueWithoutWoolworths && (
                <Button
                  title="Continue without Woolworths →"
                  variant="secondary"
                  onPress={onContinueWithoutWoolworths}
                />
              )}
            </View>
          )}
          <WoolworthsConnectPanel
            title={woolworthsOnly ? undefined : woolworthsTitle}
            hint={woolworthsOnly ? undefined : woolworthsHint}
            compact={!woolworthsOnly}
            autoHarvest={false}
            onLinked={onWoolworthsLinked}
            onError={onWoolworthsError}
          />
        </SafeAreaView>
      </Modal>
    );
  }

  return (
    <Modal visible transparent animationType="fade" statusBarTranslucent>
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.message}>
            {message}
            {total > 0 ? `\n${done} of ${total} complete` : ""}
            {ingredient ? `\n${ingredient}` : ""}
          </Text>
          <View style={styles.barBg}>
            {pct !== null ? (
              <View style={[styles.barFill, { width: `${pct}%` }]} />
            ) : (
              <View style={styles.indeterminate} />
            )}
          </View>
          {pct === null && <ActivityIndicator style={styles.spinner} color={theme.green} size="large" />}
          <Text style={styles.hint}>Please wait — this can take 1–3 minutes.</Text>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  fullScreen: { flex: 1, backgroundColor: theme.white },
  connectHeader: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
    backgroundColor: theme.white,
    gap: 8,
  },
  progressHeader: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
    backgroundColor: "#f0fdf4",
    gap: 8,
  },
  progressTitle: { fontSize: 17, fontWeight: "800", color: theme.text },
  progressMessage: { fontSize: 13, color: theme.textMuted, lineHeight: 18 },
  headerSpinner: { marginTop: 4 },
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.55)",
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  card: {
    width: "100%",
    maxWidth: 340,
    backgroundColor: theme.white,
    borderRadius: 16,
    padding: 24,
    alignItems: "stretch",
  },
  title: { fontSize: 18, fontWeight: "800", color: theme.text, marginBottom: 8, textAlign: "center" },
  message: { fontSize: 14, color: theme.textMuted, marginBottom: 16, textAlign: "center", lineHeight: 20 },
  barBg: {
    height: 10,
    backgroundColor: theme.border,
    borderRadius: 5,
    overflow: "hidden",
  },
  barFill: { height: "100%", backgroundColor: theme.green, borderRadius: 5 },
  indeterminate: { height: "100%", width: "45%", backgroundColor: theme.green, borderRadius: 5 },
  spinner: { marginTop: 16 },
  hint: { fontSize: 12, color: theme.textMuted, marginTop: 14, textAlign: "center" },
});
