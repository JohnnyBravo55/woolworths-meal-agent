import { Platform, StyleSheet, View, ViewStyle } from "react-native";
import { webLayout } from "@/lib/web-layout";

/** Wizard step actions — optional row layout; web centering only on web. */
export function ActionBar({
  children,
  style,
  row,
}: {
  children: React.ReactNode;
  style?: ViewStyle;
  /** Place buttons in a horizontal row (back + continue side by side). */
  row?: boolean;
}) {
  return (
    <View
      style={[
        style,
        row && styles.row,
        Platform.OS === "web" && webLayout?.actions,
        Platform.OS === "web" && row && styles.webRow,
      ]}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    gap: 10,
  },
  webRow: {
    justifyContent: "center",
  },
});
