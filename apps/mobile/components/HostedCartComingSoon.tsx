import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { theme } from "@/constants/theme";

const RETAILERS = [
  { id: "woolworths", name: "Woolworths", color: "#178841" },
  { id: "freshchoice", name: "FreshChoice", color: "#F36C00" },
  { id: "new-world", name: "New World", color: "#C8102E" },
] as const;

/**
 * Hosted-only cart teaser: no Woolworths connect / add-to-trolley.
 * Local builds use the real cart screen instead.
 */
export function HostedCartComingSoon() {
  const [toast, setToast] = useState("");

  const onPressRetailer = (name: string) => {
    setToast(`${name} cart fill — coming soon`);
  };

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>Fill shopping cart, coming soon</Text>
      <Text style={styles.subtitle}>
        Soon you’ll send this list to your supermarket trolley in one tap. For now, use your shop list
        above — trolley fill is on the way.
      </Text>

      <View style={styles.buttons}>
        {RETAILERS.map((r) => (
          <Pressable
            key={r.id}
            accessibilityLabel={`${r.name}, coming soon`}
            onPress={() => onPressRetailer(r.name)}
            style={({ pressed }) => [
              styles.retailerBtn,
              { backgroundColor: r.color, opacity: pressed ? 0.88 : 1 },
            ]}
          >
            <View style={styles.logoMark}>
              <Text style={styles.logoInitial}>{r.name.charAt(0)}</Text>
            </View>
            <Text style={styles.retailerName}>{r.name}</Text>
            <Text style={styles.coming}>Coming soon</Text>
          </Pressable>
        ))}
      </View>

      {toast ? <Text style={styles.toast}>{toast}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingVertical: 8,
    gap: 14,
  },
  title: {
    fontSize: 22,
    fontWeight: "800",
    color: theme.text,
    textAlign: "center",
  },
  subtitle: {
    fontSize: 14,
    lineHeight: 20,
    color: theme.textMuted,
    textAlign: "center",
    marginBottom: 4,
  },
  buttons: {
    gap: 10,
    marginTop: 4,
  },
  retailerBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 16,
    minHeight: 56,
  },
  logoMark: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: "rgba(255,255,255,0.22)",
    alignItems: "center",
    justifyContent: "center",
  },
  logoInitial: {
    color: "#fff",
    fontSize: 18,
    fontWeight: "800",
  },
  retailerName: {
    flex: 1,
    color: "#fff",
    fontSize: 17,
    fontWeight: "700",
  },
  coming: {
    color: "rgba(255,255,255,0.85)",
    fontSize: 12,
    fontWeight: "600",
  },
  toast: {
    marginTop: 4,
    textAlign: "center",
    fontSize: 13,
    fontWeight: "600",
    color: theme.text,
  },
});
