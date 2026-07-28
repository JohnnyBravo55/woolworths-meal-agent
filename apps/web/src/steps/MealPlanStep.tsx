import { useEffect, useMemo, useState } from "react";
import type { Meal, MealPlan } from "../types";
import { Button } from "../components/ui/Button";
import { Card, CardBody, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";

const SLOTS = ["breakfast", "lunch", "dinner", "snack"] as const;
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

interface Props {
  plan: MealPlan;
  allergies: string;
  onBack?: () => void;
  onApprove: () => void;
  onSwap: (index: number) => void;
  onRegenerate: (mealIndices: number[]) => void | Promise<void>;
  loading: boolean;
}

export function MealPlanStep({
  plan,
  allergies,
  onBack,
  onApprove,
  onSwap,
  onRegenerate,
  loading,
}: Props) {
  const [selected, setSelected] = useState<Meal | null>(null);
  const [allergyOk, setAllergyOk] = useState(!allergies);
  const [swapOpen, setSwapOpen] = useState(false);
  const [checked, setChecked] = useState<Set<number>>(() => new Set());

  const { grid, indexByKey } = useMemo(() => {
    const map: Record<string, Record<string, Meal | undefined>> = {};
    const keys: Record<string, number> = {};
    for (const slot of SLOTS) map[slot] = {};
    plan.meals.forEach((meal, index) => {
      map[meal.slot][meal.day_label] = meal;
      keys[`${meal.day_label}|${meal.slot}`] = index;
    });
    return { grid: map, indexByKey: keys };
  }, [plan]);

  useEffect(() => {
    setChecked(new Set());
    setSelected(null);
  }, [plan]);

  const checkedCount = checked.size;
  const allSelected = plan.meals.length > 0 && checkedCount === plan.meals.length;

  const toggleMeal = (index: number) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const selectAll = () => setChecked(new Set(plan.meals.map((_, i) => i)));
  const clearSelection = () => setChecked(new Set());

  const regenBar = (
    <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-3">
      <p className="text-sm font-semibold text-slate-600">
        Tick meals to regenerate
        {checkedCount > 0 ? ` (${checkedCount} selected)` : ""}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={allSelected ? clearSelection : selectAll}
          disabled={loading || plan.meals.length === 0}
        >
          {allSelected ? "Clear all" : "Select all"}
        </Button>
        <Button
          size="sm"
          onClick={() => onRegenerate([...checked].sort((a, b) => a - b))}
          disabled={loading || checkedCount === 0}
        >
          {checkedCount === 0
            ? "Regenerate selected"
            : `Regenerate selected (${checkedCount})`}
        </Button>
      </div>
    </div>
  );

  return (
    <div className="space-y-4">
      {plan.chef_notes && (
        <Card>
          <CardBody className="text-sm text-slate-700">
            <strong>Chef notes:</strong> {plan.chef_notes}
          </CardBody>
        </Card>
      )}

      {allergies && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm text-amber-900">
            Allergies: <strong>{allergies}</strong> — hard-blocked from all meals.
          </p>
          <label className="mt-2 flex items-center gap-2 text-sm">
            <input type="checkbox" checked={allergyOk} onChange={(e) => setAllergyOk(e.target.checked)} />
            I confirm these allergies are correct
          </label>
        </div>
      )}

      {regenBar}

      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-semibold">Week at a glance</h2>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={() => setSwapOpen(true)}>
              Swap meal…
            </Button>
            <Button size="sm" onClick={onApprove} disabled={loading || (!!allergies && !allergyOk)}>
              Approve plan →
            </Button>
          </div>
        </CardHeader>
        <CardBody className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr>
                <th className="p-2 text-left text-slate-500 font-medium" />
                {DAYS.map((d) => (
                  <th key={d} className="p-2 text-left text-slate-500 font-medium">
                    {d.slice(0, 3)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {SLOTS.map((slot) => (
                <tr key={slot} className="border-t border-slate-100">
                  <td className="p-2 capitalize text-slate-500 font-medium">{slot}</td>
                  {DAYS.map((day) => {
                    const meal = grid[slot][day];
                    const index = indexByKey[`${day}|${slot}`];
                    const isChecked = typeof index === "number" && checked.has(index);
                    return (
                      <td key={day} className="p-2 align-top">
                        {meal ? (
                          <div
                            className={`w-full rounded-lg border p-2 text-left ${
                              isChecked
                                ? "border-[var(--ww-green)] bg-green-50"
                                : "border-slate-200 bg-slate-50"
                            }`}
                          >
                            <label className="mb-2 flex items-center gap-2 text-xs text-slate-600 select-none">
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={() => toggleMeal(index)}
                                className="h-4 w-4 accent-[var(--ww-green)]"
                              />
                              Regenerate
                            </label>
                            <button
                              type="button"
                              onClick={() => setSelected(meal)}
                              className="w-full text-left"
                            >
                              <div className="font-medium text-slate-900 line-clamp-2">{meal.name}</div>
                              <Badge tone="default">{meal.prep_time_minutes}m</Badge>
                            </button>
                          </div>
                        ) : (
                          <span className="text-slate-300">—</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>

      {regenBar}

      {onBack ? (
        <div className="flex justify-start">
          <Button variant="secondary" onClick={onBack} disabled={loading}>
            ← Back to choose chef
          </Button>
        </div>
      ) : null}

      {selected && (
        <div className="fixed inset-y-0 right-0 z-40 w-full max-w-md border-l border-slate-200 bg-white p-6 shadow-xl overflow-y-auto">
          <button type="button" className="text-sm text-slate-500" onClick={() => setSelected(null)}>
            ← Close
          </button>
          <h3 className="mt-2 text-xl font-semibold">{selected.name}</h3>
          <p className="text-sm text-slate-600">{selected.description}</p>
          <h4 className="mt-4 font-medium">Ingredients</h4>
          <ul className="mt-2 space-y-1 text-sm text-slate-700">
            {selected.ingredients.map((ing, i) => (
              <li key={i}>
                {ing.quantity} {ing.unit} {ing.name}
              </li>
            ))}
          </ul>
        </div>
      )}

      {swapOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
            <h3 className="font-semibold">Swap a meal</h3>
            <ul className="mt-4 space-y-2">
              {plan.meals.map((meal, idx) => (
                <li key={idx}>
                  <button
                    type="button"
                    className="w-full rounded-lg border border-slate-200 p-3 text-left hover:bg-slate-50"
                    onClick={() => {
                      onSwap(idx);
                      setSwapOpen(false);
                    }}
                  >
                    <span className="text-slate-500 text-xs">{meal.day_label} · {meal.slot}</span>
                    <div className="font-medium">{meal.name}</div>
                  </button>
                </li>
              ))}
            </ul>
            <Button variant="secondary" className="mt-4" onClick={() => setSwapOpen(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
