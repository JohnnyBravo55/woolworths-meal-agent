export type AgentPhase =
  | "discovery"
  | "plan_draft"
  | "plan_approval"
  | "product_resolution"
  | "budget_reconciliation"
  | "cart"
  | "recipes"
  | "complete";

export interface DiscoveryAnswers {
  household_size: number;
  days: number;
  dinner_count: number;
  lunch_count: number;
  snack_count: number;
  allergies: string;
  mandatory_items: string;
  pantry_items: string;
  likes: string;
  dislikes: string;
  other_instructions: string;
  budget_nzd: number;
  store_name: string;
  simplicity: string;
  brand_preference: string;
  chef_id: string;
  lunch_mode: "practical" | "original";
}

export interface ChefPersona {
  id: string;
  name: string;
  title: string;
  tier: "basic" | "premium";
  region: string;
  tagline: string;
  avatar_initials: string;
  avatar_from: string;
  avatar_to: string;
  avatar_image?: string;
}

export interface Meal {
  name: string;
  slot: "breakfast" | "lunch" | "dinner" | "snack";
  day_label: string;
  description: string;
  prep_time_minutes: number;
  ingredients: { name: string; quantity: number; unit: string }[];
  steps: string[];
}

export interface MealPlan {
  meals: Meal[];
  shared_ingredients: unknown[];
  chef_notes: string;
}

export interface GroceryLineItem {
  ingredient: string;
  sku: string;
  product_name: string;
  quantity: number;
  unit: string;
  unit_price: number;
  line_total: number;
  is_mandatory: boolean;
  in_stock: boolean;
  product_url: string;
  warnings?: string[];
  cart_blocked?: boolean;
  block_reason?: string;
}

export interface ResolvedGroceryList {
  items: GroceryLineItem[];
  total: number;
  budget_nzd: number;
  within_budget: boolean;
  addable_total?: number;
  offline_total?: number;
}

export interface BudgetSuggestion {
  action: string;
  ingredient: string;
  current_sku: string;
  suggested_sku: string | null;
  savings: number;
  message: string;
}

export interface AppState {
  phase: AgentPhase;
  profile: unknown | null;
  meal_plan: MealPlan | null;
  resolved_list: ResolvedGroceryList | null;
  plan_approved: boolean;
  products_approved: boolean;
  cart_attempted: boolean;
  cart_success: boolean;
  cart_errors: string[];
  export_paths: string[];
  budget_suggestions: BudgetSuggestion[];
}

export interface CartResult {
  success_count: number;
  failure_count: number;
  skipped_offline: number;
  added_total: number;
  cart_subtotal: number | null;
  session_lost: boolean;
  errors: string[];
  export_paths: string[];
  duplicate_lines_merged?: number;
  cart_line_count?: number | null;
}

export interface WoolworthsCookie {
  name: string;
  value: string;
  domain: string;
  path: string;
  expires: number;
  httpOnly: boolean;
  secure: boolean;
  sameSite: string;
}

export const DEFAULT_ANSWERS: DiscoveryAnswers = {
  household_size: 2,
  days: 7,
  dinner_count: 6,
  lunch_count: 0,
  snack_count: 0,
  allergies: "",
  mandatory_items: "",
  pantry_items: "",
  likes: "",
  dislikes: "",
  other_instructions: "",
  /** 0 = left blank in the form; API applies a soft default when unset. */
  budget_nzd: 0,
  store_name: "",
  simplicity: "simple",
  brand_preference: "mixed",
  chef_id: "basic_sam",
  lunch_mode: "original",
};

export const STEPS = [
  { id: 0, label: "Preferences", key: "shop" },
  { id: 1, label: "Choose Chef", key: "chef" },
  { id: 2, label: "Meal Plan", key: "plan" },
  { id: 3, label: "Recipes", key: "recipes" },
  { id: 4, label: "Shop List", key: "list" },
  { id: 5, label: "Cart", key: "cart" },
] as const;

export function profileToAnswers(data: Record<string, unknown>): DiscoveryAnswers {
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
    lunch_mode: (data.lunch_mode === "practical" ? "practical" : "original") as
      | "practical"
      | "original",
  };
}

export function chefAvatarUrl(apiBase: string, avatarImage?: string): string | undefined {
  if (!avatarImage) return undefined;
  if (avatarImage.startsWith("http")) return avatarImage;
  return `${apiBase.replace(/\/$/, "")}${avatarImage}`;
}
