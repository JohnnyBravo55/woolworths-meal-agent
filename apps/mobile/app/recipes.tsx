import { useRouter } from "expo-router";
import { useCallback, useRef, useState } from "react";
import { Platform, StyleSheet, Text, View } from "react-native";
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
  const pendingResolve = useRef<{ force: boolean } | null>(null);
  const isWeb = Platform.OS === "web";

  const byDay = groupByDay(meals);

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

  return (
    <WizardShell>
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

      <StepNavBar position="top">{navButtons}</StepNavBar>

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

      {byDay.map(({ day, meals: dayMeals }) => (
        <View key={day} style={{ marginTop: 16 }}>
          <Text style={styles.dayLabel}>{day.toUpperCase()}</Text>
          {dayMeals.map((meal, idx) => (
            <Card key={`${day}-${idx}`} style={{ marginTop: 8 }}>
              <CardHeader>
                <Text style={styles.slot}>{SLOT_LABEL[meal.slot] ?? meal.slot}</Text>
                <H2>{meal.name}</H2>
                <Badge>{meal.prep_time_minutes} min</Badge>
              </CardHeader>
              <CardBody>
                <Muted>{meal.description}</Muted>
                {meal.ingredients.length > 0 && (
                  <View style={{ marginTop: 8 }}>
                    {meal.ingredients.map((ing, i) => (
                      <Text key={i} style={styles.ing}>
                        • {ing.quantity} {ing.unit} {ing.name}
                      </Text>
                    ))}
                  </View>
                )}
              </CardBody>
            </Card>
          ))}
        </View>
      ))}

      <StepNavBar position="bottom">{navButtons}</StepNavBar>
    </WizardShell>
  );
}

const styles = StyleSheet.create({
  hint: { fontSize: 13, color: theme.textMuted, lineHeight: 18 },
  dayLabel: { fontSize: 12, fontWeight: "700", color: theme.textMuted },
  slot: { fontSize: 11, fontWeight: "700", color: theme.green, textTransform: "uppercase" },
  ing: { fontSize: 13, color: theme.text },
});
