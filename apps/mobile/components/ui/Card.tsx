import { StyleSheet, Text, View, ViewStyle } from "react-native";
import { theme } from "@/constants/theme";

export function Card({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function CardHeader({ children }: { children: React.ReactNode }) {
  return <View style={styles.header}>{children}</View>;
}

export function CardBody({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  return <View style={[styles.body, style]}>{children}</View>;
}

export function H2({ children }: { children: React.ReactNode }) {
  return <Text style={styles.h2}>{children}</Text>;
}

export function Muted({ children }: { children: React.ReactNode }) {
  return <Text style={styles.muted}>{children}</Text>;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.white,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: theme.border,
    overflow: "hidden",
  },
  header: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  body: { padding: 16 },
  h2: { fontSize: 18, fontWeight: "700", color: theme.text },
  muted: { fontSize: 14, color: theme.textMuted, marginTop: 4 },
});
