import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Platform } from "react-native";
import { useRouter, useSegments } from "expo-router";
import {
  DEFAULT_ANSWERS,
  profileToAnswers,
  stepIndexFromPhase,
  type AppState,
  type CartResult,
  type ChefPersona,
  type DiscoveryAnswers,
  type Meal,
  type MealPlan,
  type ResolvedGroceryList,
} from "@meal-agent/app-core";
import { api } from "@/lib/api";

type Progress = { done: number; total: number; ingredient?: string; phase?: string; message?: string };

interface AppContextValue {
  answers: DiscoveryAnswers;
  setAnswers: React.Dispatch<React.SetStateAction<DiscoveryAnswers>>;
  appState: AppState | null;
  setAppState: React.Dispatch<React.SetStateAction<AppState | null>>;
  mealPlan: MealPlan | null;
  setMealPlan: React.Dispatch<React.SetStateAction<MealPlan | null>>;
  meals: Meal[];
  setMeals: React.Dispatch<React.SetStateAction<Meal[]>>;
  shopList: ResolvedGroceryList | null;
  setShopList: React.Dispatch<React.SetStateAction<ResolvedGroceryList | null>>;
  cartResult: CartResult | null;
  setCartResult: React.Dispatch<React.SetStateAction<CartResult | null>>;
  chefs: ChefPersona[];
  premiumUnlocked: boolean;
  selectedChefId: string;
  setSelectedChefId: React.Dispatch<React.SetStateAction<string>>;
  planChefId: string | null;
  setPlanChefId: React.Dispatch<React.SetStateAction<string | null>>;
  profiles: { id: string; name: string }[];
  loading: boolean;
  setLoading: React.Dispatch<React.SetStateAction<boolean>>;
  error: string;
  setError: React.Dispatch<React.SetStateAction<string>>;
  planProgress: { done: number; total: number; message: string };
  setPlanProgress: React.Dispatch<React.SetStateAction<{ done: number; total: number; message: string }>>;
  resolveProgress: Progress;
  setResolveProgress: React.Dispatch<React.SetStateAction<Progress>>;
  cartProgress: Progress & { log: { ingredient: string; status: string; message: string }[] };
  setCartProgress: React.Dispatch<
    React.SetStateAction<Progress & { log: { ingredient: string; status: string; message: string }[] }>
  >;
  woolworthsKey: number;
  refreshWoolworths: () => void;
  refreshProfiles: () => void;
  loadChefs: () => void;
  initSession: () => Promise<void>;
  furthestStep: number;
  markStepReached: (step: number) => void;
  sessionBaseline: DiscoveryAnswers | null;
  setSessionBaseline: React.Dispatch<React.SetStateAction<DiscoveryAnswers | null>>;
  clearWizardSession: () => void;
  resetDownstreamFromPlan: () => void;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [answers, setAnswers] = useState<DiscoveryAnswers>(DEFAULT_ANSWERS);
  const [appState, setAppState] = useState<AppState | null>(null);
  const [mealPlan, setMealPlan] = useState<MealPlan | null>(null);
  const [meals, setMeals] = useState<Meal[]>([]);
  const [shopList, setShopList] = useState<ResolvedGroceryList | null>(null);
  const [cartResult, setCartResult] = useState<CartResult | null>(null);
  const [chefs, setChefs] = useState<ChefPersona[]>([]);
  const [premiumUnlocked, setPremiumUnlocked] = useState(false);
  const [selectedChefId, setSelectedChefId] = useState("basic_sam");
  const [planChefId, setPlanChefId] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [planProgress, setPlanProgress] = useState({ done: 0, total: 5, message: "" });
  const [resolveProgress, setResolveProgress] = useState<Progress>({
    done: 0,
    total: 0,
    ingredient: "",
    phase: "",
    message: "",
  });
  const [cartProgress, setCartProgress] = useState<
    Progress & { log: { ingredient: string; status: string; message: string }[] }
  >({ done: 0, total: 0, ingredient: "", phase: "", message: "", log: [] });
  const [woolworthsKey, setWoolworthsKey] = useState(0);
  const [ready, setReady] = useState(false);
  const [furthestStep, setFurthestStep] = useState(0);
  const [sessionBaseline, setSessionBaseline] = useState<DiscoveryAnswers | null>(null);

  const refreshWoolworths = useCallback(() => setWoolworthsKey((k) => k + 1), []);

  const markStepReached = useCallback((step: number) => {
    setFurthestStep((prev) => Math.max(prev, step));
  }, []);

  const clearWizardSession = useCallback(() => {
    setMealPlan(null);
    setMeals([]);
    setShopList(null);
    setCartResult(null);
    setPlanChefId(null);
    setSessionBaseline(null);
    setFurthestStep(1);
  }, []);

  const resetDownstreamFromPlan = useCallback(() => {
    setMeals([]);
    setShopList(null);
    setCartResult(null);
    setFurthestStep(2);
  }, []);

  const refreshProfiles = useCallback(() => {
    api
      .listProfiles()
      .then((r) => setProfiles(r.profiles))
      .catch(() => setProfiles([]));
  }, []);

  const loadChefs = useCallback(() => {
    api
      .listChefs()
      .then((r) => {
        setChefs(r.chefs);
        setPremiumUnlocked(r.premium_unlocked);
      })
      .catch(() => {});
    api
      .getAuthMe()
      .then((me) => {
        if (me.premium_unlocked) setPremiumUnlocked(true);
      })
      .catch(() => {});
  }, []);

  const initSession = useCallback(async () => {
    try {
      await api.startSession();
      const state = await api.getState();
      setAppState(state);
      if (state.meal_plan) setMealPlan(state.meal_plan);
      if (state.resolved_list) setShopList(state.resolved_list as ResolvedGroceryList);
      const profile = state.profile as { chef_id?: string; lunch_mode?: string } | null;
      if (profile?.chef_id) {
        setSelectedChefId(profile.chef_id);
        setAnswers((prev) => ({ ...prev, chef_id: profile.chef_id! }));
      }
      if (profile?.lunch_mode) {
        setAnswers((prev) => ({
          ...prev,
          lunch_mode: profile.lunch_mode === "practical" ? "practical" : "original",
        }));
      }
      if (state.meal_plan) {
        const chefId = profile?.chef_id ?? "basic_sam";
        setPlanChefId(chefId);
        const baseline = state.profile as DiscoveryAnswers | null;
        if (baseline) {
          setSessionBaseline({ ...profileToAnswers(baseline as Record<string, unknown>), chef_id: chefId });
        }
        const reached = stepIndexFromPhase(state.phase, !!state.profile);
        setFurthestStep(reached);
        if (state.phase === "plan_approval") router.replace("/plan");
        else if (state.phase === "product_resolution") router.replace("/recipes");
        else if (state.phase === "budget_reconciliation") router.replace("/shop");
        else if (state.phase === "cart" || state.phase === "complete") router.replace("/cart");
      } else if (state.profile) {
        setFurthestStep(1);
        router.replace("/chef");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start session");
    } finally {
      setReady(true);
    }
  }, [router]);

  useEffect(() => {
    refreshProfiles();
    loadChefs();
    initSession();
  }, [refreshProfiles, loadChefs, initSession]);

  const value = useMemo(
    () => ({
      answers,
      setAnswers,
      appState,
      setAppState,
      mealPlan,
      setMealPlan,
      meals,
      setMeals,
      shopList,
      setShopList,
      cartResult,
      setCartResult,
      chefs,
      premiumUnlocked,
      selectedChefId,
      setSelectedChefId,
      planChefId,
      setPlanChefId,
      profiles,
      loading,
      setLoading,
      error,
      setError,
      planProgress,
      setPlanProgress,
      resolveProgress,
      setResolveProgress,
      cartProgress,
      setCartProgress,
      woolworthsKey,
      refreshWoolworths,
      refreshProfiles,
      loadChefs,
      initSession,
      ready,
      furthestStep,
      markStepReached,
      sessionBaseline,
      setSessionBaseline,
      clearWizardSession,
      resetDownstreamFromPlan,
    }),
    [
      answers,
      appState,
      mealPlan,
      meals,
      shopList,
      cartResult,
      chefs,
      premiumUnlocked,
      selectedChefId,
      planChefId,
      profiles,
      loading,
      error,
      planProgress,
      resolveProgress,
      cartProgress,
      woolworthsKey,
      refreshWoolworths,
      refreshProfiles,
      loadChefs,
      initSession,
      ready,
      furthestStep,
      markStepReached,
      sessionBaseline,
      clearWizardSession,
      resetDownstreamFromPlan,
    ],
  );

  if (!ready) return null;

  return <AppContext.Provider value={value as AppContextValue}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}

export { profileToAnswers, DEFAULT_ANSWERS };
