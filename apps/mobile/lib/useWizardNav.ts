import {
  routeFromStepIndex,
  stepIndexFromRoute,
  type WizardRoute,
} from "@meal-agent/app-core";
import { useRouter, useSegments } from "expo-router";
import { useApp } from "@/context/AppProvider";

export function useWizardNav() {
  const router = useRouter();
  const segments = useSegments();
  const { furthestStep } = useApp();
  const route = String(segments[segments.length - 1] ?? "discovery");
  const currentStep = stepIndexFromRoute(route);
  const showForward = currentStep < furthestStep;

  const goForward = () => {
    const next = routeFromStepIndex(currentStep + 1);
    router.push(`/${next}` as `/${WizardRoute}`);
  };

  return { route, currentStep, furthestStep, showForward, goForward };
}
