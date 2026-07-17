import { useCallback, useEffect, useState } from "react";
import {
  canReuseMealPlan,
  needsSessionLossWarning,
  SESSION_LOSS_WARNING,
  stepIndexFromPhase,
} from "@meal-agent/app-core";
import {
  approvePlan,
  approveShop,
  downloadRecipes,
  getAuthMe,
  getState,
  listChefs,
  listProfiles,
  loadProfile,
  regeneratePlan,
  saveProfile,
  setProfile,
  startSession,
  streamSSE,
  swapMeal,
} from "./api/client";
import { AuthModal } from "./components/AuthModal";
import { SaveProfileModal } from "./components/SaveProfileModal";
import { MobileStepper, Stepper } from "./components/Stepper";
import { Button } from "./components/ui/Button";
import { WizardNav } from "./components/WizardNav";
import { ChefSelectStep } from "./steps/ChefSelectStep";
import { DiscoveryStep } from "./steps/DiscoveryStep";
import { MealPlanStep } from "./steps/MealPlanStep";
import { RecipesStep } from "./steps/RecipesStep";
import { ShopListStep } from "./steps/ShopListStep";
import type {
  AppState,
  ChefPersona,
  DiscoveryAnswers,
  Meal,
  MealPlan,
  ResolvedGroceryList,
} from "./types";
import { DEFAULT_ANSWERS } from "./types";

function profileToAnswers(data: Record<string, unknown>): DiscoveryAnswers {
  return {
    household_size: Number(data.household_size ?? 2),
    days: Number(data.days ?? 7),
    dinner_count: Number(data.dinner_count ?? 5),
    lunch_count: Number(data.lunch_count ?? 0),
    snack_count: Number(data.snack_count ?? 0),
    allergies: String(data.allergies ?? ""),
    mandatory_items: String(data.mandatory_items ?? ""),
    pantry_items: String(data.pantry_items ?? ""),
    likes: String(data.likes ?? ""),
    dislikes: String(data.dislikes ?? ""),
    other_instructions: String(data.other_instructions ?? ""),
    budget_nzd: Number(data.budget_nzd ?? 0) || 0,
    store_name: String(data.store_name ?? ""),
    simplicity: String(data.simplicity ?? "simple"),
    brand_preference: String(data.brand_preference ?? "mixed"),
    chef_id: String(data.chef_id ?? "basic_sam"),
    lunch_mode: (data.lunch_mode === "practical" ? "practical" : "original") as "practical" | "original",
  };
}

export default function App() {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<DiscoveryAnswers>(DEFAULT_ANSWERS);
  const [appState, setAppState] = useState<AppState | null>(null);
  const [mealPlan, setMealPlan] = useState<MealPlan | null>(null);
  const [meals, setMeals] = useState<Meal[]>([]);
  const [shopList, setShopList] = useState<ResolvedGroceryList | null>(null);
  const [profiles, setProfiles] = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [planProgress, setPlanProgress] = useState({
    done: 0,
    total: 5,
    message: "",
  });
  const [error, setError] = useState("");
  const [authOpen, setAuthOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [saveProfileOpen, setSaveProfileOpen] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [resolveProgress, setResolveProgress] = useState({
    done: 0,
    total: 0,
    ingredient: "",
    phase: "",
    message: "",
  });
  const [chefs, setChefs] = useState<ChefPersona[]>([]);
  const [premiumUnlocked, setPremiumUnlocked] = useState(false);
  const [selectedChefId, setSelectedChefId] = useState("basic_sam");
  const [planChefId, setPlanChefId] = useState<string | null>(null);
  const [furthestStep, setFurthestStep] = useState(0);
  const [sessionBaseline, setSessionBaseline] = useState<DiscoveryAnswers | null>(null);

  const markStepReached = useCallback((next: number) => {
    setFurthestStep((prev) => Math.max(prev, next));
  }, []);

  const clearWizardSession = useCallback(() => {
    setMealPlan(null);
    setMeals([]);
    setShopList(null);
    setPlanChefId(null);
    setSessionBaseline(null);
    setFurthestStep(1);
  }, []);

  const resetDownstreamFromPlan = useCallback(() => {
    setMeals([]);
    setShopList(null);
    setFurthestStep(2);
  }, []);

  const confirmSessionLoss = useCallback(() => {
    return window.confirm(SESSION_LOSS_WARNING);
  }, []);

  const goForward = useCallback(() => {
    setStep((s) => Math.min(s + 1, furthestStep));
  }, [furthestStep]);

  const loadChefs = useCallback(() => {
    listChefs()
      .then((r) => {
        setChefs(r.chefs);
        setPremiumUnlocked(r.premium_unlocked);
      })
      .catch(() => {});
    getAuthMe()
      .then((me) => {
        if (me.premium_unlocked) setPremiumUnlocked(true);
      })
      .catch(() => {});
  }, []);

  const refreshProfiles = useCallback(() => {
    listProfiles()
      .then((r) => setProfiles(r.profiles))
      .catch((e) => {
        setProfiles([]);
        setError(e instanceof Error ? e.message : "Could not load saved profiles");
      });
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [step]);

  useEffect(() => {
    startSession()
      .then(() => getState())
      .then((state) => {
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
          if (state.profile) {
            setSessionBaseline({
              ...profileToAnswers(state.profile as Record<string, unknown>),
              chef_id: chefId,
            });
          }
          const reached = stepIndexFromPhase(state.phase, !!state.profile);
          setFurthestStep(reached);
          if (state.phase === "plan_approval") setStep(2);
          else if (state.phase === "product_resolution") setStep(3);
          else if (state.phase === "budget_reconciliation") setStep(4);
          else if (state.phase === "cart" || state.phase === "complete") setStep(5);
        } else if (state.profile) {
          setFurthestStep(1);
          setStep(1);
        }
      })
      .catch((e) => setError(e.message));
    refreshProfiles();
    loadChefs();
  }, [refreshProfiles, loadChefs]);

  const handleDiscoveryContinue = async () => {
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
      if (!confirmSessionLoss()) return;
      clearWizardSession();
    }
    setLoading(true);
    setError("");
    try {
      await setProfile({ ...answers, chef_id: "basic_sam" });
      setSelectedChefId("basic_sam");
      markStepReached(1);
      setStep(1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save preferences");
    } finally {
      setLoading(false);
    }
  };

  const handleGeneratePlan = async () => {
    if (canReuseMealPlan({ mealPlan, planChefId, selectedChefId, answers, sessionBaseline })) {
      markStepReached(2);
      setStep(2);
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
      if (!confirmSessionLoss()) return;
      clearWizardSession();
    }
    setLoading(true);
    setError("");
    setPlanProgress({ done: 0, total: 5, message: "Starting…" });
    try {
      await setProfile({ ...answers, chef_id: selectedChefId });
      await streamSSE("/api/plan/generate", (event, data) => {
        if (event === "status") {
          setPlanProgress({
            done: Number(data.done ?? 0),
            total: Number(data.total ?? 5),
            message: String(data.message ?? ""),
          });
        }
        if (event === "warning") {
          setError(String(data.message));
        }
        if (event === "complete") {
          setMealPlan(data.meal_plan as MealPlan);
          setPlanChefId(selectedChefId);
          setSessionBaseline({ ...answers, chef_id: selectedChefId });
          setShopList(null);
          setAppState(data.state as AppState);
          markStepReached(2);
          setStep(2);
        }
        if (event === "error") setError(String(data.message));
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to generate plan");
    } finally {
      setLoading(false);
    }
  };

  const handleApprovePlan = async () => {
    setLoading(true);
    try {
      const res = await approvePlan();
      setMeals((res.meals ?? res.dinners) as Meal[]);
      setAppState(res.state);
      markStepReached(3);
      setStep(3);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setLoading(false);
    }
  };

  const runResolve = async (force = false) => {
    setLoading(true);
    setResolveProgress({ done: 0, total: 0, ingredient: "", phase: "search", message: "" });
    let completed = false;
    try {
      await streamSSE(`/api/shop/resolve${force ? "?force=true" : ""}`, (event, data) => {
        if (event === "status") {
          setResolveProgress((prev) => ({
            done: Number(data.done ?? prev.done),
            total: Number(data.total ?? prev.total),
            ingredient: String(data.ingredient || prev.ingredient),
            phase: String(data.phase || prev.phase || "search"),
            message: String(data.message || prev.message),
          }));
        }
        if (event === "progress") {
          setResolveProgress((prev) => ({
            done: Number(data.done),
            total: Number(data.total),
            ingredient: String(data.ingredient || ""),
            phase: String(data.phase || prev.phase || "search"),
            message: prev.message,
          }));
        }
        if (event === "complete") {
          completed = true;
          setShopList(data.resolved_list as ResolvedGroceryList);
          setAppState(data.state as AppState);
          markStepReached(4);
          setStep(4);
        }
        if (event === "error") setError(String(data.message));
      });
      if (!completed) {
        setError("Product search ended before completing — try again or check the API is running.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Resolve failed");
    } finally {
      setLoading(false);
    }
  };

  const handleResolve = async (force = false) => {
    if (shopList && !force) {
      markStepReached(4);
      setStep(4);
      return;
    }
    setError("");
    // Web: no Connect Woolworths gate — shop list builds without a session.
    await runResolve(force);
  };

  const handleApproveShop = async () => {
    setLoading(true);
    try {
      const res = await approveShop();
      setAppState(res.state);
      markStepReached(5);
      setStep(5);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSaveProfile = async (name: string) => {
    setSavingProfile(true);
    try {
      await saveProfile(name, answers);
      refreshProfiles();
      setSaveProfileOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSavingProfile(false);
    }
  };

  const handleDownloadRecipes = async () => {
    try {
      await downloadRecipes();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Download failed");
    }
  };

  const handleLoadProfile = async (id: string) => {
    const data = await loadProfile(id);
    setAnswers(profileToAnswers(data));
  };

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-xl font-bold text-slate-900">Woolworths Meal Agent</h1>
              <MobileStepper current={step} />
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-slate-500">
                Supermarket cart fill — coming soon
              </span>
              <Button variant="ghost" size="sm" onClick={() => setAuthOpen(true)}>
                Account
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setHelpOpen(true)}>
                Help
              </Button>
            </div>
          </div>
          <div className="mt-4">
            <Stepper current={step} />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            {error}
            <button type="button" className="ml-2 underline" onClick={() => setError("")}>
              dismiss
            </button>
          </div>
        )}

        {step === 0 && (
          <>
            <WizardNav
              showForward={step < furthestStep}
              onForward={goForward}
              className="mb-4"
            />
            <DiscoveryStep
            answers={answers}
            onChange={setAnswers}
            onContinue={handleDiscoveryContinue}
            onSaveProfile={() => setSaveProfileOpen(true)}
            onLoadProfile={handleLoadProfile}
            profiles={profiles}
            loading={loading}
            woolworthsConnected={null}
          />
          </>
        )}

        {step === 1 && (
          <>
            <WizardNav
              onBack={() => setStep(0)}
              backLabel="← Back to preferences"
              showForward={step < furthestStep}
              onForward={goForward}
              className="mb-4"
            />
            <ChefSelectStep
            chefs={chefs}
            premiumUnlocked={premiumUnlocked}
            selectedChefId={selectedChefId}
            hasExistingPlan={canReuseMealPlan({
              mealPlan,
              planChefId,
              selectedChefId,
              answers,
              sessionBaseline,
            })}
            onSelect={(id) => {
              setSelectedChefId(id);
              setAnswers((prev) => ({ ...prev, chef_id: id }));
            }}
            onGenerate={handleGeneratePlan}
            loading={loading}
            planProgress={planProgress}
          />
          </>
        )}

        {step === 2 && mealPlan && (
          <>
            <WizardNav
              onBack={() => setStep(1)}
              backLabel="← Back to choose chef"
              showForward={step < furthestStep}
              onForward={goForward}
              className="mb-4"
            />
            <MealPlanStep
            plan={mealPlan}
            allergies={answers.allergies}
            onApprove={handleApprovePlan}
            onSwap={async (idx) => {
              setLoading(true);
              try {
                const res = await swapMeal(idx);
                setMealPlan(res.meal_plan);
                setShopList(null);
              } finally {
                setLoading(false);
              }
            }}
            onRegenerate={async () => {
              setLoading(true);
              try {
                const res = await regeneratePlan();
                setMealPlan(res.meal_plan);
                setPlanChefId(selectedChefId);
                setShopList(null);
                setMeals([]);
                resetDownstreamFromPlan();
              } finally {
                setLoading(false);
              }
            }}
            loading={loading}
          />
          </>
        )}

        {step === 3 && (
          <>
            <WizardNav
              onBack={() => setStep(2)}
              backLabel="← Back to meal plan"
              showForward={step < furthestStep}
              onForward={goForward}
              className="mb-4"
            />
            <RecipesStep
            meals={meals}
            onContinue={() => handleResolve(false)}
            onRefreshSearch={() => handleResolve(true)}
            hasCachedList={!!shopList}
            onDownloadRecipes={handleDownloadRecipes}
            resolving={loading}
            progress={resolveProgress}
          />
          </>
        )}

        {step === 4 && !shopList && (
          <>
            <WizardNav
              onBack={() => setStep(3)}
              backLabel="← Back to recipes"
              showForward={step < furthestStep}
              onForward={goForward}
              className="mb-4"
            />
          <div className="rounded-xl border border-slate-200 bg-white p-8 text-center space-y-4">
            <h2 className="text-lg font-semibold text-slate-900">Shop list not ready</h2>
            <p className="text-sm text-slate-600">
              Product search has not finished yet, or the session was reset. Run Woolworths product
              search from the recipes step.
            </p>
            <div className="flex justify-center gap-2">
              <Button variant="secondary" onClick={() => setStep(3)}>
                ← Back to recipes
              </Button>
              <Button onClick={() => handleResolve(true)} disabled={loading}>
                {loading ? "Searching…" : "Find Woolworths products"}
              </Button>
            </div>
          </div>
          </>
        )}

        {step === 4 && shopList && (
          <>
            <WizardNav
              onBack={() => setStep(3)}
              backLabel="← Back to recipes"
              showForward={step < furthestStep}
              onForward={goForward}
              className="mb-4"
            />
            <ShopListStep
            list={shopList}
            suggestions={appState?.budget_suggestions ?? []}
            onApprove={handleApproveShop}
            loading={loading}
          />
          </>
        )}

        {step === 5 && (
          <>
            <WizardNav
              onBack={() => setStep(4)}
              backLabel="← Back to shop list"
              className="mb-4"
            />
            <div className="rounded-xl border border-slate-200 bg-white p-8 space-y-5">
              <div className="text-center space-y-2">
                <h2 className="text-xl font-bold text-slate-900">Fill shopping cart, coming soon</h2>
                <p className="text-sm text-slate-600">
                  Soon you’ll send this list to your supermarket trolley in one tap. For now, use your
                  shop list — trolley fill is on the way.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                {(
                  [
                    { name: "Woolworths", color: "bg-[#178841]" },
                    { name: "FreshChoice", color: "bg-[#F36C00]" },
                    { name: "New World", color: "bg-[#C8102E]" },
                  ] as const
                ).map((r) => (
                  <button
                    key={r.name}
                    type="button"
                    className={`${r.color} text-white rounded-xl px-4 py-4 font-semibold shadow-sm opacity-95 cursor-default`}
                    onClick={() => setError(`${r.name} cart fill — coming soon`)}
                  >
                    {r.name}
                    <span className="block text-xs font-medium opacity-90 mt-1">Coming soon</span>
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </main>

      <footer className="border-t border-slate-200 bg-white py-3 text-center text-xs text-slate-500">
        Shop list is ready to review — filling a supermarket trolley is coming soon.
      </footer>

      <AuthModal
        open={authOpen}
        onClose={() => setAuthOpen(false)}
        onSuccess={() => loadChefs()}
      />

      <SaveProfileModal
        open={saveProfileOpen}
        onClose={() => setSaveProfileOpen(false)}
        onSave={handleSaveProfile}
        saving={savingProfile}
      />

      {helpOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-w-lg rounded-xl bg-white p-6 shadow-xl text-sm text-slate-700 space-y-2">
            <h3 className="font-semibold text-base">Help</h3>
            <p>
              <strong>Connect Woolworths</strong> — opens woolworths.co.nz in your default browser
              (Chrome, Edge, or Firefox). Sign in there only; SmartCart copies session cookies for
              automation. Use Disconnect to clear them.
            </p>
            <p>
              <strong>Manual items</strong> — no Woolworths match found; search and add these yourself.
            </p>
            <p>
              <strong>Trolley link</strong> — opens woolworths.co.nz/reviewtrolley. Sign in with
              the same account you connected here.
            </p>
            <p>
              <strong>Choose Chef</strong> — Sam (Basic) is free and uses AI for varied home
              cooking; premium chefs add regional specialisation (subscription required).
            </p>
            <p>
              <strong>Account</strong> — sign in for subscriber-only premium chefs.
            </p>
            <Button variant="secondary" onClick={() => setHelpOpen(false)}>
              Close
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
