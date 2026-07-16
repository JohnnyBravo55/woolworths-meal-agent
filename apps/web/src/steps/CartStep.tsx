import { useEffect, useState } from "react";
import type { CartResult, MealPlan } from "../types";
import { exportCsvUrl, getCartUrl } from "../api/client";
import { Button } from "../components/ui/Button";
import { Card, CardBody, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";

interface Props {
  result: CartResult | null;
  exportOnly: boolean;
  onAdd: (opts: { allow_over_budget?: boolean }) => void;
  onRetry: () => void;
  onExportOnly: () => void;
  loading: boolean;
  plan: MealPlan | null;
  onDownloadRecipes?: () => void;
  adding?: boolean;
  cartProgress?: {
    done: number;
    total: number;
    ingredient: string;
    status: string;
    log: { ingredient: string; status: string; message: string }[];
  };
}

export function CartStep({
  result,
  exportOnly,
  onAdd,
  onRetry,
  onExportOnly,
  loading,
  plan,
  onDownloadRecipes,
  adding,
  cartProgress,
}: Props) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [showAllRecipes, setShowAllRecipes] = useState(false);
  const [cartUrls, setCartUrls] = useState<{ url: string; url_alt?: string } | null>(null);

  useEffect(() => {
    getCartUrl().then(setCartUrls).catch(() => {});
  }, []);

  const openCart = async () => {
    const { url } = await getCartUrl();
    window.open(url, "_blank");
  };

  if (adding && cartProgress && !result) {
    const pct = cartProgress.total
      ? Math.min(100, (cartProgress.done / cartProgress.total) * 100)
      : 0;
    return (
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">Adding to Woolworths cart…</h2>
        </CardHeader>
        <CardBody className="space-y-4">
          <div className="flex justify-between text-sm text-slate-600">
            <span>
              {cartProgress.done}/{cartProgress.total || "…"} items
              {cartProgress.ingredient ? ` · ${cartProgress.ingredient}` : ""}
            </span>
            <span className="capitalize">{cartProgress.status.replace("_", " ")}</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full bg-[var(--ww-green)] transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          {cartProgress.log.length > 0 && (
            <ul className="max-h-48 overflow-y-auto text-sm text-slate-700 space-y-1">
              {[...cartProgress.log].reverse().slice(0, 8).map((entry, i) => (
                <li key={i}>
                  {entry.status === "success" && "✓ "}
                  {entry.status === "failed" && "✗ "}
                  {entry.status === "adding" && "… "}
                  {entry.ingredient}
                  {entry.message ? ` — ${entry.message}` : ""}
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    );
  }

  if (!result && !confirmOpen) {
    return (
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">Add to Woolworths cart</h2>
        </CardHeader>
        <CardBody className="space-y-4">
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            This adds items to your Woolworths trolley only. It will <strong>never</strong> complete
            checkout. You review and pay on woolworths.co.nz.
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setConfirmOpen(true)} disabled={loading}>
              Add to Woolworths cart
            </Button>
            <Button variant="secondary" onClick={onExportOnly} disabled={loading}>
              Export list only
            </Button>
          </div>
        </CardBody>
      </Card>
    );
  }

  if (confirmOpen && !result) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
          <h3 className="font-semibold">Confirm cart add</h3>
          <p className="mt-2 text-sm text-slate-600">
            Items will be added to your Woolworths account trolley. You must be logged into the same
            account in your browser.
          </p>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setConfirmOpen(false)} disabled={adding}>
              Cancel
            </Button>
            <Button
              disabled={adding}
              onClick={() => {
                setConfirmOpen(false);
                onAdd({});
              }}
            >
              {adding ? "Adding…" : "Yes, add items"}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!result) return null;

  const incomplete =
    result.cart_subtotal != null &&
    result.added_total > 0 &&
    result.cart_subtotal + 5 < result.added_total;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold">
            {exportOnly ? "Shopping list exported" : "Cart result"}
          </h2>
        </CardHeader>
        <CardBody className="space-y-3">
          {!exportOnly && (
            <>
              <p className="text-slate-700">
                <strong>{result.success_count}</strong> products added (${result.added_total.toFixed(2)})
                {result.cart_line_count != null && result.cart_line_count !== result.success_count && (
                  <> · {result.cart_line_count} lines in Woolworths trolley</>
                )}
                · {result.failure_count} failed · {result.skipped_offline} need manual search
              </p>
              {(result.duplicate_lines_merged ?? 0) > 0 && (
                <p className="text-sm text-slate-600">
                  {result.duplicate_lines_merged} shop-list rows shared the same Woolworths product
                  and were merged before adding.
                </p>
              )}
              {result.cart_subtotal != null && (
                <p className="text-slate-700">
                  Woolworths trolley subtotal: <strong>${result.cart_subtotal.toFixed(2)}</strong>
                </p>
              )}
            </>
          )}
          {incomplete && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              Trolley total is lower than expected — session may have expired partway. Try Connect
              Woolworths and Retry missing.
            </div>
          )}
          {result.errors.length > 0 && (
            <ul className="text-sm text-amber-800 space-y-1">
              {result.errors.map((e, i) => (
                <li key={i}>• {e}</li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap gap-2 pt-2">
            {!exportOnly && result.success_count > 0 && (
              <>
                <Button onClick={openCart}>Open Woolworths trolley</Button>
                {cartUrls?.url_alt && (
                  <a href={cartUrls.url_alt} target="_blank" rel="noreferrer">
                    <Button variant="secondary">Open Woolworths shop</Button>
                  </a>
                )}
              </>
            )}
            {!exportOnly && result.success_count > 0 && (
              <p className="w-full text-xs text-slate-500">
                Opens woolworths.co.nz/reviewtrolley — sign in with the same account you
                connected in this app. If prompted to log in, your trolley loads after that.
              </p>
            )}
            {!exportOnly && (
              <Button variant="secondary" onClick={onRetry} disabled={loading}>
                Retry missing items
              </Button>
            )}
            <a href={exportCsvUrl()}>
              <Button variant="secondary">Download CSV</Button>
            </a>
            {onDownloadRecipes && (
              <Button variant="secondary" onClick={onDownloadRecipes}>
                Download recipes
              </Button>
            )}
            {plan && (
              <Button variant="ghost" onClick={() => setShowAllRecipes(!showAllRecipes)}>
                {showAllRecipes ? "Hide recipes" : "View all recipes"}
              </Button>
            )}
          </div>
        </CardBody>
      </Card>

      {showAllRecipes && plan && (
        <div className="space-y-3">
          {plan.meals.map((meal, idx) => (
            <Card key={idx}>
              <CardHeader>
                <Badge>{meal.slot}</Badge> {meal.day_label}: {meal.name}
              </CardHeader>
              <CardBody className="text-sm">
                <ol className="list-decimal pl-5 space-y-1">
                  {meal.steps.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
