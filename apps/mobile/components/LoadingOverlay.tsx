import { ActivityIndicator, Modal, StyleSheet, Text, View } from "react-native";
import { theme } from "@/constants/theme";

export function LoadingOverlay({
  visible,
  title,
  message,
  done,
  total,
  ingredient,
}: {
  visible: boolean;
  title: string;
  message: string;
  done: number;
  total: number;
  ingredient?: string;
}) {
  const pct = total > 0 ? Math.min(100, (done / total) * 100) : null;

  return (
    <Modal visible={visible} transparent animationType="fade" statusBarTranslucent>
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
    height: 12,
    backgroundColor: theme.border,
    borderRadius: 6,
    overflow: "hidden",
  },
  barFill: { height: "100%", backgroundColor: theme.green, borderRadius: 6 },
  indeterminate: { height: "100%", width: "45%", backgroundColor: theme.green, borderRadius: 6 },
  spinner: { marginTop: 16 },
  hint: { fontSize: 12, color: theme.textMuted, marginTop: 14, textAlign: "center" },
});
