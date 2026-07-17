import { useRouter } from "expo-router";
import { useEffect, useState } from "react";
import { FlatList, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import type { GroceryLineItem } from "@meal-agent/app-core";
import { WizardShell } from "@/components/WizardShell";
import { useApp } from "@/context/AppProvider";
import { Button } from "@/components/ui/Button";
import { StepNavBar } from "@/components/StepNavBar";
import { Card, CardBody, CardHeader, H2 } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { theme } from "@/constants/theme";
import { api } from "@/lib/api";
import { useWizardNav } from "@/lib/useWizardNav";

function isAddable(item: GroceryLineItem) {
  return item.sku !== "OFFLINE" && item.in_stock && !item.cart_blocked;
}

function defaultTab(
  addable: GroceryLineItem[],
  blocked: GroceryLineItem[],
  manual: GroceryLineItem[],
): "addable" | "blocked" | "manual" {
  if (addable.length > 0) return "addable";
  if (manual.length > 0) return "manual";
  if (blocked.length > 0) return "blocked";
  return "addable";
}

export default function ShopScreen() {
  const router = useRouter();
  const { shopList, appState, loading, setLoading, setAppState, markStepReached } = useApp();
  const { showForward, goForward } = useWizardNav();
  const [tab, setTab] = useState<"addable" | "blocked" | "manual">("addable");

  useEffect(() => {
    if (!shopList) return;
    const add = shopList.items.filter(isAddable);
    const blk = shopList.items.filter((i) => i.cart_blocked);
    const man = shopList.items.filter((i) => i.sku === "OFFLINE");
    setTab(defaultTab(add, blk, man));
  }, [shopList]);

  if (!shopList) {
    return (
      <WizardShell>
        <Text>No shop list — run product search from recipes.</Text>
        <Button title="← Recipes" onPress={() => router.push("/recipes")} />
      </WizardShell>
    );
  }

  const addable = shopList.items.filter(isAddable);
  const blocked = shopList.items.filter((i) => i.cart_blocked);
  const manual = shopList.items.filter((i) => i.sku === "OFFLINE");
  const rows = tab === "addable" ? addable : tab === "blocked" ? blocked : manual;
  const addableTotal = api.computeAddableTotal(shopList);
  const offlineTotal = api.computeOfflineTotal(shopList);

  const approve = async () => {
    setLoading(true);
    try {
      const res = await api.approveShop();
      setAppState(res.state);
      markStepReached(5);
      router.push("/cart");
    } finally {
      setLoading(false);
    }
  };

  const navButtons = (
    <>
      <Button title="← Back" variant="secondary" onPress={() => router.push("/recipes")} />
      {showForward ? <Button title="Forward →" variant="secondary" onPress={goForward} /> : null}
      <Button title="Approve & continue →" onPress={approve} loading={loading} />
    </>
  );

  return (
    <WizardShell>
      <StepNavBar position="top">{navButtons}</StepNavBar>
      <Card>
        <CardBody>
          <Text style={styles.summary} testID="shop-summary">
            Will add: ${addableTotal.toFixed(2)} · Manual: ${offlineTotal.toFixed(2)} · Total: $
            {shopList.total.toFixed(2)} / ${shopList.budget_nzd.toFixed(2)}
          </Text>
          {!shopList.within_budget && <Badge tone="danger">Over budget</Badge>}
        </CardBody>
      </Card>

      {shopList.items.length === 0 && (
        <View style={styles.banner}>
          <Text style={styles.bannerText}>
            No products were resolved. Go back to recipes and tap “Build shop list” again, or check your PC API
            is running.
          </Text>
        </View>
      )}

      {shopList.items.length > 0 && addable.length === 0 && manual.length > 0 && tab !== "manual" && (
        <View style={styles.banner}>
          <Text style={styles.bannerText}>
            {Platform.OS === "web"
              ? `Items are estimated prices. Tap Manual (${manual.length}) to review them — filling a supermarket trolley is coming soon.`
              : `Items are estimated (not linked to Woolworths yet). Tap Manual (${manual.length}) to see them — sign in at Add to cart for live products.`}
          </Text>
        </View>
      )}

      <View style={styles.tabs}>
        {(
          [
            ["addable", `Will add (${addable.length})`],
            ["blocked", `Blocked (${blocked.length})`],
            ["manual", `Manual (${manual.length})`],
          ] as const
        ).map(([key, label]) => (
          <Pressable
            key={key}
            style={[styles.tab, tab === key && styles.tabActive]}
            onPress={() => setTab(key)}
          >
            <Text style={[styles.tabText, tab === key && styles.tabTextActive]}>{label}</Text>
          </Pressable>
        ))}
      </View>

      <FlatList
        data={rows}
        keyExtractor={(item, i) => `${item.ingredient}-${i}`}
        scrollEnabled={false}
        renderItem={({ item }) => (
          <View style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.ing}>{item.ingredient}</Text>
              <Text style={styles.prod}>{item.product_name}</Text>
              {item.block_reason && <Text style={styles.block}>{item.block_reason}</Text>}
            </View>
            <Text style={styles.price}>
              {item.quantity} {item.unit} · ${item.line_total.toFixed(2)}
            </Text>
          </View>
        )}
        ListEmptyComponent={
          <Text style={styles.empty}>
            {shopList.items.length === 0
              ? "Nothing to show yet."
              : tab === "addable"
                ? `No auto-add items — try Manual (${manual.length}) if you see estimated prices.`
                : "No items in this tab."}
          </Text>
        }
      />

      {(appState?.budget_suggestions?.length ?? 0) > 0 && (
        <Card style={{ marginTop: 16 }}>
          <CardHeader>
            <H2>Budget suggestions</H2>
          </CardHeader>
          <CardBody>
            {appState!.budget_suggestions.slice(0, 3).map((s, i) => (
              <Text key={i} style={styles.suggestion}>
                {s.ingredient}: save ${s.savings.toFixed(2)}
              </Text>
            ))}
          </CardBody>
        </Card>
      )}

      <StepNavBar position="bottom">{navButtons}</StepNavBar>
    </WizardShell>
  );
}

const styles = StyleSheet.create({
  summary: { fontSize: 14, color: theme.text, marginBottom: 8 },
  banner: {
    marginTop: 12,
    padding: 12,
    backgroundColor: "#fffbeb",
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#fde68a",
  },
  bannerText: { fontSize: 13, color: "#92400e" },
  tabs: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginVertical: 16 },
  tab: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, backgroundColor: theme.white },
  tabActive: { backgroundColor: "#ecfdf5" },
  tabText: { fontSize: 13, color: theme.textMuted },
  tabTextActive: { color: theme.green, fontWeight: "700" },
  row: {
    flexDirection: "row",
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
    gap: 8,
  },
  ing: { fontWeight: "600", color: theme.text },
  prod: { fontSize: 12, color: theme.textMuted, marginTop: 2 },
  block: { fontSize: 11, color: theme.red, marginTop: 4 },
  price: { fontSize: 13, color: theme.text, fontWeight: "600" },
  empty: { color: theme.textMuted, padding: 16 },
  suggestion: { fontSize: 13, color: theme.text, marginBottom: 4 },
});
