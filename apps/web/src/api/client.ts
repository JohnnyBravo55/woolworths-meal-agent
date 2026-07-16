import {
  createApiClient,
  createWebSessionStore,
  type SSEHandler,
} from "@meal-agent/app-core";
import type {
  AppState,
  CartResult,
  ChefPersona,
  DiscoveryAnswers,
  MealPlan,
  ResolvedGroceryList,
} from "@meal-agent/app-core";

export type { AppState, CartResult, ChefPersona, DiscoveryAnswers, MealPlan, ResolvedGroceryList, SSEHandler };

const sessionStore = createWebSessionStore();

export const api = createApiClient({
  baseUrl: "",
  sessionStore,
  useCredentials: true,
});

export async function startSession() {
  return api.startSession();
}

export async function getState() {
  return api.getState();
}

export async function getWoolworthsStatus() {
  return api.getWoolworthsStatus();
}

export async function listChefs() {
  return api.listChefs();
}

export async function getAuthMe() {
  return api.getAuthMe();
}

export async function woolworthsLogin(opts?: { openBrowser?: boolean; timeoutSeconds?: number }) {
  return api.woolworthsLogin(opts);
}

export async function woolworthsSync() {
  return api.woolworthsSync();
}

export async function woolworthsDisconnect() {
  return api.woolworthsDisconnect();
}

export async function listProfiles() {
  return api.listProfiles();
}

export async function loadProfile(id: string) {
  return api.loadProfile(id);
}

export async function saveProfile(name: string, answers: DiscoveryAnswers) {
  return api.saveProfile(name, answers);
}

export async function setProfile(answers: DiscoveryAnswers) {
  return api.setProfile(answers);
}

export async function approvePlan() {
  return api.approvePlan();
}

export async function swapMeal(mealIndex: number) {
  return api.swapMeal(mealIndex);
}

export async function regeneratePlan() {
  return api.regeneratePlan();
}

export async function approveShop() {
  return api.approveShop();
}

export async function addToCart(opts: { allow_over_budget?: boolean; export_only?: boolean }) {
  return api.addToCart(opts);
}

export async function retryCart() {
  return api.retryCart();
}

export async function getCartUrl() {
  return api.getCartUrl();
}

export async function authRegister(email: string, password: string) {
  return api.authRegister(email, password);
}

export async function authLogin(email: string, password: string) {
  return api.authLogin(email, password);
}

export async function authMe() {
  return api.getAuthMe();
}

export function exportCsvUrl() {
  return api.exportCsvUrl();
}

export function exportMarkdownUrl() {
  return api.exportMarkdownUrl();
}

export async function downloadRecipes() {
  return api.downloadRecipes("web");
}

export async function streamSSE(path: string, onEvent: SSEHandler, init?: RequestInit) {
  return api.streamSSE(path, onEvent, init);
}

export async function streamCartAdd(
  onEvent: SSEHandler,
  opts: { allow_over_budget?: boolean } = {},
) {
  return api.streamCartAdd(onEvent, opts);
}

export const computeAddableTotal = api.computeAddableTotal.bind(api);
export const computeOfflineTotal = api.computeOfflineTotal.bind(api);
