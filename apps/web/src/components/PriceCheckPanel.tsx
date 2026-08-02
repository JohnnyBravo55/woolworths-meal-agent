import { useEffect, useMemo, useState } from "react";
import type { PriceCheckResult, StoreChain, StoreRef } from "@meal-agent/app-core";
import { searchStores, runPriceCheck } from "../api/client";
import { Button } from "./ui/Button";
import { Card, CardBody, CardHeader } from "./ui/Card";

const CHAINS: { id: StoreChain; label: string }[] = [
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
        const res = await searchStores({
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
      if (prev.some((s) => s.id === store.id)) {
        return prev.filter((s) => s.id !== store.id);
      }
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
      const res = await runPriceCheck({
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
      <CardHeader className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-semibold">Compare store prices</h3>
          <p className="text-sm text-slate-600">
            Login-free price check across local branches. Unmatched items keep your list estimate.
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Hide" : "Run price check"}
        </Button>
      </CardHeader>

      {open && (
        <CardBody className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setChain("")}
              className={`rounded-lg px-3 py-1.5 text-sm ${
                chain === "" ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-700"
              }`}
            >
              All chains
            </button>
            {CHAINS.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setChain(c.id)}
                className={`rounded-lg px-3 py-1.5 text-sm ${
                  chain === c.id ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-700"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>

          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search suburb or store name…"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />

          {selected.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {selected.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => toggleStore(s)}
                  className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-900"
                >
                  {s.name} ×
                </button>
              ))}
            </div>
          )}

          <div className="max-h-48 overflow-y-auto rounded-lg border border-slate-200">
            {loadingStores && <p className="p-3 text-sm text-slate-500">Loading stores…</p>}
            {!loadingStores && stores.length === 0 && (
              <p className="p-3 text-sm text-slate-500">No stores match.</p>
            )}
            {stores.map((store) => {
              const on = selectedIds.has(store.id);
              return (
                <button
                  key={store.id}
                  type="button"
                  onClick={() => toggleStore(store)}
                  className={`flex w-full items-start justify-between gap-2 border-b border-slate-100 px-3 py-2 text-left text-sm last:border-0 ${
                    on ? "bg-green-50" : "hover:bg-slate-50"
                  }`}
                >
                  <span>
                    <span className="font-medium">{store.name}</span>
                    <span className="mt-0.5 block text-xs text-slate-500">
                      {store.address || store.suburb || store.chain}
                    </span>
                  </span>
                  <span className="text-xs font-semibold text-slate-600">{on ? "Selected" : "Select"}</span>
                </button>
              );
            })}
          </div>

          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={includeSplit}
              onChange={(e) => setIncludeSplit(e.target.checked)}
            />
            Suggest split shop (cheapest store per item)
          </label>

          <Button type="button" onClick={onRun} disabled={running || selected.length === 0}>
            {running ? "Comparing…" : `Compare ${selected.length || ""} store${selected.length === 1 ? "" : "s"}`}
          </Button>

          {error && <p className="text-sm text-red-700">{error}</p>}

          {result && (
            <div className="space-y-3">
              {result.skipped && result.skipped.length > 0 ? (
                <div className="space-y-1 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                  {result.skipped.map((s) => (
                    <p key={s.store.id}>
                      Skipped {s.store.name}: {s.reason}
                    </p>
                  ))}
                </div>
              ) : null}
              {result.baskets.map((basket) => {
                const key = basket.store.id;
                const isOpen = !!expanded[key];
                return (
                  <div key={key} className="rounded-lg border border-slate-200">
                    <button
                      type="button"
                      className="flex w-full items-center justify-between gap-2 px-3 py-3 text-left"
                      onClick={() => setExpanded((e) => ({ ...e, [key]: !isOpen }))}
                    >
                      <span>
                        <span className="font-semibold">{basket.store.name}</span>
                        <span className="mt-0.5 block text-xs text-slate-500">
                          {basket.live_count} live · {basket.estimate_count} estimate
                          {basket.warning ? ` · ${basket.warning}` : ""}
                        </span>
                      </span>
                      <span className="font-semibold">${basket.total.toFixed(2)}</span>
                    </button>
                    {isOpen && (
                      <ul className="border-t border-slate-100 px-3 py-2 text-sm">
                        {basket.lines.map((line, i) => (
                          <li
                            key={`${line.ingredient}-${i}`}
                            className="flex justify-between gap-3 border-b border-slate-50 py-2 last:border-0"
                          >
                            <span>
                              <span className="font-medium">{line.ingredient}</span>
                              <span className="mt-0.5 block text-xs text-slate-500">
                                {line.product_name || "—"}
                                {line.note ? ` · ${line.note}` : ""}
                                {line.price_source === "estimate" ? " · estimate" : ""}
                              </span>
                            </span>
                            <span>${line.line_total.toFixed(2)}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}

              {result.split && (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50">
                  <button
                    type="button"
                    className="flex w-full items-center justify-between gap-2 px-3 py-3 text-left"
                    onClick={() =>
                      setExpanded((e) => ({ ...e, split: !e.split }))
                    }
                  >
                    <span>
                      <span className="font-semibold text-emerald-950">Suggested split shop</span>
                      <span className="mt-0.5 block text-xs text-emerald-900">
                        Save ${result.split.savings_vs_cheapest_single_store.toFixed(2)} vs cheapest
                        single store
                        {result.split.note ? ` · ${result.split.note}` : ""}
                      </span>
                    </span>
                    <span className="font-semibold text-emerald-950">
                      ${result.split.total.toFixed(2)}
                    </span>
                  </button>
                  {expanded.split && (
                    <ul className="border-t border-emerald-100 px-3 py-2 text-sm">
                      {result.split.assignments.map((a, i) => (
                        <li
                          key={`${a.ingredient}-${i}`}
                          className="flex justify-between gap-3 border-b border-emerald-100/60 py-2 last:border-0"
                        >
                          <span>
                            <span className="font-medium">{a.ingredient}</span>
                            <span className="mt-0.5 block text-xs text-emerald-900">
                              {a.store_name}
                              {a.line.note ? ` · ${a.line.note}` : ""}
                              {a.line.price_source === "estimate" ? " · estimate" : ""}
                            </span>
                          </span>
                          <span>${a.line.line_total.toFixed(2)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}
        </CardBody>
      )}
    </Card>
  );
}
