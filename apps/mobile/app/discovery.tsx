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
import { profileToAnswers, type DiscoveryAnswers } from "@meal-agent/app-core";

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
  const set = (patch: Partial<DiscoveryAnswers>) => setAnswers({ ...answers, ...patch });

  const continueNext = async () => {
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
          <Field label="People">
            <StepperInput
              value={answers.household_size}
              onChange={(v) => set({ household_size: v })}
              min={1}
              max={8}
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
                  >
                    {mode === "practical" ? "Practical (leftovers)" : "Original recipes"}
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
          <Field label="Already in pantry (comma-separated)">
            <TextInput
              style={styles.input}
              value={answers.pantry_items}
              onChangeText={(t) => set({ pantry_items: t })}
              placeholder="olive oil, rice, soy sauce"
              placeholderTextColor={theme.placeholder}
              testID="discovery-pantry"
              accessibilityLabel="Already in pantry"
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
