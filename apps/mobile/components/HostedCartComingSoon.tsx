import { useEffect, useRef, useState } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { FeedbackModal } from "@/components/FeedbackModal";
import {
  FEEDBACK_AUTO_OPEN_MS,
  FEEDBACK_DISMISSED_VISIT_KEY,
  FEEDBACK_SUBMITTED_KEY,
} from "@/constants/feedback";
import { theme } from "@/constants/theme";

const RETAILERS = [
  {
    id: "woolworths",
    name: "Woolworths",
    color: "#178841",
    url: "https://www.woolworths.co.nz",
  },
  {
    id: "freshchoice",
    name: "FreshChoice",
    color: "#F36C00",
    url: "https://store.freshchoice.co.nz",
  },
  {
    id: "new-world",
    name: "New World",
    color: "#C8102E",
    url: "https://www.newworld.co.nz",
  },
  {
    id: "paknsave",
    name: "Pak'nSave",
    color: "#FFD100",
    url: "https://www.paknsave.co.nz",
    darkText: true,
  },
] as const;

const FEEDBACK_BLUE = "#2563eb";

function readStorage(storage: Storage | undefined, key: string): boolean {
  try {
    return storage?.getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeStorage(storage: Storage | undefined, key: string): void {
  try {
    storage?.setItem(key, "1");
  } catch {
    // Storage can be unavailable; keep feedback usable.
  }
}

async function openUrl(url: string) {
  if (Platform.OS === "web" && typeof window !== "undefined") {
    window.open(url, "_blank", "noopener,noreferrer");
    return;
  }
  await WebBrowser.openBrowserAsync(url);
}

/**
 * Hosted cart step: guided assisted shop (no silent trolley fill).
 * Native builds use the real Woolworths cart screen instead.
 */
export function HostedCartComingSoon() {
  const router = useRouter();
  const [toast, setToast] = useState("");
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const autoOpenTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearAutoOpenTimer = () => {
    if (autoOpenTimerRef.current !== null) {
      clearTimeout(autoOpenTimerRef.current);
      autoOpenTimerRef.current = null;
    }
  };

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (readStorage(window.localStorage, FEEDBACK_SUBMITTED_KEY)) return;
    if (readStorage(window.sessionStorage, FEEDBACK_DISMISSED_VISIT_KEY)) return;

    autoOpenTimerRef.current = setTimeout(() => {
      autoOpenTimerRef.current = null;
      if (readStorage(window.localStorage, FEEDBACK_SUBMITTED_KEY)) return;
      if (readStorage(window.sessionStorage, FEEDBACK_DISMISSED_VISIT_KEY)) return;
      setFeedbackOpen(true);
    }, FEEDBACK_AUTO_OPEN_MS);
    return clearAutoOpenTimer;
  }, []);

  const onPressRetailer = async (name: string, url: string) => {
    setToast(`Opening ${name}. Use Compare & shop on your list for matched Search / Open links.`);
    await openUrl(url);
  };

  const closeFeedback = () => {
    clearAutoOpenTimer();
    setFeedbackOpen(false);
    if (typeof window !== "undefined") {
      writeStorage(window.sessionStorage, FEEDBACK_DISMISSED_VISIT_KEY);
    }
  };

  const onSubmitted = () => {
    clearAutoOpenTimer();
    setFeedbackOpen(false);
    if (typeof window !== "undefined") {
      writeStorage(window.localStorage, FEEDBACK_SUBMITTED_KEY);
    }
  };

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>Shop at your supermarket</Text>
      <Text style={styles.subtitle}>
        Open a store site and add items yourself. For matched products and Search / Open links, go
        back to the shop list and use Compare & shop stores.
      </Text>

      <Pressable
        accessibilityLabel="Back to shop list for assisted shopping"
        onPress={() => router.push("/shop")}
        style={({ pressed }) => [styles.primaryBtn, { opacity: pressed ? 0.88 : 1 }]}
      >
        <Text style={styles.primaryBtnText} selectable={false}>
          Compare & shop on list
        </Text>
      </Pressable>

      <View style={styles.buttons}>
        {RETAILERS.map((r) => (
          <Pressable
            key={r.id}
            accessibilityLabel={`Open ${r.name} website`}
            onPress={() => onPressRetailer(r.name, r.url)}
            style={({ pressed }) => [
              styles.retailerBtn,
              { backgroundColor: r.color, opacity: pressed ? 0.88 : 1 },
            ]}
          >
            <View
              style={[
                styles.logoMark,
                "darkText" in r && r.darkText ? styles.logoMarkDark : null,
              ]}
            >
              <Text
                style={[
                  styles.logoInitial,
                  "darkText" in r && r.darkText ? styles.logoInitialDark : null,
                ]}
                selectable={false}
              >
                {r.name.charAt(0)}
              </Text>
            </View>
            <Text
              style={[
                styles.retailerName,
                "darkText" in r && r.darkText ? styles.retailerNameDark : null,
              ]}
              selectable={false}
            >
              {r.name}
            </Text>
            <Text
              style={[styles.coming, "darkText" in r && r.darkText ? styles.comingDark : null]}
              selectable={false}
            >
              Open site
            </Text>
          </Pressable>
        ))}
      </View>

      <Pressable
        accessibilityLabel="Give feedback"
        onPress={() => setFeedbackOpen(true)}
        style={({ pressed }) => [styles.feedbackBtn, { opacity: pressed ? 0.88 : 1 }]}
      >
        <Text style={styles.feedbackBtnText} selectable={false}>
          Give feedback
        </Text>
      </Pressable>

      {toast ? <Text style={styles.toast}>{toast}</Text> : null}

      <FeedbackModal
        visible={feedbackOpen}
        onClose={closeFeedback}
        onSubmitted={onSubmitted}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingVertical: 8,
    gap: 14,
  },
  title: {
    fontSize: 22,
    fontWeight: "800",
    color: theme.text,
    textAlign: "center",
  },
  subtitle: {
    fontSize: 14,
    lineHeight: 20,
    color: theme.textMuted,
    textAlign: "center",
    marginBottom: 4,
  },
  primaryBtn: {
    alignSelf: "center",
    backgroundColor: theme.green,
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 20,
    minWidth: 240,
    alignItems: "center",
  },
  primaryBtnText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "800",
  },
  buttons: {
    gap: 10,
    marginTop: 4,
  },
  retailerBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 16,
    minHeight: 56,
    ...(Platform.OS === "web" ? ({ userSelect: "none" } as object) : {}),
  },
  logoMark: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: "rgba(255,255,255,0.22)",
    alignItems: "center",
    justifyContent: "center",
  },
  logoMarkDark: {
    backgroundColor: "rgba(0,0,0,0.12)",
  },
  logoInitial: {
    color: "#fff",
    fontSize: 18,
    fontWeight: "800",
  },
  logoInitialDark: {
    color: "#111",
  },
  retailerName: {
    flex: 1,
    color: "#fff",
    fontSize: 17,
    fontWeight: "700",
  },
  retailerNameDark: {
    color: "#111",
  },
  coming: {
    color: "rgba(255,255,255,0.85)",
    fontSize: 12,
    fontWeight: "600",
  },
  comingDark: {
    color: "rgba(0,0,0,0.7)",
  },
  feedbackBtn: {
    marginTop: 18,
    alignSelf: "center",
    backgroundColor: FEEDBACK_BLUE,
    borderRadius: 14,
    paddingVertical: 18,
    paddingHorizontal: 28,
    minHeight: 64,
    minWidth: 280,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: FEEDBACK_BLUE,
    shadowOpacity: 0.35,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 5,
    ...(Platform.OS === "web" ? ({ userSelect: "none" } as object) : {}),
  },
  feedbackBtnText: {
    color: "#fff",
    fontSize: 19,
    fontWeight: "800",
    letterSpacing: 0.2,
  },
  toast: {
    marginTop: 4,
    textAlign: "center",
    fontSize: 13,
    fontWeight: "600",
    color: theme.text,
  },
});
