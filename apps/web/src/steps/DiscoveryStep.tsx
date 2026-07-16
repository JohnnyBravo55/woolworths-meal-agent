import type { DiscoveryAnswers } from "../types";
import { Button } from "../components/ui/Button";
import { Card, CardBody, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";

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
  const set = (patch: Partial<DiscoveryAnswers>) => onChange({ ...answers, ...patch });

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-6">
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Household</h2>
          </CardHeader>
          <CardBody className="grid gap-4 sm:grid-cols-2">
            <Field label="People">
              <StepperInput
                value={answers.household_size}
                onChange={(v) => set({ household_size: v })}
                min={1}
                max={8}
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
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                value={answers.allergies}
                onChange={(e) => set({ allergies: e.target.value })}
                placeholder="gluten, nuts"
              />
            </Field>
            <Field label="Mandatory items each shop">
              <input
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                value={answers.mandatory_items}
                onChange={(e) => set({ mandatory_items: e.target.value })}
                placeholder="milk, gluten free bread"
              />
            </Field>
            <Field label="Already have at home (pantry)">
              <input
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                value={answers.pantry_items}
                onChange={(e) => set({ pantry_items: e.target.value })}
                placeholder="olive oil, rice, soy sauce — chef uses these, won't shop for them"
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
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                rows={3}
                value={answers.other_instructions}
                onChange={(e) => set({ other_instructions: e.target.value })}
                placeholder="e.g. oven & microwave only — no stovetop cooking; 3 dinners curry-based"
              />
            </Field>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold">Budget &amp; store</h2>
          </CardHeader>
          <CardBody className="grid gap-4 sm:grid-cols-2">
            <Field label="Weekly budget (NZD)">
              <input
                type="number"
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                value={answers.budget_nzd}
                onChange={(e) => set({ budget_nzd: Number(e.target.value) })}
              />
            </Field>
            <Field label="Store (suburb)">
              <input
                className="w-full rounded-lg border border-slate-300 px-3 py-2"
                value={answers.store_name}
                onChange={(e) => set({ store_name: e.target.value })}
                placeholder="Ferrymead"
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
            <Badge tone="default">${answers.budget_nzd} budget</Badge>
            {answers.allergies && <Badge tone="warning">Allergies: {answers.allergies}</Badge>}
            {answers.pantry_items && (
              <Badge tone="default">Pantry: {answers.pantry_items}</Badge>
            )}
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
              <Button onClick={onContinue} disabled={loading}>
                {loading ? "Saving…" : "Choose your chef →"}
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
