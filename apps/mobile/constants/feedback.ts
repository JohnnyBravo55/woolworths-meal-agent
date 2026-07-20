export const FEEDBACK_SUBMITTED_KEY = "meal-agent-feedback-submitted";
export const FEEDBACK_DISMISSED_VISIT_KEY = "meal-agent-feedback-dismissed-visit";
export const FEEDBACK_AUTO_OPEN_MS = 10_000;

export const MEAL_PLAN_USEFUL_OPTIONS = [
  "Very useful",
  "Useful",
  "Unsure",
  "Unhelpful",
  "Not useful",
] as const;

export const MOST_VALUABLE_OPTIONS = [
  "Chef meal plan",
  "Shopping list",
  "Personalised preferences",
  "Saving time",
  "None",
] as const;

export const LIKELIHOOD_OPTIONS = [
  "Very likely",
  "Likely",
  "Unsure",
  "Unlikely",
  "Definitely not",
] as const;

export const IF_NEVER_PUBLIC_OPTIONS = [
  "Very disappointed",
  "Disappointed",
  "Unsure",
  "Not disappointed",
  "Not at all disappointed",
] as const;

export type MealPlanUseful = (typeof MEAL_PLAN_USEFUL_OPTIONS)[number];
export type MostValuable = (typeof MOST_VALUABLE_OPTIONS)[number];
export type Likelihood = (typeof LIKELIHOOD_OPTIONS)[number];
export type IfNeverPublic = (typeof IF_NEVER_PUBLIC_OPTIONS)[number];
