import { needsSessionLossWarning } from "@meal-agent/app-core";
import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { WizardShell } from "@/components/WizardShell";
import { useApp } from "@/context/AppProvider";
import { Button } from "@/components/ui/Button";
import { ActionBar } from "@/components/ActionBar";
import { Card, CardBody, CardHeader, H2, Muted } from "@/components/ui/Card";
import { theme } from "@/constants/theme";
import { getApiBaseUrl } from "@/lib/config";
import { api } from "@/lib/api";
import { confirmSessionLoss } from "@/lib/confirm-session-loss";
import { useWizardNav } from "@/lib/useWizardNav";
import {
  EMPTY_AGE_BANDS,
  ageBandsSum,
  clampAgeBandValue,
  maxForAgeBand,
  profileToAnswers,
  trimAgeBandsToChildren,
  type ChildrenAgeBands,
  type DiscoveryAnswers,
} from "@meal-agent/app-core";
import { useState } from "react";

const AGE_BAND_LABELS: { key: keyof ChildrenAgeBands; label: string }[] = [
  { key: "1-3", label: "1–3 years" },
  { key: "4-6", label: "4–6 years" },
  { key: "7-9", label: "7–9 years" },
  { key: "10-12", label: "10–12 years" },
];

const MAX_HOUSEHOLD = 8;

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
    <View style={styles.stepper}>
      <Pressable style={styles.stepBtn} onPress={() => onChange(clamp(value - 1))}>
        <Text style={styles.stepBtnText}>−</Text>
      </Pressable>
      <Text style={styles.stepVal}>{value}</Text>
      <Pressable style={styles.stepBtn} onPress={() => onChange(clamp(value + 1))}>
        <Text style={styles.stepBtnText}>+</Text>
      </Pressable>
    </View>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={styles.field}>
      <Text style={styles.label}>{label}</Text>
      {children}
    </View>
  );
}

export default function DiscoveryScreen() {
  const router = useRouter();
  const {
    answers,
    setAnswers,
    loading,
    setLoading,
    setError,
    profiles,
    mealPlan,
    planChefId,
    selectedChefId,
    sessionBaseline,
    clearWizardSession,
    markStepReached,
  } = useApp();
  const { showForward, goForward } = useWizardNav();
  const [ageError, setAgeError] = useState("");

  const set = (patch: Partial<DiscoveryAnswers>) => {
    const next = { ...answers, ...patch };
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
    setAnswers(next);
    if (ageError) setAgeError("");
  };

  const setAdults = (v: number) => {
    const maxAdults = Math.max(1, MAX_HOUSEHOLD - (answers.children_under_13 || 0));
    set({ adults: Math.min(Math.max(1, v), maxAdults) });
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

  const continueNext = async () => {
    const children = answers.children_under_13 || 0;
    if (children > 0) {
      const bands = answers.children_age_bands || EMPTY_AGE_BANDS;
      if (ageBandsSum(bands) !== children) {
        setAgeError("Assign an age for each child");
        setError("Assign an age for each child");
        return;
      }
    }
    setAgeError("");
    if (
      needsSessionLossWarning({
        mealPlan,
        planChefId,
        selectedChefId,
        answers,
        sessionBaseline,
        forPreferencesChange: true,
      })
    ) {
      const ok = await confirmSessionLoss();
      if (!ok) return;
      clearWizardSession();
    }
    setLoading(true);
    setError("");
    try {
      await api.setProfile({ ...answers, chef_id: "basic_sam" });
      markStepReached(1);
      router.push("/chef");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to save";
      if (msg.toLowerCase().includes("network request failed")) {
        setError(
          `Cannot reach API at ${getApiBaseUrl()} — start meal-agent-api on your PC and use the same Wi-Fi (not tunnel-only).`,
        );
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <WizardShell>
      <Card>
        <CardHeader>
          <H2>Preferences</H2>
          <Muted>Household, meals, diet and budget</Muted>
        </CardHeader>
        <CardBody>
          <Field label="Adult portions">
            <Muted>People 13+</Muted>
            <StepperInput
              value={answers.adults ?? 2}
              onChange={setAdults}
              min={1}
              max={MAX_HOUSEHOLD}
            />
          </Field>
          <Field label="Child portions">
            <Muted>Children 12 and under</Muted>
            <StepperInput
              value={answers.children_under_13 ?? 0}
              onChange={setChildren}
              min={0}
              max={MAX_HOUSEHOLD}
            />
          </Field>
          <Field label="Days">
            <View style={styles.row}>
              {[7, 14].map((d) => (
                <Pressable
                  key={d}
                  style={[styles.chip, answers.days === d && styles.chipActive]}
                  onPress={() => set({ days: d })}
                >
                  <Text style={[styles.chipText, answers.days === d && styles.chipTextActive]}>
                    {d} days
                  </Text>
                </Pressable>
              ))}
            </View>
          </Field>
          {(answers.children_under_13 ?? 0) > 0 && (
            <View style={{ marginTop: 8, gap: 10 }}>
              <Text style={styles.label}>Ages of children</Text>
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
              {!!ageError && <Text style={{ color: "#b45309", fontSize: 13 }}>{ageError}</Text>}
            </View>
          )}
        </CardBody>
      </Card>

      <Card style={{ marginTop: 16 }}>
        <CardHeader>
          <H2>Meals per week</H2>
        </CardHeader>
        <CardBody>
          <Field label="Dinners">
            <StepperInput value={answers.dinner_count} onChange={(v) => set({ dinner_count: v })} max={14} />
          </Field>
          <Field label="Lunches">
            <StepperInput value={answers.lunch_count} onChange={(v) => set({ lunch_count: v })} max={14} />
          </Field>
          <Field label="Snacks">
            <StepperInput value={answers.snack_count} onChange={(v) => set({ snack_count: v })} max={14} />
          </Field>
          <Field label="Lunch mode">
            <View style={styles.row}>
              {(["practical", "original"] as const).map((mode) => (
                <Pressable
                  key={mode}
                  style={[styles.chip, answers.lunch_mode === mode && styles.chipActive]}
                  onPress={() => set({ lunch_mode: mode })}
                >
                  <Text
                    style={[styles.chipText, answers.lunch_mode === mode && styles.chipTextActive]}
                    selectable={false}
                  >
                    {mode === "practical" ? "Practical (leftovers)" : "Original recipes"}
                  </Text>
                </Pressable>
              ))}
            </View>
          </Field>
          <Field label="Meal complexity">
            <View style={styles.row}>
              {(["simple", "moderate", "ambitious"] as const).map((level) => (
                <Pressable
                  key={level}
                  style={[styles.chip, answers.simplicity === level && styles.chipActive]}
                  onPress={() => set({ simplicity: level })}
                  accessibilityLabel={`Meal complexity ${level}`}
                  testID={`discovery-simplicity-${level}`}
                >
                  <Text
                    style={[
                      styles.chipText,
                      answers.simplicity === level && styles.chipTextActive,
                    ]}
                    selectable={false}
                  >
                    {level.charAt(0).toUpperCase() + level.slice(1)}
                  </Text>
                </Pressable>
              ))}
            </View>
          </Field>
        </CardBody>
      </Card>

      <Card style={{ marginTop: 16 }}>
        <CardHeader>
          <H2>Diet & budget</H2>
        </CardHeader>
        <CardBody>
          <Field label="Allergies (comma-separated, optional)">
            <TextInput
              style={styles.input}
              value={answers.allergies}
              onChangeText={(t) => set({ allergies: t })}
              placeholder="e.g. gluten, nuts"
              placeholderTextColor={theme.placeholder}
            />
          </Field>
          <Field label="Weekly budget NZD (optional)">
            <TextInput
              style={styles.input}
              keyboardType="numeric"
              value={answers.budget_nzd > 0 ? String(answers.budget_nzd) : ""}
              onChangeText={(t) => {
                const cleaned = t.replace(/[^0-9.]/g, "");
                if (!cleaned.trim()) {
                  set({ budget_nzd: 0 });
                  return;
                }
                set({ budget_nzd: Number(cleaned) || 0 });
              }}
              placeholder="Leave blank for no hard budget"
              placeholderTextColor={theme.placeholder}
              testID="discovery-budget"
              accessibilityLabel="Weekly budget NZD"
            />
          </Field>
          <Field label="Mandatory items (comma-separated, optional)">
            <TextInput
              style={styles.input}
              value={answers.mandatory_items}
              onChangeText={(t) => set({ mandatory_items: t })}
              placeholder="milk, bread"
              placeholderTextColor={theme.placeholder}
              testID="discovery-mandatory"
              accessibilityLabel="Mandatory items"
            />
          </Field>
          <Field label="Likes (comma-separated)">
            <TextInput
              style={styles.input}
              value={answers.likes}
              onChangeText={(t) => set({ likes: t })}
              placeholder="chicken, pasta, japanese"
              placeholderTextColor={theme.placeholder}
              testID="discovery-likes"
              accessibilityLabel="Likes"
            />
          </Field>
          <Field label="Dislikes (comma-separated)">
            <TextInput
              style={styles.input}
              value={answers.dislikes}
              onChangeText={(t) => set({ dislikes: t })}
              placeholder="lamb, coriander"
              placeholderTextColor={theme.placeholder}
              testID="discovery-dislikes"
              accessibilityLabel="Dislikes"
            />
          </Field>
          <Field label="Other instructions">
            <TextInput
              style={[styles.input, styles.textarea]}
              value={answers.other_instructions}
              onChangeText={(t) => set({ other_instructions: t })}
              placeholder="e.g. oven & microwave only — no stovetop cooking"
              placeholderTextColor={theme.placeholder}
              multiline
              textAlignVertical="top"
            />
          </Field>
        </CardBody>
      </Card>

      {profiles.length > 0 && (
        <Card style={{ marginTop: 16 }}>
          <CardHeader>
            <H2>Saved profiles</H2>
            <Muted>Tap to load</Muted>
          </CardHeader>
          <CardBody>
            {profiles.map((p) => (
              <Pressable
                key={p.id}
                style={styles.profileRow}
                onPress={async () => {
                  const data = await api.loadProfile(p.id);
                  setAnswers({
                    ...answers,
                    ...profileToAnswers(data),
                  });
                }}
              >
                <Text>{p.name}</Text>
              </Pressable>
            ))}
          </CardBody>
        </Card>
      )}

      <ActionBar style={styles.actions}>
        {showForward ? (
          <Button title="Forward →" variant="secondary" onPress={goForward} />
        ) : (
          <View />
        )}
        <Button
          title="Continue to chef →"
          onPress={continueNext}
          loading={loading}
          testID="discovery-continue"
        />
      </ActionBar>
    </WizardShell>
  );
}

const styles = StyleSheet.create({
  field: { marginBottom: 16 },
  label: { fontSize: 14, fontWeight: "600", color: theme.text, marginBottom: 6 },
  stepper: { flexDirection: "row", alignItems: "center", gap: 8 },
  stepBtn: {
    width: 36,
    height: 36,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: theme.border,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.white,
  },
  stepBtnText: { fontSize: 20, color: theme.text },
  stepVal: { fontSize: 16, fontWeight: "700", minWidth: 28, textAlign: "center" },
  row: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.white,
  },
  chipActive: { borderColor: theme.green, backgroundColor: "#ecfdf5" },
  chipText: { fontSize: 13, color: theme.text },
  chipTextActive: { color: theme.green, fontWeight: "600" },
  input: {
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 8,
    padding: 10,
    fontSize: 15,
    color: theme.text,
    backgroundColor: theme.white,
  },
  textarea: {
    minHeight: 80,
  },
  profileRow: { paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: theme.border },
  actions: { marginTop: 24, flexDirection: "row", justifyContent: "space-between", gap: 12 },
});
