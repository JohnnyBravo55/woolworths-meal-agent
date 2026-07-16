import { Stack } from "expo-router";
import { AccessCodeGate } from "@/components/AccessCodeGate";
import { AppProvider } from "@/context/AppProvider";

export default function RootLayout() {
  return (
    <AccessCodeGate>
      <AppProvider>
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="index" />
          <Stack.Screen name="discovery" />
          <Stack.Screen name="chef" />
          <Stack.Screen name="plan" />
          <Stack.Screen name="recipes" />
          <Stack.Screen name="shop" />
          <Stack.Screen name="cart" />
          <Stack.Screen name="connect-woolworths" options={{ presentation: "fullScreenModal" }} />
        </Stack>
      </AppProvider>
    </AccessCodeGate>
  );
}
