import { useRouter } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import type { Meal } from "@meal-agent/app-core";
import { WizardShell } from "@/components/WizardShell";
import { useApp } from "@/context/AppProvider";
import { Button } from "@/components/ui/Button";
import { StepNavBar } from "@/components/StepNavBar";
import { Card, CardBody, CardHeader, H2, Muted } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { theme } from "@/constants/theme";
import { api } from "@/lib/api";
import { useWizardNav } from "@/lib/useWizardNav";

const SLOTS = ["breakfast", "lunch", "dinner", "snack"] as const;
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function PlanScreen() {
  const router = useRouter();
  const {
    mealPlan,
    loading,
    setLoading,
    setMealPlan,
    setShopList,
    setMeals,
    setAppState,
    setError,
    markStepReached,
    resetDownstreamFromPlan,
  } = useApp();
  const { showForward, goForward } = useWizardNav();
  const [selected, setSelected] = useState<Meal | null>(null);
  const [checked, setChecked] = useState<Set<number>>(() => new Set());

  const { grid, indexByKey, mealCount } = useMemo(() => {
    if (!mealPlan) {
      return {
        grid: null as Record<string, Record<string, Meal | undefined>> | null,
        indexByKey: {} as Record<string, number>,
        mealCount: 0,
      };
    }
    const map: Record<string, Record<string, Meal | undefined>> = {};
    const keys: Record<string, number> = {};
    for (const slot of SLOTS) map[slot] = {};
    mealPlan.meals.forEach((meal, index) => {
      map[meal.slot][meal.day_label] = meal;
      keys[`${meal.day_label}|${meal.slot}`] = index;
    });
    return { grid: map, indexByKey: keys, mealCount: mealPlan.meals.length };
  }, [mealPlan]);

  useEffect(() => {
    setChecked(new Set());
    setSelected(null);
  }, [mealPlan]);

  if (!mealPlan || !grid) {
    return (
      <WizardShell>
        <Text>No meal plan yet.</Text>
        <Button title="Choose chef" onPress={() => router.push("/chef")} />
      </WizardShell>
    );
  }

  const checkedCount = checked.size;
  const allSelected = mealCount > 0 && checkedCount === mealCount;

  const toggleMeal = (index: number) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const selectAll = () => {
    setChecked(new Set(mealPlan.meals.map((_, i) => i)));
  };

  const clearSelection = () => setChecked(new Set());

  const regenerateSelected = async () => {
    if (checkedCount === 0) return;
    setLoading(true);
    setError("");
    try {
      const res = await api.regeneratePlan([...checked].sort((a, b) => a - b));
      setMealPlan(res.meal_plan);
      setShopList(null);
      resetDownstreamFromPlan();
      setChecked(new Set());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to regenerate meals");
    } finally {
      setLoading(false);
    }
  };

  const approve = async () => {
    setLoading(true);
    try {
      const res = await api.approvePlan();
      setMeals((res.meals ?? res.dinners) as Meal[]);
      setAppState(res.state);
      markStepReached(3);
      router.push("/recipes");
    } finally {
      setLoading(false);
    }
  };

  const regenBar = (
    <View style={styles.regenBar}>
      <Text style={styles.regenHint}>
        Tick meals to regenerate
        {checkedCount > 0 ? ` (${checkedCount} selected)` : ""}
      </Text>
      <View style={styles.regenActions}>
        <Button
          title={allSelected ? "Clear all" : "Select all"}
          variant="secondary"
          onPress={allSelected ? clearSelection : selectAll}
          disabled={loading || mealCount === 0}
        />
        <Button
          title={
            checkedCount === 0
              ? "Regenerate selected"
              : `Regenerate selected (${checkedCount})`
          }
          onPress={regenerateSelected}
          loading={loading}
          disabled={loading || checkedCount === 0}
          testID="plan-regenerate-selected"
        />
      </View>
    </View>
  );

  const navButtons = (
    <>
      <Button title="← Back" variant="secondary" onPress={() => router.push("/chef")} />
      {showForward ? <Button title="Forward →" variant="secondary" onPress={goForward} /> : null}
      <Button title="Approve plan →" onPress={approve} loading={loading} testID="plan-approve" />
    </>
  );

  return (
    <WizardShell>
      <StepNavBar position="top">{navButtons}</StepNavBar>
      {mealPlan.chef_notes ? (
        <Card style={{ marginBottom: 16 }}>
          <CardBody>
            <Text style={styles.notes}>{mealPlan.chef_notes}</Text>
          </CardBody>
        </Card>
      ) : null}

      {regenBar}

      {DAYS.map((day) => (
        <Card key={day} style={{ marginBottom: 12 }}>
          <CardHeader>
            <H2>{day}</H2>
          </CardHeader>
          <CardBody>
            {SLOTS.map((slot) => {
              const meal = grid[slot][day];
              if (!meal) return null;
              const index = indexByKey[`${day}|${slot}`];
              const isChecked = checked.has(index);
              return (
                <View key={slot} style={styles.mealRow}>
                  <Pressable
                    accessibilityRole="checkbox"
                    accessibilityState={{ checked: isChecked }}
                    accessibilityLabel={`Select ${meal.name} for regenerate`}
                    onPress={() => toggleMeal(index)}
                    style={[styles.checkbox, isChecked && styles.checkboxChecked]}
                    testID={`plan-meal-check-${index}`}
                  >
                    {isChecked ? <Text style={styles.checkboxMark}>✓</Text> : null}
                  </Pressable>
                  <Pressable style={styles.mealMain} onPress={() => setSelected(meal)}>
                    <Badge>{slot}</Badge>
                    <Text style={styles.mealName} selectable={false}>
                      {meal.name}
                    </Text>
                    <Text style={styles.prep}>{meal.prep_time_minutes}m</Text>
                  </Pressable>
                </View>
              );
            })}
          </CardBody>
        </Card>
      ))}

      {regenBar}

      {selected && (
        <Card style={{ marginTop: 8 }}>
          <CardHeader>
            <H2>{selected.name}</H2>
            <Muted>{selected.description}</Muted>
          </CardHeader>
          <CardBody>
            {selected.ingredients.map((ing, i) => (
              <Text key={i} style={styles.ing}>
                • {ing.quantity} {ing.unit} {ing.name}
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
  notes: { fontSize: 14, color: theme.textMuted, fontStyle: "italic" },
  regenBar: {
    marginBottom: 14,
    padding: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.white,
    gap: 10,
  },
  regenHint: {
    fontSize: 13,
    fontWeight: "600",
    color: theme.textMuted,
  },
  regenActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  mealRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: 6,
    borderWidth: 2,
    borderColor: theme.border,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.white,
  },
  checkboxChecked: {
    borderColor: theme.green,
    backgroundColor: theme.green,
  },
  checkboxMark: {
    color: theme.white,
    fontSize: 14,
    fontWeight: "800",
    lineHeight: 16,
  },
  mealMain: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  mealName: { flex: 1, fontWeight: "600", color: theme.text },
  prep: { fontSize: 12, color: theme.textMuted },
  ing: { fontSize: 13, color: theme.text, marginBottom: 4 },
});
