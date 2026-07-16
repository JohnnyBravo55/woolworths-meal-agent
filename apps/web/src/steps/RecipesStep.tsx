import type { Meal } from "../types";
import { Button } from "../components/ui/Button";
import { Card, CardBody, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";

interface Props {
  meals: Meal[];
  onBack?: () => void;
  onContinue: () => void;
  onRefreshSearch: () => void;
  hasCachedList: boolean;
  onDownloadRecipes: () => void;
  resolving: boolean;
  progress: { done: number; total: number; ingredient?: string; phase?: string; message?: string };
}

const SLOT_ORDER: Record<string, number> = {
  breakfast: 0,
  lunch: 1,
  snack: 2,
  dinner: 3,
};

const SLOT_LABEL: Record<string, string> = {
  breakfast: "Breakfast",
  lunch: "Lunch",
  snack: "Snack",
  dinner: "Dinner",
};

function groupMealsByDay(meals: Meal[]): { day: string; meals: Meal[] }[] {
  const byDay = new Map<string, Meal[]>();
  for (const meal of meals) {
    const day = meal.day_label || "Unscheduled";
    if (!byDay.has(day)) byDay.set(day, []);
    byDay.get(day)!.push(meal);
  }
  return Array.from(byDay.entries()).map(([day, dayMeals]) => ({
    day,
    meals: [...dayMeals].sort(
      (a, b) => (SLOT_ORDER[a.slot] ?? 9) - (SLOT_ORDER[b.slot] ?? 9),
    ),
  }));
}

function resolveStatusLabel(progress: Props["progress"]): string {
  if (progress.phase === "validate") {
    return progress.message || "Checking products match your recipes…";
  }
  if (progress.phase === "budget") {
    return progress.message || "Reconciling budget…";
  }
  if (progress.message) return progress.message;
  return "Searching Woolworths…";
}

export function RecipesStep({
  meals,
  onBack,
  onContinue,
  onRefreshSearch,
  hasCachedList,
  onDownloadRecipes,
  resolving,
  progress,
}: Props) {
  const byDay = groupMealsByDay(meals);
  const slotCounts = meals.reduce(
    (acc, m) => {
      acc[m.slot] = (acc[m.slot] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );
  const summary = ["breakfast", "lunch", "snack", "dinner"]
    .filter((s) => slotCounts[s])
    .map((s) => `${slotCounts[s]} ${s}${slotCounts[s] > 1 ? "s" : ""}`)
    .join(" · ");

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-semibold">Your week of recipes</h2>
            <p className="text-sm text-slate-600">
              {meals.length} meals{summary ? ` · ${summary}` : ""}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={onDownloadRecipes}>
              Download recipes
            </Button>
            {hasCachedList && (
              <Button variant="secondary" onClick={onContinue} disabled={resolving}>
                Continue to shop list →
              </Button>
            )}
            <Button onClick={hasCachedList ? onRefreshSearch : onContinue} disabled={resolving}>
              {resolving
                ? "Searching Woolworths…"
                : hasCachedList
                  ? "Re-search all products"
                  : "Find Woolworths products →"}
            </Button>
          </div>
        </CardHeader>
        {resolving && (
          <CardBody>
            <div className="mb-2 flex justify-between text-sm text-slate-600">
              <span>
                {resolveStatusLabel(progress)}
                {progress.total > 0 && (
                  <>
                    {" "}
                    {progress.done}/{progress.total}
                  </>
                )}
                {progress.ingredient && progress.phase !== "budget"
                  ? `: ${progress.ingredient}`
                  : ""}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full bg-[var(--ww-green)] transition-all"
                style={{
                  width: `${
                    progress.total
                      ? Math.min(100, (progress.done / progress.total) * 100)
                      : progress.phase === "budget"
                        ? 100
                        : 0
                  }%`,
                }}
              />
            </div>
          </CardBody>
        )}
      </Card>

      <div className="space-y-6">
        {byDay.map(({ day, meals: dayMeals }) => (
          <div key={day} className="space-y-3">
            <h3 className="text-sm font-bold uppercase tracking-wide text-slate-500">{day}</h3>
            {dayMeals.map((meal, idx) => (
              <Card key={`${day}-${idx}`}>
                <CardHeader className="flex items-center justify-between">
                  <div>
                    <span className="text-xs font-medium uppercase text-[var(--ww-green)]">
                      {SLOT_LABEL[meal.slot] ?? meal.slot}
                    </span>
                    <h3 className="font-semibold text-slate-900">{meal.name}</h3>
                  </div>
                  <Badge>{meal.prep_time_minutes} min</Badge>
                </CardHeader>
                <CardBody className="text-sm text-slate-700 space-y-3">
                  <p>{meal.description}</p>
                  {meal.ingredients.length > 0 && (
                    <div>
                      <strong>Ingredients</strong>
                      <ul className="mt-1 list-disc pl-5">
                        {meal.ingredients.map((ing, i) => (
                          <li key={i}>
                            {ing.quantity} {ing.unit} {ing.name}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {meal.steps.length > 0 && (
                    <div>
                      <strong>Steps</strong>
                      <ol className="mt-1 list-decimal pl-5 space-y-1">
                        {meal.steps.map((step, i) => (
                          <li key={i}>{step}</li>
                        ))}
                      </ol>
                    </div>
                  )}
                </CardBody>
              </Card>
            ))}
          </div>
        ))}
      </div>

      {onBack ? (
        <div className="flex justify-start">
          <Button variant="secondary" onClick={onBack} disabled={resolving}>
            ← Back to meal plan
          </Button>
        </div>
      ) : null}
    </div>
  );
}
