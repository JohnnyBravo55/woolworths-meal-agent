import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { api } from "@/lib/api";
import { theme } from "@/constants/theme";

export function WoolworthsStatus({
  refreshKey,
  onConnect,
  showConnectLink = true,
}: {
  refreshKey: number;
  onConnect: () => void;
  showConnectLink?: boolean;
}) {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api
      .getWoolworthsStatus()
      .then((r) => {
        setConnected(r.connected);
        setMessage(r.message);
      })
      .catch(() => setConnected(false));
  }, [refreshKey]);

  const disconnect = async () => {
    await api.woolworthsDisconnect();
    setConnected(false);
    setMessage("Disconnected");
  };

  return (
    <View style={styles.wrap}>
      <View
        style={[
          styles.dot,
          { backgroundColor: connected ? theme.green : connected === false ? theme.red : theme.border },
        ]}
      />
      <Text style={styles.text} numberOfLines={2}>
        {connected
          ? "Woolworths connected"
          : showConnectLink
            ? "Not connected"
            : "Sign in at Add to cart"}
      </Text>
      {connected ? (
        <Pressable onPress={disconnect}>
          <Text style={styles.link}>Disconnect</Text>
        </Pressable>
      ) : showConnectLink ? (
        <Pressable onPress={onConnect}>
          <Text style={styles.link}>Connect</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: "row", alignItems: "center", gap: 6, maxWidth: 200 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  text: { fontSize: 12, color: theme.textMuted, flex: 1 },
  link: { fontSize: 12, color: theme.green, fontWeight: "600" },
});
