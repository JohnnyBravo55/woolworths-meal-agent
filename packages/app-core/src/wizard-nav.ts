import type { DiscoveryAnswers } from "./types";

export const WIZARD_ROUTES = ["discovery", "chef", "plan", "recipes", "shop", "cart"] as const;
export type WizardRoute = (typeof WIZARD_ROUTES)[number];

export const SESSION_LOSS_WARNING =
  "You will lose previous meal plans and start a new session.";

export function stepIndexFromRoute(route: string): number {
  const idx = WIZARD_ROUTES.indexOf(route as WizardRoute);
  return idx >= 0 ? idx : 0;
}

export function routeFromStepIndex(index: number): WizardRoute {
  const clamped = Math.max(0, Math.min(WIZARD_ROUTES.length - 1, index));
  return WIZARD_ROUTES[clamped];
}

export function stepIndexFromPhase(phase: string | undefined, hasProfile: boolean): number {
  switch (phase) {
    case "plan_approval":
      return 2;
    case "product_resolution":
      return 3;
    case "budget_reconciliation":
      return 4;
    case "cart":
    case "complete":
      return 5;
    default:
      return hasProfile ? 1 : 0;
  }
}

export function preferencesFingerprint(answers: DiscoveryAnswers): string {
  const { chef_id: _chef, ...prefs } = answers;
  return JSON.stringify(prefs);
}

export function hasPreferencesChanged(
  current: DiscoveryAnswers,
  baseline: DiscoveryAnswers | null,
): boolean {
  if (!baseline) return false;
  return preferencesFingerprint(current) !== preferencesFingerprint(baseline);
}

/** True when the on-screen chef/prefs no longer match the plan currently held. */
export function isMealPlanStale(opts: {
  mealPlan: unknown | null;
  planChefId: string | null;
  selectedChefId: string;
  answers: DiscoveryAnswers;
  sessionBaseline: DiscoveryAnswers | null;
}): boolean {
  if (!opts.mealPlan) return false;
  if (opts.planChefId && opts.planChefId !== opts.selectedChefId) return true;
  if (hasPreferencesChanged(opts.answers, opts.sessionBaseline)) return true;
  return false;
}

export function canReuseMealPlan(opts: {
  mealPlan: unknown | null;
  planChefId: string | null;
  selectedChefId: string;
  answers: DiscoveryAnswers;
  sessionBaseline: DiscoveryAnswers | null;
}): boolean {
  if (!opts.mealPlan || !opts.planChefId) return false;
  if (isMealPlanStale(opts)) return false;
  return true;
}

export function needsSessionLossWarning(opts: {
  mealPlan: unknown | null;
  planChefId: string | null;
  selectedChefId: string;
  answers: DiscoveryAnswers;
  sessionBaseline: DiscoveryAnswers | null;
  forChefChange?: boolean;
  forPreferencesChange?: boolean;
}): boolean {
  if (!opts.mealPlan) return false;
  if (opts.forPreferencesChange && hasPreferencesChanged(opts.answers, opts.sessionBaseline)) {
    return true;
  }
  if (opts.forChefChange && opts.planChefId !== opts.selectedChefId) {
    return true;
  }
  return false;
}
