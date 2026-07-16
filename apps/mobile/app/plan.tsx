import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
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
  const { mealPlan, answers, loading, setLoading, setMealPlan, setShopList, setMeals, setAppState, markStepReached, resetDownstreamFromPlan } =
    useApp();
  const { showForward, goForward } = useWizardNav();
  const [selected, setSelected] = useState<Meal | null>(null);

  const grid = useMemo(() => {
    if (!mealPlan) return null;
    const map: Record<string, Record<string, Meal | undefined>> = {};
    for (const slot of SLOTS) map[slot] = {};
    for (const meal of mealPlan.meals) {
      map[meal.slot][meal.day_label] = meal;
    }
    return map;
  }, [mealPlan]);

  if (!mealPlan || !grid) {
    return (
      <WizardShell>
        <Text>No meal plan yet.</Text>
        <Button title="Choose chef" onPress={() => router.push("/chef")} />
      </WizardShell>
    );
  }

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

  const navButtons = (
    <>
      <Button title="← Back" variant="secondary" onPress={() => router.push("/chef")} />
      {showForward ? <Button title="Forward →" variant="secondary" onPress={goForward} /> : null}
      <Button
        title="Regenerate"
        variant="secondary"
        loading={loading}
        onPress={async () => {
          setLoading(true);
          try {
            const res = await api.regeneratePlan();
            setMealPlan(res.meal_plan);
            setShopList(null);
            resetDownstreamFromPlan();
          } finally {
            setLoading(false);
          }
        }}
      />
      <Button title="Approve plan →" onPress={approve} loading={loading} />
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

      {DAYS.map((day) => (
        <Card key={day} style={{ marginBottom: 12 }}>
          <CardHeader>
            <H2>{day}</H2>
          </CardHeader>
          <CardBody>
            {SLOTS.map((slot) => {
              const meal = grid[slot][day];
              if (!meal) return null;
              return (
                <Pressable key={slot} style={styles.mealRow} onPress={() => setSelected(meal)}>
                  <Badge>{slot}</Badge>
                  <Text style={styles.mealName}>{meal.name}</Text>
                  <Text style={styles.prep}>{meal.prep_time_minutes}m</Text>
                </Pressable>
              );
            })}
          </CardBody>
        </Card>
      ))}

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
  mealRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
  },
  mealName: { flex: 1, fontWeight: "600", color: theme.text },
  prep: { fontSize: 12, color: theme.textMuted },
  ing: { fontSize: 13, color: theme.text, marginBottom: 4 },
});
