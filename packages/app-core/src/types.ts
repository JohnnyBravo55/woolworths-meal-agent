export type AgentPhase =
  | "discovery"
  | "plan_draft"
  | "plan_approval"
  | "product_resolution"
  | "budget_reconciliation"
  | "cart"
  | "recipes"
  | "complete";

export type ChildrenAgeBands = {
  "1-3": number;
  "4-6": number;
  "7-9": number;
  "10-12": number;
};

export interface DiscoveryAnswers {
  household_size: number;
  adults: number;
  children_under_13: number;
  children_age_bands: ChildrenAgeBands;
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

export type StoreChain = "woolworths" | "paknsave" | "new_world" | "freshchoice";

export interface StoreRef {
  id: string;
  chain: StoreChain;
  name: string;
  address?: string;
  suburb?: string;
  pricing_note?: string;
  /** Homepage / shopfront URL for assisted shopping. */
  store_url?: string;
}

export interface PriceCheckLine {
  ingredient: string;
  quantity: number;
  unit: string;
  product_name: string;
  sku: string;
  unit_price: number;
  line_total: number;
  price_source: "live" | "estimate";
  note: string;
  /** Direct product page when known. */
  product_url?: string;
  /** Catalogue search URL for this line. */
  search_url?: string;
}

export interface PriceCheckStoreBasket {
  store: StoreRef;
  total: number;
  live_count: number;
  estimate_count: number;
  lines: PriceCheckLine[];
  warning: string;
}

export interface PriceSplitAssignment {
  ingredient: string;
  store_id: string;
  store_name: string;
  chain: StoreChain;
  line: PriceCheckLine;
}

export interface PriceSplitResult {
  total: number;
  savings_vs_cheapest_single_store: number;
  estimate_count: number;
  live_count: number;
  assignments: PriceSplitAssignment[];
  note: string;
}

export interface PriceCheckSkippedStore {
  store: StoreRef;
  reason: string;
}

export interface PriceCheckResult {
  baskets: PriceCheckStoreBasket[];
  skipped?: PriceCheckSkippedStore[];
  split: PriceSplitResult | null;
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

export const EMPTY_AGE_BANDS: ChildrenAgeBands = {
  "1-3": 0,
  "4-6": 0,
  "7-9": 0,
  "10-12": 0,
};

export const AGE_BAND_KEYS: (keyof ChildrenAgeBands)[] = ["1-3", "4-6", "7-9", "10-12"];

export function ageBandsSum(bands: ChildrenAgeBands): number {
  return AGE_BAND_KEYS.reduce((sum, key) => sum + (bands[key] || 0), 0);
}

/** Max allowed for one band so total assigned ages never exceeds children. */
export function maxForAgeBand(
  bands: ChildrenAgeBands,
  key: keyof ChildrenAgeBands,
  childrenUnder13: number,
): number {
  const children = Math.max(0, childrenUnder13);
  const others = ageBandsSum(bands) - (bands[key] || 0);
  return Math.max(0, children - others);
}

export function clampAgeBandValue(
  bands: ChildrenAgeBands,
  key: keyof ChildrenAgeBands,
  value: number,
  childrenUnder13: number,
): ChildrenAgeBands {
  const capped = Math.min(Math.max(0, Math.floor(value)), maxForAgeBand(bands, key, childrenUnder13));
  return { ...bands, [key]: capped };
}

/** When child count drops, reduce band totals so they never exceed the new total. */
export function trimAgeBandsToChildren(
  bands: ChildrenAgeBands,
  childrenUnder13: number,
): ChildrenAgeBands {
  const children = Math.max(0, childrenUnder13);
  if (children === 0) return { ...EMPTY_AGE_BANDS };
  let excess = ageBandsSum(bands) - children;
  if (excess <= 0) return { ...bands };
  const next: ChildrenAgeBands = { ...bands };
  for (const key of [...AGE_BAND_KEYS].reverse()) {
    if (excess <= 0) break;
    const take = Math.min(next[key] || 0, excess);
    next[key] = (next[key] || 0) - take;
    excess -= take;
  }
  return next;
}

export const DEFAULT_ANSWERS: DiscoveryAnswers = {
  household_size: 2,
  adults: 2,
  children_under_13: 0,
  children_age_bands: { ...EMPTY_AGE_BANDS },
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

function parseAgeBands(raw: unknown): ChildrenAgeBands {
  const src = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  return {
    "1-3": Number(src["1-3"] ?? src.band_1_3 ?? 0) || 0,
    "4-6": Number(src["4-6"] ?? src.band_4_6 ?? 0) || 0,
    "7-9": Number(src["7-9"] ?? src.band_7_9 ?? 0) || 0,
    "10-12": Number(src["10-12"] ?? src.band_10_12 ?? 0) || 0,
  };
}

export function profileToAnswers(data: Record<string, unknown>): DiscoveryAnswers {
  const hasAdults = data.adults !== undefined && data.adults !== null;
  const hasChildren = data.children_under_13 !== undefined && data.children_under_13 !== null;
  const householdSize = Number(data.household_size ?? 2) || 2;
  const adults = hasAdults || hasChildren ? Number(data.adults ?? 2) || 0 : householdSize;
  const children_under_13 =
    hasAdults || hasChildren ? Number(data.children_under_13 ?? 0) || 0 : 0;
  const children_age_bands =
    children_under_13 > 0 ? parseAgeBands(data.children_age_bands) : { ...EMPTY_AGE_BANDS };
  return {
    household_size: Math.max(1, adults + children_under_13),
    adults,
    children_under_13,
    children_age_bands,
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
