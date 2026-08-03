import { useRouter } from "expo-router";
import { useCallback, useMemo, useRef, useState } from "react";
import { FlatList, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import type { Meal, ResolvedGroceryList } from "@meal-agent/app-core";
import { WizardShell } from "@/components/WizardShell";
import { useApp } from "@/context/AppProvider";
import { Button } from "@/components/ui/Button";
import { StepNavBar } from "@/components/StepNavBar";
import { Card, CardBody, CardHeader, H2, Muted } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ParallelLoadingModal } from "@/components/ParallelLoadingModal";
import { theme } from "@/constants/theme";
import { api, getApiBaseUrl } from "@/lib/api";
import { isHostedApiUrl } from "@/lib/config";
import { needsWoolworthsSignInBeforeShop } from "@/lib/woolworths-mobile";
import { useWizardNav } from "@/lib/useWizardNav";

const SLOT_ORDER: Record<string, number> = { breakfast: 0, lunch: 1, snack: 2, dinner: 3 };
const SLOT_LABEL: Record<string, string> = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  snack: "Snack",
  dinner: "Dinner",
};
const DAY_ORDER = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

function dayRank(day: string): number {
  const idx = DAY_ORDER.findIndex((d) => d.toLowerCase() === day.toLowerCase());
  return idx === -1 ? 99 : idx;
}

function groupByDay(meals: Meal[]) {
  const byDay = new Map<string, Meal[]>();
  for (const meal of meals) {
    const day = meal.day_label || "Unscheduled";
    if (!byDay.has(day)) byDay.set(day, []);
    byDay.get(day)!.push(meal);
  }
  return Array.from(byDay.entries())
    .sort((a, b) => dayRank(a[0]) - dayRank(b[0]))
    .map(([day, dayMeals]) => ({
      day,
      meals: [...dayMeals].sort((a, b) => (SLOT_ORDER[a.slot] ?? 9) - (SLOT_ORDER[b.slot] ?? 9)),
    }));
}

export default function RecipesScreen() {
  const router = useRouter();
  const {
    meals,
    shopList,
    pantryToBuy,
    setPantryToBuy,
    loading,
    setLoading,
    setShopList,
    setAppState,
    setError,
    resolveProgress,
    setResolveProgress,
    refreshWoolworths,
    markStepReached,
  } = useApp();
  const { showForward, goForward } = useWizardNav();

  const [awaitingWoolworths, setAwaitingWoolworths] = useState(false);
  const [expandedMeals, setExpandedMeals] = useState<Set<string>>(() => new Set());
  const pendingResolve = useRef<{ force: boolean } | null>(null);
  const isWeb = Platform.OS === "web";

  const pantryItems = useMemo(() => {
    const seen = new Set<string>();
    const ordered: string[] = [];
    for (const meal of meals) {
      for (const ing of meal.ingredients) {
        if (!ing.is_pantry) continue;
        const name = ing.name.trim().toLowerCase();
        if (!name || seen.has(name)) continue;
        seen.add(name);
        ordered.push(name);
      }
    }
    return ordered;
  }, [meals]);

  const byDay = useMemo(() => groupByDay(meals), [meals]);
  const mealRows = useMemo(
    () =>
      byDay.flatMap(({ day, meals: dayMeals }) => [
        { kind: "day" as const, key: `day-${day}`, day },
        ...dayMeals.map((meal, idx) => ({
          kind: "meal" as const,
          key: `${day}-${idx}-${meal.name}`,
          day,
          meal,
          idx,
        })),
      ]),
    [byDay],
  );

  const toggleIngredients = (key: string) => {
    setExpandedMeals((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const runResolveSSE = useCallback(
    async (force: boolean) => {
      let completed = false;
      try {
        await api.streamSSE(`/api/shop/resolve${force ? "?force=true" : ""}`, (event, data) => {
          if (event === "status") {
            setResolveProgress((prev) => ({
              done: Number(data.done ?? prev.done),
              total: Number(data.total ?? prev.total),
              message: String(data.message || prev.message),
              phase: String(data.phase || prev.phase || "search"),
              ingredient: "",
            }));
          }
          if (event === "progress") {
            setResolveProgress((prev) => ({
              done: Number(data.done),
              total: Number(data.total),
              ingredient: String(data.ingredient || ""),
              phase: String(data.phase || prev.phase || "search"),
              message: prev.message,
            }));
          }
          if (event === "complete") {
            completed = true;
            setShopList(data.resolved_list as ResolvedGroceryList);
            setAppState(data.state as never);
            markStepReached(4);
            router.push("/shop");
          }
          if (event === "error") setError(String(data.message));
        });
        if (!completed) {
          setError(
            isHostedApiUrl(getApiBaseUrl())
              ? "Product search ended early — the hosted API may have dropped the connection. Try again."
              : "Product search ended early — check meal-agent-api is running on port 8000.",
          );
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Product search failed");
      } finally {
        setLoading(false);
        pendingResolve.current = null;
      }
    },
    [router, setAppState, setError, setLoading, setResolveProgress, setShopList, markStepReached],
  );

  const resolve = async (force = false) => {
    if (shopList && !force) {
      markStepReached(4);
      router.push("/shop");
      return;
    }
    setError("");

    try {
      await api.setPantryToBuy(pantryToBuy);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save pantry ticks");
      return;
    }

    // Web: never prompt Connect / extension — go straight to product search.
    // Phone: still require WebView link when needed.
    if (!isWeb && (await needsWoolworthsSignInBeforeShop())) {
      pendingResolve.current = { force };
      setAwaitingWoolworths(true);
      return;
    }

    setLoading(true);
    setResolveProgress({
      done: 0,
      total: 0,
      ingredient: "",
      phase: "search",
      message: "Starting product search…",
    });
    await runResolveSSE(force);
  };

  const cancelWoolworthsConnect = () => {
    setAwaitingWoolworths(false);
    pendingResolve.current = null;
  };

  const onWoolworthsLinked = () => {
    setAwaitingWoolworths(false);
    refreshWoolworths();
    const pending = pendingResolve.current;
    if (pending) {
      setLoading(true);
      setResolveProgress({
        done: 0,
        total: 0,
        ingredient: "",
        phase: "search",
        message: "Starting product search…",
      });
      void runResolveSSE(pending.force);
    }
  };

  const navButtons = (
    <>
      <Button title="← Back" variant="secondary" onPress={() => router.push("/plan")} disabled={loading} />
      {showForward ? (
        <Button title="Forward →" variant="secondary" onPress={goForward} disabled={loading} />
      ) : null}
      <Button
        title={shopList ? "Re-build shop list" : "Build shop list →"}
        onPress={() => resolve(!!shopList)}
        loading={loading}
        disabled={awaitingWoolworths}
        testID="recipes-build-shop"
      />
      {shopList ? (
        <Button title="Continue to shop list →" variant="secondary" onPress={() => router.push("/shop")} />
      ) : null}
    </>
  );

  const listHeader = (
    <>
      <StepNavBar position="top">{navButtons}</StepNavBar>

      {pantryItems.length > 0 ? (
        <Card>
          <CardHeader>
            <H2>Required pantry items</H2>
            <Muted>Tick to add item to shopping list</Muted>
          </CardHeader>
          <CardBody>
            {pantryItems.map((name) => {
              const checked = pantryToBuy.includes(name);
              return (
                <Pressable
                  key={name}
                  style={styles.pantryRow}
                  onPress={() => {
                    setShopList(null);
                    setPantryToBuy((prev) =>
                      checked ? prev.filter((x) => x !== name) : [...prev, name],
                    );
                  }}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked }}
                >
                  <Text style={styles.pantryCheck}>{checked ? "☑" : "☐"}</Text>
                  <Text style={styles.pantryLabel}>{name}</Text>
                </Pressable>
              );
            })}
          </CardBody>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <H2>Your week of recipes</H2>
          <Muted>{meals.length} meals</Muted>
        </CardHeader>
        <CardBody>
          <Text style={styles.hint}>
            {isWeb
              ? "Build your shop list from these recipes. Filling a supermarket trolley is coming soon."
              : "Connect Woolworths before we build your shop list. Sign in when prompted, then product search begins automatically."}
          </Text>
        </CardBody>
      </Card>
    </>
  );

  return (
    <WizardShell scrollable={false}>
      <ParallelLoadingModal
        visible={loading || (!isWeb && awaitingWoolworths)}
        title="Building your shop list"
        message={resolveProgress.message || "Searching Woolworths products…"}
        done={resolveProgress.done}
        total={resolveProgress.total}
        ingredient={resolveProgress.ingredient}
        showWoolworths={!isWeb && awaitingWoolworths}
        woolworthsOnly={!isWeb && awaitingWoolworths}
        woolworthsTitle="Connect to Woolworths"
        woolworthsHint="Sign in first — your shop list will build once your account is connected."
        onWoolworthsLinked={onWoolworthsLinked}
        onWoolworthsError={setError}
        onCancelWoolworths={cancelWoolworthsConnect}
      />

      <FlatList
        style={styles.list}
        data={mealRows}
        extraData={expandedMeals}
        keyExtractor={(item) => item.key}
        contentContainerStyle={styles.listContent}
        initialNumToRender={8}
        maxToRenderPerBatch={6}
        windowSize={7}
        removeClippedSubviews={Platform.OS !== "web"}
        ListHeaderComponent={listHeader}
        ListFooterComponent={<StepNavBar position="bottom">{navButtons}</StepNavBar>}
        renderItem={({ item }) => {
          if (item.kind === "day") {
            return <Text style={styles.dayLabel}>{item.day.toUpperCase()}</Text>;
          }
          const { meal, key } = item;
          const expanded = expandedMeals.has(key);
          const shopIngredients = meal.ingredients.filter((ing) => !ing.is_pantry);
          const pantryNames = meal.ingredients
            .filter((ing) => ing.is_pantry)
            .map((ing) => ing.name.trim().toLowerCase())
            .filter(Boolean);
          const pantryNote =
            pantryNames.length > 0
              ? `Uses pantry: ${[...new Set(pantryNames)].join(", ")}`
              : null;
          const ingredientCount = shopIngredients.length;
          return (
            <Card style={styles.mealCard}>
              <CardHeader>
                <Text style={styles.slot}>{SLOT_LABEL[meal.slot] ?? meal.slot}</Text>
                <H2>{meal.name}</H2>
                <Badge>{meal.prep_time_minutes} min</Badge>
              </CardHeader>
              <CardBody>
                <Muted>{meal.description}</Muted>
                {pantryNote ? <Text style={styles.pantryNote}>{pantryNote}</Text> : null}
                {ingredientCount > 0 ? (
                  <View style={styles.ingBlock}>
                    <Pressable
                      onPress={() => toggleIngredients(key)}
                      accessibilityRole="button"
                      accessibilityState={{ expanded }}
                      testID={`recipes-toggle-ing-${key}`}
                    >
                      <Text style={styles.ingToggle}>
                        {expanded ? "Hide" : "Show"} ingredients ({ingredientCount})
                      </Text>
                    </Pressable>
                    {expanded
                      ? shopIngredients.map((ing, i) => (
                          <Text key={i} style={styles.ing}>
                            • {ing.quantity} {ing.unit} {ing.name}
                          </Text>
                        ))
                      : null}
                  </View>
                ) : null}
              </CardBody>
            </Card>
          );
        }}
      />
    </WizardShell>
  );
}

const styles = StyleSheet.create({
  list: { flex: 1 },
  listContent: { paddingBottom: 160 },
  dayLabel: {
    marginTop: 12,
    marginBottom: 4,
    fontSize: 12,
    fontWeight: "700",
    color: theme.muted,
    letterSpacing: 0.6,
  },
  mealCard: { marginBottom: 10 },
  slot: { fontSize: 11, fontWeight: "600", color: theme.green, textTransform: "uppercase" },
  hint: { color: theme.muted, fontSize: 13, lineHeight: 18 },
  ingBlock: { marginTop: 10 },
  ingToggle: { color: theme.green, fontWeight: "600", marginBottom: 6 },
  ing: { color: theme.text, fontSize: 13, marginBottom: 2 },
  pantryRow: { flexDirection: "row", alignItems: "center", gap: 8, paddingVertical: 6 },
  pantryCheck: { fontSize: 18, width: 24 },
  pantryLabel: { fontSize: 14, color: theme.text, textTransform: "capitalize" },
  pantryNote: { marginTop: 8, fontSize: 13, fontStyle: "italic", color: theme.muted },
});
