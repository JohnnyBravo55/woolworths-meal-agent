import { StyleSheet, Text, View } from "react-native";
import { theme } from "@/constants/theme";

export function Badge({
  children,
  tone = "default",
}: {
  children: React.ReactNode;
  tone?: "default" | "danger" | "mandatory";
}) {
  const bg =
    tone === "danger" ? "#fef2f2" : tone === "mandatory" ? "#fffbeb" : "#ecfdf5";
  const color =
    tone === "danger" ? theme.red : tone === "mandatory" ? theme.amber : theme.green;

  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <Text style={[styles.text, { color }]}>{children}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, alignSelf: "flex-start" },
  text: { fontSize: 11, fontWeight: "700" },
});
