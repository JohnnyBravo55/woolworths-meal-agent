import { useCallback, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Button } from "@/components/ui/Button";
import {
  NDA_BLOCKS,
  NDA_VERSION,
  markNdaAccepted,
  type NdaBlock,
} from "@/constants/nda";
import { theme } from "@/constants/theme";
import { api } from "@/lib/api";

function NdaBlockView({ block }: { block: NdaBlock }) {
  switch (block.type) {
    case "title":
      return <Text style={styles.docTitle}>{block.text}</Text>;
    case "subtitle":
      return <Text style={styles.docSubtitle}>{block.text}</Text>;
    case "heading":
      return <Text style={styles.docHeading}>{block.text}</Text>;
    case "paragraph":
      return <Text style={styles.docParagraph}>{block.text}</Text>;
    case "bullet":
      return <Text style={styles.docBullet}>• {block.text}</Text>;
    case "numbered":
      return (
        <Text style={styles.docBullet}>
          {block.n}. {block.text}
        </Text>
      );
    case "rule":
      return <View style={styles.rule} />;
    default:
      return null;
  }
}

export function NdaGate({ onAccepted }: { onAccepted: () => void }) {
  const [fullName, setFullName] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = Boolean(fullName.trim()) && agreed && !submitting;

  const onSubmit = useCallback(async () => {
    if (!canSubmit) return;
    setError("");
    setSubmitting(true);
    try {
      await api.acceptNda({
        full_name: fullName.trim(),
        agreed: true,
        nda_version: NDA_VERSION,
      });
      markNdaAccepted();
      onAccepted();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Could not record NDA acceptance";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }, [canSubmit, fullName, onAccepted]);

  return (
    <View style={styles.screen}>
      <View style={styles.card}>
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          testID="nda-scroll"
        >
          {NDA_BLOCKS.map((block, i) => (
            <NdaBlockView key={i} block={block} />
          ))}

          <Text style={styles.fieldLabel}>Full Legal Name:</Text>
          <TextInput
            style={styles.input}
            value={fullName}
            onChangeText={setFullName}
            placeholder="Type your full legal name"
            placeholderTextColor={theme.placeholder}
            autoCapitalize="words"
            autoCorrect={false}
            testID="nda-full-name"
            accessibilityLabel="Full legal name"
          />

          <Text style={styles.fieldLabel}>Date Accepted:</Text>
          <Text style={styles.dateHint}>Automatically recorded electronically</Text>

          <Pressable
            style={styles.checkboxRow}
            onPress={() => setAgreed((v) => !v)}
            accessibilityRole="checkbox"
            accessibilityState={{ checked: agreed }}
            testID="nda-agree"
          >
            <View style={[styles.checkbox, agreed && styles.checkboxChecked]}>
              {agreed ? <Text style={styles.checkmark}>✓</Text> : null}
            </View>
            <Text style={styles.checkboxLabel}>
              I Agree to the Confidential Beta Testing Agreement
            </Text>
          </Pressable>
        </ScrollView>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Button
          title={submitting ? "Submitting…" : "Accept & Begin Beta Test"}
          onPress={() => void onSubmit()}
          disabled={!canSubmit}
          loading={submitting}
          testID="nda-accept"
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: theme.bg,
    alignItems: "center",
    justifyContent: "center",
    padding: 16,
  },
  card: {
    width: "100%",
    maxWidth: 640,
    maxHeight: "100%",
    flex: 1,
    backgroundColor: theme.white,
    borderRadius: 16,
    padding: 20,
    borderWidth: 1,
    borderColor: theme.border,
    gap: 12,
  },
  scroll: { flex: 1 },
  scrollContent: { paddingBottom: 16, gap: 8 },
  docTitle: {
    fontSize: 22,
    fontWeight: "800",
    color: theme.text,
    textAlign: "center",
    marginBottom: 4,
  },
  docSubtitle: {
    fontSize: 16,
    fontWeight: "700",
    color: theme.text,
    textAlign: "center",
  },
  docHeading: {
    fontSize: 16,
    fontWeight: "700",
    color: theme.text,
    marginTop: 12,
  },
  docParagraph: { fontSize: 14, color: theme.text, lineHeight: 20 },
  docBullet: { fontSize: 14, color: theme.text, lineHeight: 20, paddingLeft: 8 },
  rule: {
    height: 1,
    backgroundColor: theme.border,
    marginVertical: 8,
  },
  fieldLabel: {
    fontSize: 14,
    fontWeight: "700",
    color: theme.text,
    marginTop: 12,
  },
  input: {
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: theme.text,
    backgroundColor: theme.white,
  },
  dateHint: { fontSize: 13, color: theme.textMuted },
  checkboxRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
    marginTop: 12,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 4,
    borderWidth: 2,
    borderColor: theme.green,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
  },
  checkboxChecked: { backgroundColor: theme.green },
  checkmark: { color: theme.white, fontSize: 14, fontWeight: "800" },
  checkboxLabel: { flex: 1, fontSize: 14, color: theme.text, lineHeight: 20 },
  error: { color: theme.red, fontSize: 13, textAlign: "center" },
});
