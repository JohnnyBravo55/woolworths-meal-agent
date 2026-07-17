import { useRouter, useLocalSearchParams } from "expo-router";
import { useEffect } from "react";
import { Platform, SafeAreaView, StyleSheet, View } from "react-native";
import { Button } from "@/components/ui/Button";
import { WoolworthsConnectPanel } from "@/components/WoolworthsConnectPanel";
import { theme } from "@/constants/theme";
import { useApp } from "@/context/AppProvider";

/**
 * Web: always redirect to cart (Coming soon). No extension / connect UI on web.
 * Native: in-app WebView connect panel.
 */
export default function ConnectWoolworthsScreen() {
  const router = useRouter();
  const { after } = useLocalSearchParams<{ after?: string }>();
  const { refreshWoolworths, setError } = useApp();

  useEffect(() => {
    if (Platform.OS === "web") {
      router.replace("/cart");
    }
  }, [router]);

  const finish = () => {
    refreshWoolworths();
    if (after === "add-cart") {
      router.replace("/cart?autoAdd=1");
      return;
    }
    router.back();
  };

  if (Platform.OS === "web") {
    return <SafeAreaView style={styles.container} />;
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.topBar}>
        <Button title="Cancel" variant="secondary" onPress={() => router.back()} />
      </View>
      <WoolworthsConnectPanel
        title={after === "add-cart" ? "Sign in to add to cart" : "Connect Woolworths"}
        onLinked={finish}
        onError={(message) => setError(message)}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.white },
  topBar: { padding: 12, alignItems: "flex-start" },
});
