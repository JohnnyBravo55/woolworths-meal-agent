import { useRouter } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { Image, Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import {
  canReuseMealPlan,
  needsSessionLossWarning,
  type ChefPersona,
  type MealPlan,
} from "@meal-agent/app-core";
import { WizardShell } from "@/components/WizardShell";
import { useApp } from "@/context/AppProvider";
import { Button } from "@/components/ui/Button";
import { ActionBar } from "@/components/ActionBar";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ParallelLoadingModal } from "@/components/ParallelLoadingModal";
import { theme } from "@/constants/theme";
import { api, getApiBaseUrl } from "@/lib/api";
import { chefAvatarSource } from "@/lib/chef-avatars";
import { isHostedApiUrl } from "@/lib/config";
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
  const selected = chefs.find((c) => c.id === selectedChefId);
  const apiBase = getApiBaseUrl();
  const { width } = useWindowDimensions();
  const premiumColumns = width >= 640 ? 3 : 2;

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
      let streamError = "";
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
        if (event === "error") {
          streamError = String(data.message || "Meal plan failed");
          setError(streamError);
        }
      });
      if (!completed) {
        // Plan may already be saved on the API even if the SSE "complete" event was dropped.
        try {
          const recovered = await api.getPlan();
          const state = await api.getState();
          if (recovered.meal_plan) {
            completed = true;
            setMealPlan(recovered.meal_plan);
            setPlanChefId(selectedChefId);
            setSessionBaseline({ ...answers, chef_id: selectedChefId });
            setShopList(null);
            setAppState(state as never);
            setPlanReady(true);
            markStepReached(2);
            setGenerating(false);
            setLoading(false);
            if (!woolworthsOpenRef.current) goToPlan();
          }
        } catch {
          /* no plan on server yet */
        }
      }
      if (!completed) {
        if (!streamError) {
          setError(
            isHostedApiUrl(getApiBaseUrl())
              ? "Meal plan stream ended early — the hosted API may have dropped the connection. Wait a few seconds and try again."
              : "Meal plan ended early — check meal-agent-api is running on port 8000.",
          );
        }
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
            {isHostedApiUrl(apiBase)
              ? `AI meal plans via hosted API (${openAiModel}).`
              : `AI meal plans via your PC API (${openAiModel}) — same OpenAI key as desktop.`}
          </Text>
        </View>
      )}
      {openAiReady === false && (
        <View style={styles.aiBannerWarn}>
          <Text style={styles.aiBannerWarnText}>
            {isHostedApiUrl(apiBase)
              ? "OpenAI is not configured on the hosted API. Set OPENAI_API_KEY on Render and redeploy."
              : "OpenAI not configured on your PC. Add OPENAI_API_KEY to woolworths-meal-agent\\.env and restart meal-agent-api — the phone uses that same server."}
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
          <View style={styles.tierHeader}>
            <Text style={styles.tierLabel}>Basic</Text>
            <Badge>Free</Badge>
          </View>
        </CardHeader>
        <CardBody style={styles.basicBody}>
          {basic.map((chef) => (
            <ChefAvatar
              key={chef.id}
              chef={chef}
              selected={selectedChefId === chef.id}
              locked={false}
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
          <View style={styles.tierHeader}>
            <Text style={styles.tierLabelPremium}>Premium</Text>
            <Badge tone="mandatory">Subscriber</Badge>
          </View>
        </CardHeader>
        <CardBody style={styles.premiumBody}>
          <View style={styles.premiumGrid}>
            {premium.map((chef) => (
              <View
                key={chef.id}
                style={[styles.premiumCell, { width: `${100 / premiumColumns}%` }]}
              >
                <ChefAvatar
                  chef={chef}
                  selected={selectedChefId === chef.id}
                  locked={!premiumUnlocked}
                  onPress={() => {
                    if (!premiumUnlocked) return;
                    setSelectedChefId(chef.id);
                    setAnswers((a) => ({ ...a, chef_id: chef.id }));
                  }}
                />
              </View>
            ))}
          </View>
        </CardBody>
      </Card>

      {selected ? (
        <Text style={styles.selectedLine}>
          Selected: <Text style={styles.selectedName}>{selected.name}</Text> — {selected.title}
        </Text>
      ) : null}

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
          testID="chef-generate"
        />
      </ActionBar>
    </WizardShell>
  );
}

function ChefAvatar({
  chef,
  selected,
  locked,
  onPress,
}: {
  chef: ChefPersona;
  selected: boolean;
  locked: boolean;
  onPress: () => void;
}) {
  const isPremium = chef.tier === "premium";
  const source = chefAvatarSource(chef.id);

  return (
    <Pressable
      style={[styles.avatarPressable, locked && styles.chefLocked]}
      onPress={onPress}
      disabled={locked}
    >
      <View
        style={[
          styles.avatarRing,
          isPremium && styles.avatarRingPremium,
          selected && styles.avatarRingSelected,
        ]}
      >
        {source ? (
          <Image source={source} style={styles.avatar} />
        ) : (
          <View
            style={[
              styles.avatar,
              styles.avatarFallback,
              { backgroundColor: chef.avatar_from || theme.green },
            ]}
          >
            <Text style={styles.initials}>{chef.avatar_initials}</Text>
          </View>
        )}
        {locked ? (
          <View style={styles.lockOverlay}>
            <Text style={styles.lockIcon}>🔒</Text>
          </View>
        ) : null}
      </View>
      <Text style={styles.chefName}>{chef.name}</Text>
      <Text style={styles.chefTitle}>{chef.title}</Text>
      <Text style={styles.chefTagline}>{chef.tagline}</Text>
      <Text style={styles.chefRegion}>{chef.region}</Text>
    </Pressable>
  );
}

const AVATAR_SIZE = 112;

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
  tierHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  tierLabel: {
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 0.6,
    textTransform: "uppercase",
    color: "#64748b",
  },
  tierLabelPremium: {
    fontSize: 13,
    fontWeight: "700",
    letterSpacing: 0.6,
    textTransform: "uppercase",
    color: "#b45309",
  },
  basicBody: {
    alignItems: "center",
    paddingVertical: 24,
  },
  premiumBody: {
    paddingVertical: 16,
  },
  premiumGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
  },
  premiumCell: {
    paddingHorizontal: 8,
    paddingVertical: 12,
    alignItems: "center",
  },
  avatarPressable: {
    alignItems: "center",
    maxWidth: 176,
  },
  chefLocked: { opacity: 0.6 },
  avatarRing: {
    borderRadius: (AVATAR_SIZE + 8) / 2,
    padding: 4,
  },
  avatarRingPremium: {
    backgroundColor: "#fbbf24",
    shadowColor: "#d97706",
    shadowOpacity: 0.35,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 3,
  },
  avatarRingSelected: {
    borderWidth: 4,
    borderColor: theme.green,
    padding: 2,
  },
  avatar: {
    width: AVATAR_SIZE,
    height: AVATAR_SIZE,
    borderRadius: AVATAR_SIZE / 2,
  },
  avatarFallback: {
    alignItems: "center",
    justifyContent: "center",
  },
  lockOverlay: {
    ...StyleSheet.absoluteFillObject,
    borderRadius: (AVATAR_SIZE + 8) / 2,
    backgroundColor: "rgba(0,0,0,0.4)",
    alignItems: "center",
    justifyContent: "center",
  },
  lockIcon: { fontSize: 28 },
  initials: { color: theme.white, fontWeight: "700", fontSize: 28 },
  chefName: {
    marginTop: 12,
    fontWeight: "700",
    fontSize: 16,
    color: theme.text,
    textAlign: "center",
  },
  chefTitle: {
    color: theme.green,
    fontSize: 13,
    fontWeight: "600",
    textAlign: "center",
  },
  chefTagline: {
    marginTop: 4,
    fontSize: 12,
    color: theme.textMuted,
    textAlign: "center",
    maxWidth: 176,
  },
  chefRegion: {
    marginTop: 4,
    fontSize: 12,
    color: "#94a3b8",
    textAlign: "center",
  },
  selectedLine: {
    marginTop: 16,
    textAlign: "center",
    fontSize: 14,
    color: "#475569",
  },
  selectedName: { fontWeight: "700", color: theme.text },
  actions: {
    marginTop: 24,
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    gap: 12,
  },
});
