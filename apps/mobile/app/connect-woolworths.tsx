import { useRouter, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Platform, SafeAreaView, StyleSheet, View } from "react-native";
import { Button } from "@/components/ui/Button";
import { WoolworthsConnectPanel } from "@/components/WoolworthsConnectPanel";
import { WoolworthsWebConnectModal } from "@/components/WoolworthsWebConnectModal";
import { theme } from "@/constants/theme";
import { useApp } from "@/context/AppProvider";
import { getApiBaseUrl } from "@/lib/api";
import { isHostedApiUrl } from "@/lib/config";

export default function ConnectWoolworthsScreen() {
  const router = useRouter();
  const { after } = useLocalSearchParams<{ after?: string }>();
  const { refreshWoolworths, setError } = useApp();
  const [webModal, setWebModal] = useState(Platform.OS === "web");

  const finish = () => {
    refreshWoolworths();
    if (after === "add-cart") {
      router.replace("/cart?autoAdd=1");
      return;
    }
    router.back();
  };

  // Hosted Expo web: iframe WebView cannot read Woolworths cookies — use bookmarklet modal.
  if (Platform.OS === "web" && isHostedApiUrl(getApiBaseUrl())) {
    return (
      <SafeAreaView style={styles.container}>
        <WoolworthsWebConnectModal
          visible={webModal}
          onConnected={() => {
            setWebModal(false);
            finish();
          }}
          onError={(message) => setError(message)}
          onCancel={() => {
            setWebModal(false);
            router.back();
          }}
        />
      </SafeAreaView>
    );
  }

  // Local Expo web: keep native-style WebView panel when available; PC cookie import via modal.
  if (Platform.OS === "web") {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.topBar}>
          <Button title="Cancel" variant="secondary" onPress={() => router.back()} />
        </View>
        <WoolworthsWebConnectModal
          visible={webModal}
          onConnected={() => {
            setWebModal(false);
            finish();
          }}
          onError={(message) => setError(message)}
          onCancel={() => {
            setWebModal(false);
            router.back();
          }}
        />
      </SafeAreaView>
    );
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
