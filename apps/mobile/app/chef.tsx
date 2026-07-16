import { useRouter } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";
import {
  canReuseMealPlan,
  chefAvatarUrl,
  needsSessionLossWarning,
  type ChefPersona,
  type MealPlan,
} from "@meal-agent/app-core";
import { WizardShell } from "@/components/WizardShell";
import { useApp } from "@/context/AppProvider";
import { Button } from "@/components/ui/Button";
import { ActionBar } from "@/components/ActionBar";
import { Card, CardBody, CardHeader, H2, Muted } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ParallelLoadingModal } from "@/components/ParallelLoadingModal";
import { theme } from "@/constants/theme";
import { api, getApiBaseUrl } from "@/lib/api";
import { confirmSessionLoss } from "@/lib/confirm-session-loss";
import { needsMobileWoolworthsSignIn } from "@/lib/woolworths-mobile";
import { useWizardNav } from "@/lib/useWizardNav";

export default function ChefScreen() {
  const router = useRouter();
  const {
    answers,
    chefs,
    premiumUnlocked,
    selectedChefId,
    setSelectedChefId,
    setAnswers,
    mealPlan,
    planChefId,
    loading,
    setLoading,
    setError,
    setMealPlan,
    setShopList,
    setAppState,
    planProgress,
    setPlanProgress,
    setPlanChefId,
    refreshWoolworths,
    sessionBaseline,
    setSessionBaseline,
    clearWizardSession,
    markStepReached,
  } = useApp();
  const { showForward, goForward } = useWizardNav();

  const [openAiReady, setOpenAiReady] = useState<boolean | null>(null);
  const [openAiModel, setOpenAiModel] = useState("");
  const [woolworthsOpen, setWoolworthsOpen] = useState(false);
  const [planReady, setPlanReady] = useState(false);
  const [generating, setGenerating] = useState(false);
  const woolworthsOpenRef = useRef(false);

  useEffect(() => {
    api
      .getHealth()
      .then((h) => {
        setOpenAiReady(h.openai_configured);
        setOpenAiModel(h.openai_model);
      })
      .catch(() => setOpenAiReady(null));
  }, []);

  const basic = chefs.filter((c) => c.tier === "basic");
  const premium = chefs.filter((c) => c.tier === "premium");
  const apiBase = getApiBaseUrl();

  const goToPlan = () => router.push("/plan");

  const finishWoolworths = () => {
    woolworthsOpenRef.current = false;
    setWoolworthsOpen(false);
    if (planReady) goToPlan();
  };

  const runGenerate = async () => {
    if (canReuseMealPlan({ mealPlan, planChefId, selectedChefId, answers, sessionBaseline })) {
      markStepReached(2);
      goToPlan();
      return;
    }
    if (
      needsSessionLossWarning({
        mealPlan,
        planChefId,
        selectedChefId,
        answers,
        sessionBaseline,
        forChefChange: true,
      })
    ) {
      const ok = await confirmSessionLoss();
      if (!ok) return;
      clearWizardSession();
    }
    setGenerating(true);
    setLoading(true);
    setPlanReady(false);
    setError("");
    setPlanProgress({ done: 0, total: 5, message: "Starting…" });
    const needsWw = await needsMobileWoolworthsSignIn();
    woolworthsOpenRef.current = needsWw;
    setWoolworthsOpen(needsWw);
    try {
      await api.setProfile({ ...answers, chef_id: selectedChefId });
      let completed = false;
      await api.streamSSE("/api/plan/generate", (event, data) => {
        if (event === "status") {
          setPlanProgress({
            done: Number(data.done ?? 0),
            total: Number(data.total ?? 5),
            message: String(data.message ?? ""),
          });
        }
        if (event === "warning") setError(String(data.message));
        if (event === "complete") {
          completed = true;
          setMealPlan(data.meal_plan as MealPlan);
          setPlanChefId(selectedChefId);
          setSessionBaseline({ ...answers, chef_id: selectedChefId });
          setShopList(null);
          setAppState(data.state as never);
          setPlanReady(true);
          markStepReached(2);
          setGenerating(false);
          setLoading(false);
          if (!woolworthsOpenRef.current) {
            goToPlan();
          }
        }
        if (event === "error") setError(String(data.message));
      });
      if (!completed) {
        setError("Meal plan ended early — check your PC API is running.");
        woolworthsOpenRef.current = false;
        setWoolworthsOpen(false);
        setGenerating(false);
        setLoading(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generate failed");
      woolworthsOpenRef.current = false;
      setWoolworthsOpen(false);
      setGenerating(false);
      setLoading(false);
    }
  };

  return (
    <WizardShell>
      <ParallelLoadingModal
        visible={generating || woolworthsOpen}
        title="Creating your meal plan"
        message={planProgress.message || "Starting…"}
        done={planProgress.done}
        total={planProgress.total}
        showWoolworths={woolworthsOpen}
        planReady={planReady && woolworthsOpen}
        woolworthsTitle="Sign in while your plan is created"
        woolworthsHint="Tap Sign in page if you don't see a login form. When done, tap I've signed in."
        onWoolworthsLinked={() => {
          refreshWoolworths();
          finishWoolworths();
        }}
        onContinueWithoutWoolworths={finishWoolworths}
        onWoolworthsError={setError}
      />
      {openAiReady === true && (
        <View style={styles.aiBannerOk}>
          <Text style={styles.aiBannerOkText}>
            AI meal plans via your PC API ({openAiModel}) — same OpenAI key as desktop.
          </Text>
        </View>
      )}
      {openAiReady === false && (
        <View style={styles.aiBannerWarn}>
          <Text style={styles.aiBannerWarnText}>
            OpenAI not configured on your PC. Add OPENAI_API_KEY to woolworths-meal-agent\.env and
            restart meal-agent-api — the phone uses that same server.
          </Text>
        </View>
      )}

      {!premiumUnlocked && (
        <View style={styles.banner}>
          <Text style={styles.bannerText}>
            Premium chefs need a subscription. Continue with Sam (Basic) or sign in as a subscriber.
          </Text>
        </View>
      )}

      <Card>
        <CardHeader>
          <H2>Basic</H2>
          <Badge>Free</Badge>
        </CardHeader>
        <CardBody>
          {basic.map((chef) => (
            <ChefRow
              key={chef.id}
              chef={chef}
              selected={selectedChefId === chef.id}
              locked={false}
              apiBase={apiBase}
              onPress={() => {
                setSelectedChefId(chef.id);
                setAnswers((a) => ({ ...a, chef_id: chef.id }));
              }}
            />
          ))}
        </CardBody>
      </Card>

      <Card style={{ marginTop: 16 }}>
        <CardHeader>
          <H2>Premium</H2>
          <Badge tone="mandatory">Subscriber</Badge>
        </CardHeader>
        <CardBody>
          {premium.map((chef) => (
            <ChefRow
              key={chef.id}
              chef={chef}
              selected={selectedChefId === chef.id}
              locked={!premiumUnlocked}
              apiBase={apiBase}
              onPress={() => {
                if (!premiumUnlocked) return;
                setSelectedChefId(chef.id);
                setAnswers((a) => ({ ...a, chef_id: chef.id }));
              }}
            />
          ))}
        </CardBody>
      </Card>

      <ActionBar style={styles.actions}>
        <Button title="← Back" variant="secondary" onPress={() => router.push("/discovery")} disabled={generating || woolworthsOpen} />
        {showForward ? (
          <Button title="Forward →" variant="secondary" onPress={goForward} disabled={generating || woolworthsOpen} />
        ) : null}
        <Button
          title={
            generating
              ? "Generating…"
              : canReuseMealPlan({ mealPlan, planChefId, selectedChefId, answers, sessionBaseline })
                ? "Continue to meal plan →"
                : "Generate meal plan →"
          }
          onPress={runGenerate}
          loading={generating}
          disabled={!selectedChefId || woolworthsOpen}
        />
      </ActionBar>
    </WizardShell>
  );
}

function ChefRow({
  chef,
  selected,
  locked,
  apiBase,
  onPress,
}: {
  chef: ChefPersona;
  selected: boolean;
  locked: boolean;
  apiBase: string;
  onPress: () => void;
}) {
  const uri = chefAvatarUrl(apiBase, chef.avatar_image);
  return (
    <Pressable
      style={[styles.chefRow, selected && styles.chefSelected, locked && styles.chefLocked]}
      onPress={onPress}
      disabled={locked}
    >
      {uri ? (
        <Image source={{ uri }} style={styles.avatar} />
      ) : (
        <View style={[styles.avatar, styles.avatarFallback]}>
          <Text style={styles.initials}>{chef.avatar_initials}</Text>
        </View>
      )}
      <View style={{ flex: 1 }}>
        <Text style={styles.chefName}>{chef.name}</Text>
        <Text style={styles.chefTitle}>{chef.title}</Text>
        <Muted>{chef.tagline}</Muted>
      </View>
      {locked && <Text>🔒</Text>}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  aiBannerOk: {
    backgroundColor: "#ecfdf5",
    borderWidth: 1,
    borderColor: "#a7f3d0",
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  aiBannerOkText: { fontSize: 13, color: "#065f46" },
  aiBannerWarn: {
    backgroundColor: "#fffbeb",
    borderWidth: 1,
    borderColor: "#fde68a",
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  aiBannerWarnText: { fontSize: 13, color: "#92400e" },
  banner: {
    backgroundColor: "#fffbeb",
    borderWidth: 1,
    borderColor: "#fde68a",
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  bannerText: { fontSize: 13, color: "#92400e" },
  chefRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    padding: 12,
    borderRadius: 10,
    marginBottom: 8,
    borderWidth: 2,
    borderColor: "transparent",
  },
  chefSelected: { borderColor: theme.green, backgroundColor: "#ecfdf5" },
  chefLocked: { opacity: 0.6 },
  avatar: { width: 56, height: 56, borderRadius: 28 },
  avatarFallback: { backgroundColor: theme.green, alignItems: "center", justifyContent: "center" },
  initials: { color: theme.white, fontWeight: "700", fontSize: 18 },
  chefName: { fontWeight: "700", fontSize: 16, color: theme.text },
  chefTitle: { color: theme.green, fontSize: 13, fontWeight: "600" },
  actions: {
    marginTop: 24,
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    gap: 12,
  },
});
