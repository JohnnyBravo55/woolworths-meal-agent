import { useEffect, useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Button } from "@/components/ui/Button";
import {
  FEEDBACK_SUBMITTED_KEY,
  IF_NEVER_PUBLIC_OPTIONS,
  LIKELIHOOD_OPTIONS,
  MEAL_PLAN_USEFUL_OPTIONS,
  MOST_VALUABLE_OPTIONS,
  type IfNeverPublic,
  type Likelihood,
  type MealPlanUseful,
  type MostValuable,
} from "@/constants/feedback";
import { theme } from "@/constants/theme";
import { api } from "@/lib/api";
import { sessionStore } from "@/lib/session-store";

type Props = {
  visible: boolean;
  onClose: () => void;
  onSubmitted: () => void;
};

type ChipGroupProps<T extends string> = {
  label: string;
  options: readonly T[];
  selected?: T;
  onSelect: (option: T) => void;
};

function ChipGroup<T extends string>({
  label,
  options,
  selected,
  onSelect,
}: ChipGroupProps<T>) {
  return (
    <View style={styles.group}>
      <Text style={styles.question}>{label}</Text>
      <View style={styles.chips}>
        {options.map((option) => {
          const isSelected = selected === option;
          return (
            <Pressable
              key={option}
              accessibilityRole="radio"
              accessibilityState={{ checked: isSelected }}
              onPress={() => onSelect(option)}
              style={({ pressed }) => [
                styles.chip,
                isSelected && styles.chipSelected,
                pressed && styles.chipPressed,
              ]}
            >
              <Text style={[styles.chipText, isSelected && styles.chipTextSelected]}>
                {option}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

export function FeedbackModal({ visible, onClose, onSubmitted }: Props) {
  const [mealPlanUseful, setMealPlanUseful] = useState<MealPlanUseful>();
  const [mostValuable, setMostValuable] = useState<MostValuable>();
  const [useAgain, setUseAgain] = useState<Likelihood>();
  const [ifNeverPublic, setIfNeverPublic] = useState<IfNeverPublic>();
  const [premiumSubscribe, setPremiumSubscribe] = useState<Likelihood>();
  const [improve, setImprove] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    if (!visible) return;
    let wasSubmitted = false;
    try {
      if (typeof localStorage !== "undefined") {
        wasSubmitted = localStorage.getItem(FEEDBACK_SUBMITTED_KEY) === "1";
      }
    } catch {
      // Storage can be unavailable; keep the questionnaire usable.
    }
    setMealPlanUseful(undefined);
    setMostValuable(undefined);
    setUseAgain(undefined);
    setIfNeverPublic(undefined);
    setPremiumSubscribe(undefined);
    setImprove("");
    setLoading(false);
    setError(undefined);
    setSubmitted(wasSubmitted);
  }, [visible]);

  const canSubmit =
    mealPlanUseful !== undefined &&
    mostValuable !== undefined &&
    useAgain !== undefined &&
    ifNeverPublic !== undefined &&
    premiumSubscribe !== undefined;

  async function handleSubmit() {
    if (!canSubmit || loading) return;
    setLoading(true);
    setError(undefined);

    try {
      const sessionId = await sessionStore.getSessionId();
      await api.submitFeedback({
        meal_plan_useful: mealPlanUseful,
        most_valuable: mostValuable,
        use_again: useAgain,
        if_never_public: ifNeverPublic,
        premium_subscribe: premiumSubscribe,
        improve: improve.trim(),
        session_id: sessionId ?? undefined,
      });
      setSubmitted(true);
      try {
        if (typeof localStorage !== "undefined") {
          localStorage.setItem(FEEDBACK_SUBMITTED_KEY, "1");
        }
      } catch {
        // Submission succeeded, so storage failure must not invite a retry.
      }
    } catch (submitError) {
      setError(
        submitError instanceof Error
          ? submitError.message
          : "We couldn't submit your feedback. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      statusBarTranslucent
      onRequestClose={() => {
        if (!loading) onClose();
      }}
    >
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <ScrollView
            contentContainerStyle={styles.content}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
            {submitted ? (
              <View style={styles.thanks}>
                <Text style={styles.title}>Thank you!</Text>
                <Text style={styles.subtitle}>Your feedback will help us improve Meal Agent.</Text>
                <Button title="Done" onPress={onSubmitted} />
              </View>
            ) : (
              <>
                <Text style={styles.title}>Quick feedback</Text>
                <Text style={styles.subtitle}>
                  Helps us improve Meal Agent — about 30 seconds
                </Text>

                <ChipGroup
                  label="1. How useful was your meal plan?"
                  options={MEAL_PLAN_USEFUL_OPTIONS}
                  selected={mealPlanUseful}
                  onSelect={setMealPlanUseful}
                />
                <ChipGroup
                  label="2. Which part was most valuable?"
                  options={MOST_VALUABLE_OPTIONS}
                  selected={mostValuable}
                  onSelect={setMostValuable}
                />
                <ChipGroup
                  label="3. How likely are you to use this app again?"
                  options={LIKELIHOOD_OPTIONS}
                  selected={useAgain}
                  onSelect={setUseAgain}
                />
                <ChipGroup
                  label="4. If Meal Agent never became publicly available, how would you feel?"
                  options={IF_NEVER_PUBLIC_OPTIONS}
                  selected={ifNeverPublic}
                  onSelect={setIfNeverPublic}
                />
                <ChipGroup
                  label="5. If Premium included specialised chefs and extra features for NZ$9.99/month, how likely are you to subscribe?"
                  options={LIKELIHOOD_OPTIONS}
                  selected={premiumSubscribe}
                  onSelect={setPremiumSubscribe}
                />

                <View style={styles.group}>
                  <Text style={styles.question}>Anything we could improve? (optional)</Text>
                  <TextInput
                    value={improve}
                    onChangeText={setImprove}
                    editable={!loading}
                    multiline
                    maxLength={1000}
                    placeholder="Share any ideas or issues"
                    placeholderTextColor={theme.placeholder}
                    style={styles.input}
                    textAlignVertical="top"
                  />
                </View>

                {error ? (
                  <Text accessibilityRole="alert" style={styles.error}>
                    {error}
                  </Text>
                ) : null}

                <View style={styles.actions}>
                  <Button
                    title="Submit"
                    onPress={handleSubmit}
                    disabled={!canSubmit}
                    loading={loading}
                  />
                  <Button
                    title="Not now"
                    onPress={onClose}
                    disabled={loading}
                    variant="ghost"
                  />
                </View>
              </>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.55)",
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  card: {
    width: "100%",
    maxWidth: 440,
    maxHeight: "90%",
    backgroundColor: theme.white,
    borderRadius: 16,
    overflow: "hidden",
  },
  content: { padding: 20 },
  title: {
    color: theme.text,
    fontSize: 21,
    fontWeight: "800",
    textAlign: "center",
  },
  subtitle: {
    color: theme.textMuted,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 6,
    marginBottom: 20,
    textAlign: "center",
  },
  group: { marginBottom: 18 },
  question: {
    color: theme.text,
    fontSize: 14,
    fontWeight: "700",
    lineHeight: 20,
    marginBottom: 9,
  },
  chips: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  chip: {
    borderColor: theme.border,
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  chipSelected: {
    backgroundColor: theme.green,
    borderColor: theme.green,
  },
  chipPressed: { opacity: 0.75 },
  chipText: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "600",
  },
  chipTextSelected: { color: theme.white },
  input: {
    minHeight: 92,
    borderColor: theme.border,
    borderRadius: 10,
    borderWidth: 1,
    color: theme.text,
    fontSize: 14,
    lineHeight: 20,
    padding: 12,
  },
  error: {
    color: theme.red,
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 12,
    textAlign: "center",
  },
  actions: { gap: 4 },
  thanks: {
    alignItems: "stretch",
    paddingVertical: 12,
  },
});
