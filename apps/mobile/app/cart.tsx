import { useRouter, useLocalSearchParams } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { useCallback, useEffect, useRef } from "react";
import { Platform, StyleSheet, Text, View } from "react-native";
import { WizardShell } from "@/components/WizardShell";
import { useApp } from "@/context/AppProvider";
import { Button } from "@/components/ui/Button";
import { ActionBar } from "@/components/ActionBar";
import { Card, CardBody, CardHeader, H2, Muted } from "@/components/ui/Card";
import { ProgressBanner } from "@/components/ProgressBanner";
import { theme } from "@/constants/theme";
import { api } from "@/lib/api";
import { needsWoolworthsSignInForCart } from "@/lib/woolworths-mobile";

export default function CartScreen() {
  const router = useRouter();
  const { autoAdd } = useLocalSearchParams<{ autoAdd?: string }>();
  const {
    cartResult,
    setCartResult,
    loading,
    setLoading,
    setCartProgress,
    cartProgress,
    setError,
    refreshWoolworths,
  } = useApp();
  const autoAddRan = useRef(false);

  const runAddToCart = useCallback(
    async (opts: { allow_over_budget?: boolean; export_only?: boolean }) => {
      setError("");

      if (!opts.export_only) {
        const needsSignIn = await needsWoolworthsSignInForCart();
        if (needsSignIn) {
          router.push({ pathname: "/connect-woolworths", params: { after: "add-cart" } });
          return;
        }
      }

      setLoading(true);
      setCartProgress({ done: 0, total: 0, ingredient: "", phase: "adding", message: "", log: [] });
      try {
        if (opts.export_only) {
          setCartResult(await api.addToCart({ export_only: true }));
          return;
        }

        await api.streamCartAdd((event, data) => {
          if (event === "progress") {
            setCartProgress((prev) => ({
              ...prev,
              done: Number(data.done ?? prev.done),
              total: Number(data.total ?? prev.total),
              ingredient: String(data.ingredient || ""),
              status: String(data.status || ""),
              log: [
                ...prev.log,
                {
                  ingredient: String(data.ingredient || ""),
                  status: String(data.status || ""),
                  message: String(data.message || ""),
                },
              ],
            }));
          }
          if (event === "complete") {
            setCartResult(data.result as never);
          }
        }, opts);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Add to cart failed");
      } finally {
        setLoading(false);
      }
    },
    [refreshWoolworths, router, setCartProgress, setCartResult, setError, setLoading],
  );

  useEffect(() => {
    if (autoAdd === "1" && !autoAddRan.current) {
      autoAddRan.current = true;
      void runAddToCart({});
    }
  }, [autoAdd, runAddToCart]);

  const openTrolley = async () => {
    const { url } = await api.getCartUrl();
    if (Platform.OS === "web" && typeof window !== "undefined") {
      window.open(url, "_blank");
    } else {
      await WebBrowser.openBrowserAsync(url);
    }
  };

  return (
    <WizardShell>
      {loading && (
        <ProgressBanner
          message={
            cartProgress.ingredient
              ? `Adding ${cartProgress.ingredient}…`
              : "Adding items to Woolworths cart…"
          }
          done={cartProgress.done}
          total={cartProgress.total}
        />
      )}

      <Card>
        <CardHeader>
          <H2>Add to Woolworths cart</H2>
          <Muted>
            Tap Add to cart to sign in to Woolworths if needed, then items are added to your trolley.
          </Muted>
        </CardHeader>
        <CardBody>
          {cartResult && (
            <View style={styles.result}>
              <Text style={styles.resultLine}>Added: {cartResult.success_count} items</Text>
              <Text style={styles.resultLine}>Failed: {cartResult.failure_count}</Text>
              <Text style={styles.resultLine}>Total: ${cartResult.added_total.toFixed(2)}</Text>
              {cartResult.errors.map((e, i) => (
                <Text key={i} style={styles.error}>
                  {e}
                </Text>
              ))}
            </View>
          )}

          <ActionBar style={styles.actions}>
            <Button title="Add to cart" onPress={() => runAddToCart({})} loading={loading} />
            <Button
              title="Export list only"
              variant="secondary"
              onPress={() => runAddToCart({ export_only: true })}
              loading={loading}
            />
            <Button title="View trolley on Woolworths" variant="secondary" onPress={openTrolley} />
            {cartResult && (
              <Button
                title="Retry failed items"
                variant="secondary"
                onPress={() => api.retryCart().then(setCartResult)}
              />
            )}
          </ActionBar>
        </CardBody>
      </Card>

      <ActionBar style={styles.backAction}>
        <Button title="← Back to shop list" variant="ghost" onPress={() => router.push("/shop")} />
      </ActionBar>
    </WizardShell>
  );
}

const styles = StyleSheet.create({
  result: { marginBottom: 16 },
  resultLine: { fontSize: 14, color: theme.text, marginBottom: 4 },
  error: { fontSize: 12, color: theme.red, marginTop: 4 },
  actions: { gap: 10 },
  backAction: { marginTop: 16 },
});
