import { SESSION_LOSS_WARNING } from "@meal-agent/app-core";
import { Alert, Platform } from "react-native";

export function confirmSessionLoss(): Promise<boolean> {
  if (Platform.OS === "web") {
    return Promise.resolve(
      typeof window !== "undefined" ? window.confirm(SESSION_LOSS_WARNING) : false,
    );
  }
  return new Promise((resolve) => {
    Alert.alert("Start a new session?", SESSION_LOSS_WARNING, [
      { text: "Cancel", style: "cancel", onPress: () => resolve(false) },
      { text: "Continue", style: "destructive", onPress: () => resolve(true) },
    ]);
  });
}
