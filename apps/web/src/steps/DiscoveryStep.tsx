import { useState } from "react";
import type { ChildrenAgeBands, DiscoveryAnswers } from "../types";
import {
  EMPTY_AGE_BANDS,
  ageBandsSum,
  clampAgeBandValue,
  maxForAgeBand,
  trimAgeBandsToChildren,
} from "../types";
import { Button } from "../components/ui/Button";
import { Card, CardBody, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";

const AGE_BAND_LABELS: { key: keyof ChildrenAgeBands; label: string }[] = [
  { key: "1-3", label: "1–3 years" },
  { key: "4-6", label: "4–6 years" },
  { key: "7-9", label: "7–9 years" },
  { key: "10-12", label: "10–12 years" },
];

const MAX_HOUSEHOLD = 8;

interface Props {
  answers: DiscoveryAnswers;
  onChange: (answers: DiscoveryAnswers) => void;
  onContinue: () => void;
  onSaveProfile: () => void;
  onLoadProfile: (id: string) => void;
  profiles: { id: string; name: string }[];
  loading: boolean;
  woolworthsConnected: boolean | null;
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block text-sm">
      <span className="font-medium text-slate-700">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function StepperInput({
  value,
  onChange,
  min = 0,
  max = 20,
}: {
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
}) {
  const clamp = (n: number) => Math.min(max, Math.max(min, n));

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        className="h-9 w-9 rounded-lg border border-slate-300 bg-white text-lg"
        onClick={() => onChange(clamp(value - 1))}
      >
        −
      </button>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => {
          const raw = e.target.value;
          if (raw === "") return;
          onChange(clamp(Number(raw)));
        }}
        className="w-14 rounded-lg border border-slate-300 px-2 py-1.5 text-center font-semibold"
      />
      <button
        type="button"
        className="h-9 w-9 rounded-lg border border-slate-300 bg-white text-lg"
        onClick={() => onChange(clamp(value + 1))}
      >
        +
      </button>
    </div>
  );
}

export function DiscoveryStep({
  answers,
  onChange,
  onContinue,
  onSaveProfile,
  onLoadProfile,
  profiles,
  loading,
  woolworthsConnected,
}: Props) {
  const [ageError, setAgeError] = useState("");

  const set = (patch: Partial<DiscoveryAnswers>) => {
    const next = { ...answers, ...patch, store_name: "" };
    const adults = Math.max(0, next.adults ?? 0);
    const children = Math.max(0, next.children_under_13 ?? 0);
    next.adults = adults;
    next.children_under_13 = children;
    next.household_size = Math.max(1, adults + children);
    if (children === 0) {
      next.children_age_bands = { ...EMPTY_AGE_BANDS };
    } else if (patch.children_under_13 !== undefined) {
      next.children_age_bands = trimAgeBandsToChildren(
        next.children_age_bands || EMPTY_AGE_BANDS,
        children,
      );
    }
    onChange(next);
    if (ageError) setAgeError("");
  };

  const setAdults = (v: number) => {
    const maxAdults = Math.max(0, MAX_HOUSEHOLD - (answers.children_under_13 || 0));
    set({ adults: Math.min(v, maxAdults) });
  };

  const setChildren = (v: number) => {
    const maxChildren = Math.max(0, MAX_HOUSEHOLD - (answers.adults || 0));
    set({ children_under_13: Math.min(v, maxChildren) });
  };

  const setBand = (key: keyof ChildrenAgeBands, v: number) => {
    const bands = answers.children_age_bands || EMPTY_AGE_BANDS;
    set({
      children_age_bands: clampAgeBandValue(
        bands,
        key,
        v,
        answers.children_under_13 || 0,
      ),
    });
  };

  const handleContinue = () => {
    const children = answers.children_under_13 || 0;
    if (children > 0) {
      const bands = answers.children_age_bands || EMPTY_AGE_BANDS;
      if (ageBandsSum(bands) !== children) {
        setAgeError("Assign an age for each child");
        return;
      }
    }
    setAgeError("");
    onContinue();
  };

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-6">
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Household</h2>
          </CardHeader>
          <CardBody className="grid gap-4 sm:grid-cols-2">
            <Field label="Adult portions">
              <p className="mb-1 text-xs text-slate-500">People 13+</p>
              <StepperInput
                value={answers.adults ?? 2}
                onChange={setAdults}
                min={1}
                max={MAX_HOUSEHOLD}
              />
            </Field>
            <Field label="Child portions">
              <p className="mb-1 text-xs text-slate-500">Children 12 and under</p>
              <StepperInput
                value={answers.children_under_13 ?? 0}
                onChange={setChildren}
                min={0}
                max={MAX_HOUSEHOLD}
              />
            </Field>
            <Field label="Days">
              <div className="flex gap-2">
                {[7, 14].map((d) => (
                  <button
                    key={d}
                    type="button"
                    onClick={() => set({ days: d })}
                    className={`rounded-lg px-4 py-2 text-sm font-medium border ${
                      answers.days === d
                        ? "border-[var(--ww-green)] bg-green-50 text-[var(--ww-green)]"
                        : "border-slate-300 bg-white"
                    }`}
                  >
                    {d} days
                  </button>
                ))}
              </div>
            </Field>
            {(answers.children_under_13 ?? 0) > 0 && (
              <div className="sm:col-span-2 space-y-3 rounded-lg border border-slate-200 p-3">
                <p className="text-sm font-medium text-slate-700">Ages of children</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {AGE_BAND_LABELS.map(({ key, label }) => {
                    const bands = answers.children_age_bands || EMPTY_AGE_BANDS;
                    return (
                      <Field key={key} label={label}>
                        <StepperInput
                          value={bands[key] || 0}
                          onChange={(v) => setBand(key, v)}
                          min={0}
                          max={maxForAgeBand(bands, key, answers.children_under_13 || 0)}
                        />
                      </Field>
                    );
                  })}
                </div>
                {ageError && <p className="text-sm text-amber-700">{ageError}</p>}
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Meals</h2>
          </CardHeader>
          <CardBody className="grid gap-4 sm:grid-cols-3">
            <Field label="Dinners">
              <StepperInput value={answers.dinner_count} onChange={(v) => set({ dinner_count: v })} />
            </Field>
            <Field label="Lunches">
              <StepperInput value={answers.lunch_count} onChange={(v) => set({ lunch_count: v })} />
            </Field>
            <Field label="Snacks">
              <StepperInput value={answers.snack_count} onChange={(v) => set({ snack_count: v })} />
            </Field>
            {answers.lunch_count > 0 && (
              <div className="sm:col-span-3 space-y-2">
                <span className="text-sm font-medium text-slate-700">Lunch style</span>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => set({ lunch_mode: "practical" })}
                    className={`rounded-lg px-3 py-2 text-sm text-left border max-w-xs ${
                      answers.lunch_mode === "practical"
                        ? "border-[var(--ww-green)] bg-green-50"
                        : "border-slate-300"
                    }`}
                  >
                    <strong>Practical</strong> — bigger dinners, leftovers for lunch (wraps/sandwiches)
                  </button>
                  <button
                    type="button"
                    onClick={() => set({ lunch_mode: "original" })}
                    className={`rounded-lg px-3 py-2 text-sm text-left border max-w-xs ${
                      answers.lunch_mode === "original"
                        ? "border-[var(--ww-green)] bg-green-50"
                        : "border-slate-300"
                    }`}
                  >
                    <strong>Original meals</strong> — separate lunch recipes each day
                  </button>
                </div>
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Diet &amp; safety</h2>
          </CardHeader>
          <CardBody className="grid gap-4">
            <Field label="Allergies (comma-separated)">
              <input
                className="w-full rounded-lg border border-slate-300 px-3 py-2 placeholder:text-slate-400"
                value={answers.allergies}
                onChange={(e) => set({ allergies: e.target.value })}
                placeholder="e.g. gluten, nuts"
              />
            </Field>
            <Field label="Mandatory items each shop">
              <input
                className="w-full rounded-lg border border-slate-300 px-3 py-2 placeholder:text-slate-400"
                value={answers.mandatory_items}
                onChange={(e) => set({ mandatory_items: e.target.value })}
                placeholder="milk, gluten free bread"
              />
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Likes">
                <input
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  value={answers.likes}
                  onChange={(e) => set({ likes: e.target.value })}
                />
              </Field>
              <Field label="Dislikes">
                <input
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  value={answers.dislikes}
                  onChange={(e) => set({ dislikes: e.target.value })}
                />
              </Field>
            </div>
            <Field label="Other instructions">
              <textarea
                className="w-full rounded-lg border border-slate-300 px-3 py-2 placeholder:text-slate-400"
                rows={3}
                value={answers.other_instructions}
                onChange={(e) => set({ other_instructions: e.target.value })}
                placeholder="e.g. oven & microwave only — no stovetop cooking"
              />
            </Field>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Budget</h2>
          </CardHeader>
          <CardBody className="grid gap-4 sm:grid-cols-2">
            <Field label="Weekly budget NZD (optional)">
              <input
                type="number"
                className="w-full rounded-lg border border-slate-300 px-3 py-2 placeholder:text-slate-400"
                value={answers.budget_nzd > 0 ? answers.budget_nzd : ""}
                onChange={(e) =>
                  set({ budget_nzd: e.target.value.trim() ? Number(e.target.value) || 0 : 0 })
                }
                placeholder="Leave blank for no hard budget"
              />
            </Field>
            <Field label="Brand preference">
              <div className="flex flex-wrap gap-2">
                {(["budget", "mixed", "premium"] as const).map((b) => (
                  <button
                    key={b}
                    type="button"
                    onClick={() => set({ brand_preference: b })}
                    className={`rounded-lg px-3 py-1.5 text-sm capitalize border ${
                      answers.brand_preference === b
                        ? "border-[var(--ww-green)] bg-green-50"
                        : "border-slate-300"
                    }`}
                  >
                    {b}
                  </button>
                ))}
              </div>
            </Field>
            <Field label="Complexity">
              <div className="flex flex-wrap gap-2">
                {(["simple", "moderate", "ambitious"] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => set({ simplicity: s })}
                    className={`rounded-lg px-3 py-1.5 text-sm capitalize border ${
                      answers.simplicity === s
                        ? "border-[var(--ww-green)] bg-green-50"
                        : "border-slate-300"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </Field>
          </CardBody>
        </Card>
      </div>

      <div className="space-y-4">
        <Card className="sticky top-4">
          <CardHeader>
            <h2 className="text-lg font-semibold">Summary</h2>
          </CardHeader>
          <CardBody className="space-y-3 text-sm text-slate-700">
            <p>
              Shopping for <strong>{answers.household_size}</strong> people ·{" "}
              <strong>{answers.days}</strong> days
            </p>
            <p>
              ~{answers.dinner_count} dinners, {answers.lunch_count} lunches, {answers.snack_count}{" "}
              snacks
            </p>
            {answers.lunch_count > 0 && (
              <p className="text-xs text-slate-500">
                Lunches: {answers.lunch_mode === "practical" ? "practical (leftovers)" : "original recipes"}
              </p>
            )}
            {answers.budget_nzd > 0 ? (
              <Badge tone="default">${answers.budget_nzd} budget</Badge>
            ) : (
              <Badge tone="default">No hard budget</Badge>
            )}
            {answers.allergies && <Badge tone="warning">Allergies: {answers.allergies}</Badge>}
            {woolworthsConnected === false && (
              <p className="text-amber-700 text-xs">
                Connect Woolworths for live prices. Plans still work with estimates.
              </p>
            )}
            <div className="pt-3 flex flex-col gap-2">
              <select
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
                defaultValue=""
                onChange={(e) => e.target.value && onLoadProfile(e.target.value)}
              >
                <option value="" disabled>
                  Load profile…
                </option>
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <Button variant="secondary" onClick={onSaveProfile}>
                Save profile
              </Button>
              <Button onClick={handleContinue} disabled={loading}>
                {loading ? "Saving…" : "Choose your chef →"}
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
