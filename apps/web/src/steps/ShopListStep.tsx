import { useState } from "react";
import type { BudgetSuggestion, GroceryLineItem, ResolvedGroceryList } from "../types";
import { computeAddableTotal, computeOfflineTotal, exportCsvUrl, exportMarkdownUrl } from "../api/client";
import { Button } from "../components/ui/Button";
import { Card, CardBody, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";

interface Props {
  list: ResolvedGroceryList;
  suggestions: BudgetSuggestion[];
  onApprove: () => void;
  onBack?: () => void;
  loading: boolean;
}

function isAddable(item: GroceryLineItem) {
  return item.sku !== "OFFLINE" && item.in_stock && !item.cart_blocked;
}

export function ShopListStep({ list, suggestions, onApprove, onBack, loading }: Props) {
  const [tab, setTab] = useState<"addable" | "blocked" | "manual">("addable");
  const addable = list.items.filter(isAddable);
  const blocked = list.items.filter((i) => i.cart_blocked);
  const manual = list.items.filter((i) => i.sku === "OFFLINE");
  const addableTotal = computeAddableTotal(list);
  const offlineTotal = computeOfflineTotal(list);
  const pct = Math.min(100, (list.total / list.budget_nzd) * 100);

  const rows =
    tab === "addable" ? addable : tab === "blocked" ? blocked : manual;
  const warningCount = list.items.filter(
    (i) => (i.warnings?.length ?? 0) > 0 && !i.cart_blocked
  ).length;

  return (
    <div className="space-y-4">
      <Card>
        <CardBody>
          <div className="flex flex-wrap gap-4 text-sm text-slate-700 mb-3">
            <span>
              Will add: <strong>${addableTotal.toFixed(2)}</strong>
            </span>
            <span>
              Manual: <strong>${offlineTotal.toFixed(2)}</strong>
            </span>
            <span>
              Total: <strong>${list.total.toFixed(2)}</strong> / ${list.budget_nzd.toFixed(2)}
            </span>
            {!list.within_budget && <Badge tone="danger">Over budget</Badge>}
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-slate-200">
            <div
              className={`h-full ${list.within_budget ? "bg-[var(--ww-green)]" : "bg-amber-500"}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        </CardBody>
      </Card>

      {manual.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <strong>{manual.length} item(s) not found</strong> — we tried multiple search terms on
          Woolworths but couldn&apos;t match these. Add them yourself on the Woolworths site.
        </div>
      )}

      {blocked.length > 0 && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900">
          <strong>{blocked.length} item(s) blocked</strong> — wrong product type or failed recipe
          / allergy checks. These will <strong>not</strong> go in your cart.
        </div>
      )}

      {warningCount > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <strong>{warningCount} item(s)</strong> have label warnings (e.g. may contain traces of
          gluten). Review before approving.
        </div>
      )}

      {suggestions.length > 0 && (
        <Card>
          <CardHeader>
            <h3 className="font-semibold">Budget swap suggestions</h3>
          </CardHeader>
          <CardBody className="space-y-2 text-sm">
            {suggestions.slice(0, 5).map((s, i) => (
              <p key={i} className="text-slate-700">
                <strong>{s.ingredient}</strong> — save ${s.savings.toFixed(2)}: {s.message}
              </p>
            ))}
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setTab("addable")}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                tab === "addable" ? "bg-green-100 text-green-900" : "text-slate-600"
              }`}
            >
              Will add ({addable.length})
            </button>
            <button
              type="button"
              onClick={() => setTab("blocked")}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                tab === "blocked" ? "bg-red-100 text-red-900" : "text-slate-600"
              }`}
            >
              Blocked ({blocked.length})
            </button>
            <button
              type="button"
              onClick={() => setTab("manual")}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                tab === "manual" ? "bg-amber-100 text-amber-900" : "text-slate-600"
              }`}
            >
              Manual ({manual.length})
            </button>
          </div>
          <div className="flex gap-2">
            <a href={exportCsvUrl()} className="text-sm text-[var(--ww-green)] underline">
              Export CSV
            </a>
            <a href={exportMarkdownUrl()} className="text-sm text-[var(--ww-green)] underline">
              Export MD
            </a>
          </div>
        </CardHeader>
        <CardBody className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="p-3 text-left">Ingredient</th>
                <th className="p-3 text-left">Product</th>
                <th className="p-3 text-right">Qty</th>
                <th className="p-3 text-right">Price</th>
                <th className="p-3" />
              </tr>
            </thead>
            <tbody>
              {rows.map((item, i) => (
                <tr key={i} className="border-t border-slate-100">
                  <td className="p-3">
                    {item.ingredient}
                    {item.is_mandatory && (
                      <Badge tone="mandatory" className="ml-2">
                        mandatory
                      </Badge>
                    )}
                    {item.cart_blocked && (
                      <Badge tone="danger" className="ml-2">
                        blocked
                      </Badge>
                    )}
                  </td>
                  <td className="p-3 text-slate-700">
                    {item.product_name}
                    {item.block_reason && (
                      <p className="mt-1 text-xs text-red-800">{item.block_reason}</p>
                    )}
                    {(item.warnings?.length ?? 0) > 0 && (
                      <p className="mt-1 text-xs text-amber-800">{item.warnings!.join(" ")}</p>
                    )}
                  </td>
                  <td className="p-3 text-right">
                    {item.quantity} {item.unit}
                  </td>
                  <td className="p-3 text-right font-medium">${item.line_total.toFixed(2)}</td>
                  <td className="p-3 text-right">
                    {item.product_url && (
                      <a
                        href={item.product_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[var(--ww-green)]"
                      >
                        View ↗
                      </a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardBody>
      </Card>

      <div className="flex justify-between">
        {onBack ? (
          <Button variant="secondary" onClick={onBack}>
            ← Back to meal plan
          </Button>
        ) : (
          <span />
        )}
        <Button onClick={onApprove} disabled={loading}>
          Approve &amp; continue →
        </Button>
      </div>
    </div>
  );
}
