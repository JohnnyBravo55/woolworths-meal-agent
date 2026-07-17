import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
import { api } from "./api";

const WOOLWORTHS_MOBILE_LINKED = "meal_agent_woolworths_mobile_linked";

export async function setMobileWoolworthsLinked(linked: boolean): Promise<void> {
  if (Platform.OS === "web") return;
  if (linked) {
    await SecureStore.setItemAsync(WOOLWORTHS_MOBILE_LINKED, "1");
  } else {
    await SecureStore.deleteItemAsync(WOOLWORTHS_MOBILE_LINKED);
  }
}

export async function isMobileWoolworthsLinked(): Promise<boolean> {
  if (Platform.OS === "web") return true;
  const v = await SecureStore.getItemAsync(WOOLWORTHS_MOBILE_LINKED);
  return v === "1";
}

/** On phone, require WebView sign-in — PC API cookies don't mean the phone session is linked. */
export async function needsMobileWoolworthsSignIn(): Promise<boolean> {
  if (Platform.OS === "web") return false;
  return !(await isMobileWoolworthsLinked());
}

/** Web never gates on Woolworths connect (Coming soon cart). Phone still does. */
export async function needsWoolworthsSignInBeforeShop(): Promise<boolean> {
  if (Platform.OS === "web") return false;
  return needsMobileWoolworthsSignIn();
}

export async function needsWoolworthsSignInForCart(): Promise<boolean> {
  if (Platform.OS === "web") return false;
  return needsWoolworthsSignInBeforeShop();
}
