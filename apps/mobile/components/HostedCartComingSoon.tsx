import { useEffect, useRef, useState } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { FeedbackModal } from "@/components/FeedbackModal";
import {
  FEEDBACK_AUTO_OPEN_MS,
  FEEDBACK_DISMISSED_VISIT_KEY,
  FEEDBACK_SUBMITTED_KEY,
} from "@/constants/feedback";
import { theme } from "@/constants/theme";

const RETAILERS = [
  { id: "woolworths", name: "Woolworths", color: "#178841" },
  { id: "freshchoice", name: "FreshChoice", color: "#F36C00" },
  { id: "new-world", name: "New World", color: "#C8102E" },
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

/**
 * Hosted-only cart teaser: no Woolworths connect / add-to-trolley.
 * Local builds use the real cart screen instead.
 */
export function HostedCartComingSoon() {
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

  const onPressRetailer = (name: string) => {
    setToast(`${name} cart fill — coming soon`);
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
      <Text style={styles.title}>Fill shopping cart, coming soon</Text>
      <Text style={styles.subtitle}>
        Soon you’ll send this list to your supermarket trolley in one tap. For now, use your shop list
        above — trolley fill is on the way.
      </Text>

      <View style={styles.buttons}>
        {RETAILERS.map((r) => (
          <Pressable
            key={r.id}
            accessibilityLabel={`${r.name}, coming soon`}
            onPress={() => onPressRetailer(r.name)}
            style={({ pressed }) => [
              styles.retailerBtn,
              { backgroundColor: r.color, opacity: pressed ? 0.88 : 1 },
            ]}
          >
            <View style={styles.logoMark}>
              <Text style={styles.logoInitial} selectable={false}>
                {r.name.charAt(0)}
              </Text>
            </View>
            <Text style={styles.retailerName} selectable={false}>
              {r.name}
            </Text>
            <Text style={styles.coming} selectable={false}>
              Coming soon
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
  logoInitial: {
    color: "#fff",
    fontSize: 18,
    fontWeight: "800",
  },
  retailerName: {
    flex: 1,
    color: "#fff",
    fontSize: 17,
    fontWeight: "700",
  },
  coming: {
    color: "rgba(255,255,255,0.85)",
    fontSize: 12,
    fontWeight: "600",
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
