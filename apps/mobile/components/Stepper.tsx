import { StyleSheet, Text, View, Platform } from "react-native";
import { STEPS } from "@meal-agent/app-core";
import { theme } from "@/constants/theme";

const ROUTE_KEYS = ["discovery", "chef", "plan", "recipes", "shop", "cart"];

export function Stepper({ currentRoute }: { currentRoute: string }) {
  const idx = ROUTE_KEYS.indexOf(currentRoute);
  const current = idx >= 0 ? idx : 0;
  const isWeb = Platform.OS === "web";

  return (
    <View style={[styles.row, isWeb && styles.rowWeb]}>      {STEPS.map((step, i) => (
        <View key={step.key} style={styles.item}>
          <View
            style={[
              styles.dot,
              i <= current ? { backgroundColor: theme.green } : { backgroundColor: theme.border },
            ]}
          />
          <Text style={[styles.label, i === current && styles.labelActive]} numberOfLines={1}>
            {step.label}
          </Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginTop: 12 },
  rowWeb: { justifyContent: "center" },  item: { alignItems: "center", minWidth: 52 },
  dot: { width: 10, height: 10, borderRadius: 5, marginBottom: 4 },
  label: { fontSize: 10, color: theme.textMuted },
  labelActive: { color: theme.green, fontWeight: "700" },
});
