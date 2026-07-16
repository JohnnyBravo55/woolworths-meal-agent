import { StyleSheet, ViewStyle } from "react-native";
import { ActionBar } from "@/components/ActionBar";
import { theme } from "@/constants/theme";

export function StepNavBar({
  children,
  position,
  style,
  row = true,
}: {
  children: React.ReactNode;
  position: "top" | "bottom";
  style?: ViewStyle;
  row?: boolean;
}) {
  return (
    <ActionBar row={row} style={[position === "top" ? styles.top : styles.bottom, style]}>
      {children}
    </ActionBar>
  );
}

const styles = StyleSheet.create({
  top: {
    marginBottom: 16,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  bottom: {
    marginTop: 24,
  },
});
