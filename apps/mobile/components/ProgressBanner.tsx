import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { theme } from "@/constants/theme";

export function ProgressBanner({
  message,
  done,
  total,
  ingredient,
}: {
  message: string;
  done: number;
  total: number;
  ingredient?: string;
}) {
  const pct = total > 0 ? Math.min(100, (done / total) * 100) : null;

  return (
    <View style={styles.wrap}>
      <Text style={styles.message}>
        {message}
        {total > 0 ? ` (${done}/${total})` : ""}
        {ingredient ? ` — ${ingredient}` : ""}
      </Text>
      <View style={styles.barBg}>
        {pct !== null ? (
          <View style={[styles.barFill, { width: `${pct}%` }]} />
        ) : (
          <View style={styles.indeterminate} />
        )}
      </View>
      {pct === null && <ActivityIndicator style={styles.spinner} color={theme.green} />}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: theme.white,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 10,
    padding: 14,
    marginBottom: 16,
  },
  message: { fontSize: 14, fontWeight: "600", color: theme.text, marginBottom: 10 },
  barBg: {
    height: 10,
    backgroundColor: theme.border,
    borderRadius: 5,
    overflow: "hidden",
  },
  barFill: { height: "100%", backgroundColor: theme.green, borderRadius: 5 },
  indeterminate: { height: "100%", width: "40%", backgroundColor: theme.green, borderRadius: 5 },
  spinner: { marginTop: 10 },
});
