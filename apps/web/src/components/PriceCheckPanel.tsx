import { useEffect, useMemo, useState } from "react";
import type { PriceCheckLine, PriceCheckResult, StoreChain, StoreRef } from "@meal-agent/app-core";
import {
  lineBoughtKey,
  lineCopyText,
  lineProductUrl,
  lineSearchUrl,
  storeShopUrl,
} from "@meal-agent/app-core";
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

function openUrl(url: string) {
  if (!url) return;
  window.open(url, "_blank", "noopener,noreferrer");
}

async function copyLine(line: PriceCheckLine) {
  const text = lineCopyText(line);
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // Ignore clipboard failures (permissions).
  }
}

function LineActions({
  store,
  line,
  bought,
  onToggleBought,
}: {
  store: StoreRef;
  line: PriceCheckLine;
  bought: boolean;
  onToggleBought: () => void;
}) {
  const productUrl = lineProductUrl(store, line);
  const searchUrl = lineSearchUrl(store, line);
  return (
    <div className="mt-1.5 flex flex-wrap gap-1.5">
      {productUrl ? (
        <button
          type="button"
          className="rounded border border-slate-300 bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
          onClick={() => openUrl(productUrl)}
        >
          Open
        </button>
      ) : null}
      {searchUrl ? (
        <button
          type="button"
          className="rounded border border-slate-300 bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
          onClick={() => openUrl(searchUrl)}
        >
          Search
        </button>
      ) : null}
      <button
        type="button"
        className="rounded border border-slate-300 bg-white px-2 py-0.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50"
        onClick={() => copyLine(line)}
      >
        Copy
      </button>
      <button
        type="button"
        className={`rounded border px-2 py-0.5 text-[11px] font-semibold ${
          bought
            ? "border-green-800 bg-green-800 text-white"
            : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
        }`}
        onClick={onToggleBought}
      >
        {bought ? "Bought" : "Mark"}
      </button>
    </div>
  );
}

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
  const [bought, setBought] = useState<Record<string, boolean>>({});

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
      setBought({});
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
    }
  };

  const toggleBought = (key: string) => {
    setBought((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <Card>
      <CardHeader className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-semibold">Compare & shop stores</h3>
          <p className="text-sm text-slate-600">
            Login-free prices, then Open / Search on the store site. You add items yourself — no silent
            cart for New World, Pak&apos;nSave, or FreshChoice.
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
                const shopUrl = storeShopUrl(basket.store);
                return (
                  <div key={key} className="rounded-lg border border-slate-200">
                    <div className="flex w-full items-center justify-between gap-2 px-3 py-3 text-left">
                      <span>
                        <span className="font-semibold">{basket.store.name}</span>
                        <span className="mt-0.5 block text-xs text-slate-500">
                          {basket.live_count} live · {basket.estimate_count} estimate
                          {basket.warning ? ` · ${basket.warning}` : ""}
                        </span>
                      </span>
                      <span className="font-semibold">${basket.total.toFixed(2)}</span>
                    </div>
                    <div className="flex items-center justify-between gap-3 px-3 pb-2">
                      <button
                        type="button"
                        className={`rounded-lg border px-3 py-2 text-sm font-semibold ${
                          isOpen
                            ? "border-[var(--ww-green)] bg-emerald-50 text-slate-900"
                            : "border-slate-300 bg-slate-50 text-slate-900"
                        }`}
                        aria-expanded={isOpen}
                        onClick={() => setExpanded((e) => ({ ...e, [key]: !isOpen }))}
                      >
                        Item list {isOpen ? "▲" : "▼"}
                      </button>
                      {shopUrl ? (
                        <Button
                          type="button"
                          variant="secondary"
                          className="ml-auto"
                          onClick={() => openUrl(shopUrl)}
                        >
                          Shop at {basket.store.name}
                        </Button>
                      ) : null}
                    </div>
                    {isOpen && (
                      <ul className="border-t border-slate-100 px-3 py-2 text-sm">
                        {basket.lines.map((line, i) => {
                          const bKey = lineBoughtKey(key, line.ingredient, i);
                          const isBought = !!bought[bKey];
                          return (
                            <li
                              key={`${line.ingredient}-${i}`}
                              className={`flex justify-between gap-3 border-b border-slate-50 py-2 last:border-0 ${
                                isBought ? "opacity-70" : ""
                              }`}
                            >
                              <span>
                                <span
                                  className={`font-medium ${isBought ? "text-slate-500 line-through" : ""}`}
                                >
                                  {line.ingredient}
                                </span>
                                <span className="mt-0.5 block text-xs text-slate-500">
                                  {line.product_name || "—"}
                                  {line.note ? ` · ${line.note}` : ""}
                                  {line.price_source === "estimate" ? " · estimate" : ""}
                                </span>
                                <LineActions
                                  store={basket.store}
                                  line={line}
                                  bought={isBought}
                                  onToggleBought={() => toggleBought(bKey)}
                                />
                              </span>
                              <span>${line.line_total.toFixed(2)}</span>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </div>
                );
              })}

              {result.split && (
                <div className="rounded-lg border border-emerald-200 bg-emerald-50">
                  <div className="flex w-full items-center justify-between gap-2 px-3 py-3 text-left">
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
                  </div>
                  <div className="flex items-center px-3 pb-2">
                    <button
                      type="button"
                      className={`rounded-lg border px-3 py-2 text-sm font-semibold ${
                        expanded.split
                          ? "border-emerald-600 bg-white text-emerald-950"
                          : "border-emerald-300 bg-white/80 text-emerald-950"
                      }`}
                      aria-expanded={!!expanded.split}
                      onClick={() =>
                        setExpanded((e) => ({ ...e, split: !e.split }))
                      }
                    >
                      Item list {expanded.split ? "▲" : "▼"}
                    </button>
                  </div>
                  {expanded.split && (
                    <ul className="border-t border-emerald-100 px-3 py-2 text-sm">
                      {result.split.assignments.map((a, i) => {
                        const bKey = lineBoughtKey(a.store_id, a.ingredient, i);
                        const isBought = !!bought[bKey];
                        const store: StoreRef = {
                          id: a.store_id,
                          chain: a.chain,
                          name: a.store_name,
                        };
                        return (
                          <li
                            key={`${a.ingredient}-${i}`}
                            className={`flex justify-between gap-3 border-b border-emerald-100/60 py-2 last:border-0 ${
                              isBought ? "opacity-70" : ""
                            }`}
                          >
                            <span>
                              <span
                                className={`font-medium ${isBought ? "text-slate-500 line-through" : ""}`}
                              >
                                {a.ingredient}
                              </span>
                              <span className="mt-0.5 block text-xs text-emerald-900">
                                {a.store_name}
                                {a.line.note ? ` · ${a.line.note}` : ""}
                                {a.line.price_source === "estimate" ? " · estimate" : ""}
                              </span>
                              <LineActions
                                store={store}
                                line={a.line}
                                bought={isBought}
                                onToggleBought={() => toggleBought(bKey)}
                              />
                            </span>
                            <span>${a.line.line_total.toFixed(2)}</span>
                          </li>
                        );
                      })}
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
