import { Pressable, StyleSheet, Text, ActivityIndicator, ViewStyle, Platform } from "react-native";
import { theme } from "@/constants/theme";

type Variant = "primary" | "secondary" | "ghost";

export function Button({
  title,
  onPress,
  disabled,
  variant = "primary",
  loading,
  style,
}: {
  title: string;
  onPress: () => void;
  disabled?: boolean;
  variant?: Variant;
  loading?: boolean;
  style?: ViewStyle;
}) {
  const bg =
    variant === "primary" ? theme.green : variant === "secondary" ? theme.white : "transparent";
  const color = variant === "primary" ? theme.white : theme.text;
  const border = variant === "secondary" ? theme.border : "transparent";

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.btn,
        Platform.OS === "web" && styles.btnWeb,
        { backgroundColor: bg, borderColor: border, opacity: pressed || disabled ? 0.7 : 1 },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={color} />
      ) : (
        <Text style={[styles.text, { color }]}>{title}</Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 10,
    borderWidth: 1,
    alignItems: "center",
    minWidth: 80,
  },
  btnWeb: { minWidth: 220 },
  text: { fontSize: 15, fontWeight: "600" },
});
