import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import type { PriceCheckResult, StoreChain, StoreRef } from "@meal-agent/app-core";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, H2 } from "@/components/ui/Card";
import { theme } from "@/constants/theme";
import { api } from "@/lib/api";

const CHAINS: { id: StoreChain | ""; label: string }[] = [
  { id: "", label: "All" },
  { id: "woolworths", label: "Woolworths" },
  { id: "paknsave", label: "Pak'nSave" },
  { id: "new_world", label: "New World" },
  { id: "freshchoice", label: "FreshChoice" },
];

const MAX_STORES = 4;

export function PriceCheckPanel() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [chain, setChain] = useState<StoreChain | "">("");
  const [stores, setStores] = useState<StoreRef[]>([]);
  const [selected, setSelected] = useState<StoreRef[]>([]);
  const [includeSplit, setIncludeSplit] = useState(true);
  const [loadingStores, setLoadingStores] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<PriceCheckResult | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const selectedIds = useMemo(() => new Set(selected.map((s) => s.id)), [selected]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    (async () => {
      setLoadingStores(true);
      setError("");
      try {
        const res = await api.searchStores({
          q: query,
          chain: chain || undefined,
          limit: 30,
        });
        if (!cancelled) setStores(res.stores);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoadingStores(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, query, chain]);

  const toggleStore = (store: StoreRef) => {
    setSelected((prev) => {
      if (prev.some((s) => s.id === store.id)) return prev.filter((s) => s.id !== store.id);
      if (prev.length >= MAX_STORES) return prev;
      return [...prev, store];
    });
  };

  const onRun = async () => {
    if (selected.length === 0) {
      setError("Pick at least one local store.");
      return;
    }
    setRunning(true);
    setError("");
    try {
      const res = await api.runPriceCheck({
        store_ids: selected.map((s) => s.id),
        include_split: includeSplit,
      });
      setResult(res);
      setExpanded({});
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <H2>Compare store prices</H2>
        <Text style={styles.sub}>
          Login-free check across local branches. Missing matches keep your list estimate.
        </Text>
        <Button
          title={open ? "Hide price check" : "Run price check"}
          variant="secondary"
          onPress={() => setOpen((v) => !v)}
        />
      </CardHeader>

      {open ? (
        <CardBody>
          <View style={styles.rowWrap}>
            {CHAINS.map((c) => (
              <Pressable
                key={c.label}
                onPress={() => setChain(c.id)}
                style={[styles.chip, chain === c.id && styles.chipOn]}
              >
                <Text style={[styles.chipText, chain === c.id && styles.chipTextOn]}>{c.label}</Text>
              </Pressable>
            ))}
          </View>

          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Search suburb or store…"
            style={styles.input}
            autoCapitalize="none"
            autoCorrect={false}
          />

          {selected.length > 0 ? (
            <View style={styles.rowWrap}>
              {selected.map((s) => (
                <Pressable key={s.id} onPress={() => toggleStore(s)} style={styles.selectedChip}>
                  <Text style={styles.selectedChipText}>{s.name} ×</Text>
                </Pressable>
              ))}
            </View>
          ) : null}

          <View style={styles.listBox}>
            {loadingStores ? <ActivityIndicator color={theme.green} /> : null}
            {!loadingStores && stores.length === 0 ? (
              <Text style={styles.muted}>No stores match.</Text>
            ) : null}
            {stores.slice(0, 12).map((store) => {
              const on = selectedIds.has(store.id);
              return (
                <Pressable
                  key={store.id}
                  onPress={() => toggleStore(store)}
                  style={[styles.storeRow, on && styles.storeRowOn]}
                >
                  <View style={{ flex: 1 }}>
                    <Text style={styles.storeName}>{store.name}</Text>
                    <Text style={styles.muted}>{store.address || store.suburb || store.chain}</Text>
                  </View>
                  <Text style={styles.muted}>{on ? "Selected" : "Select"}</Text>
                </Pressable>
              );
            })}
          </View>

          <Pressable
            onPress={() => setIncludeSplit((v) => !v)}
            style={styles.splitToggle}
          >
            <Text style={styles.storeName}>
              {includeSplit ? "☑" : "☐"} Suggest split shop
            </Text>
          </Pressable>

          <Button
            title={`Compare ${selected.length || ""} store${selected.length === 1 ? "" : "s"}`}
            onPress={onRun}
            loading={running}
            disabled={selected.length === 0}
          />

          {error ? <Text style={styles.error}>{error}</Text> : null}

          {result
            ? result.baskets.map((basket) => {
                const key = basket.store.id;
                const isOpen = !!expanded[key];
                return (
                  <View key={key} style={styles.resultCard}>
                    <Pressable
                      onPress={() => setExpanded((e) => ({ ...e, [key]: !isOpen }))}
                      style={styles.resultHeader}
                    >
                      <View style={{ flex: 1 }}>
                        <Text style={styles.storeName}>{basket.store.name}</Text>
                        <Text style={styles.muted}>
                          {basket.live_count} live · {basket.estimate_count} estimate
                        </Text>
                      </View>
                      <Text style={styles.total}>${basket.total.toFixed(2)}</Text>
                    </Pressable>
                    {isOpen
                      ? basket.lines.map((line, i) => (
                          <View key={`${line.ingredient}-${i}`} style={styles.lineRow}>
                            <View style={{ flex: 1 }}>
                              <Text style={styles.lineIng}>{line.ingredient}</Text>
                              <Text style={styles.muted}>
                                {line.product_name || "—"}
                                {line.note ? ` · ${line.note}` : ""}
                              </Text>
                            </View>
                            <Text>${line.line_total.toFixed(2)}</Text>
                          </View>
                        ))
                      : null}
                  </View>
                );
              })
            : null}

          {result?.split ? (
            <View style={[styles.resultCard, styles.splitCard]}>
              <Pressable
                onPress={() => setExpanded((e) => ({ ...e, split: !e.split }))}
                style={styles.resultHeader}
              >
                <View style={{ flex: 1 }}>
                  <Text style={styles.storeName}>Suggested split shop</Text>
                  <Text style={styles.muted}>
                    Save ${result.split.savings_vs_cheapest_single_store.toFixed(2)}
                    {result.split.note ? ` · ${result.split.note}` : ""}
                  </Text>
                </View>
                <Text style={styles.total}>${result.split.total.toFixed(2)}</Text>
              </Pressable>
              {expanded.split
                ? result.split.assignments.map((a, i) => (
                    <View key={`${a.ingredient}-${i}`} style={styles.lineRow}>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.lineIng}>{a.ingredient}</Text>
                        <Text style={styles.muted}>{a.store_name}</Text>
                      </View>
                      <Text>${a.line.line_total.toFixed(2)}</Text>
                    </View>
                  ))
                : null}
            </View>
          ) : null}
        </CardBody>
      ) : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  sub: { color: theme.textMuted, fontSize: 13, marginBottom: 8, marginTop: 4 },
  rowWrap: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 10 },
  chip: {
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: "#e2e8f0",
  },
  chipOn: { backgroundColor: "#0f172a" },
  chipText: { fontSize: 12, fontWeight: "600", color: "#334155" },
  chipTextOn: { color: "#fff" },
  input: {
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 10,
    fontSize: 14,
    color: theme.text,
  },
  selectedChip: {
    backgroundColor: "#dcfce7",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  selectedChipText: { color: "#14532d", fontSize: 12, fontWeight: "600" },
  listBox: {
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 10,
    maxHeight: 220,
    marginBottom: 10,
    overflow: "hidden",
  },
  storeRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: "#e2e8f0",
  },
  storeRowOn: { backgroundColor: "#f0fdf4" },
  storeName: { fontWeight: "700", color: theme.text, fontSize: 14 },
  muted: { color: theme.textMuted, fontSize: 12, marginTop: 2 },
  splitToggle: { marginBottom: 10 },
  error: { color: "#b91c1c", marginTop: 8, fontSize: 13 },
  resultCard: {
    marginTop: 12,
    borderWidth: 1,
    borderColor: "#e2e8f0",
    borderRadius: 10,
    overflow: "hidden",
  },
  splitCard: { borderColor: "#86efac", backgroundColor: "#f0fdf4" },
  resultHeader: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
  total: { fontWeight: "800", fontSize: 15, color: theme.text },
  lineRow: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: "#e2e8f0",
  },
  lineIng: { fontWeight: "600", color: theme.text, fontSize: 13 },
});
