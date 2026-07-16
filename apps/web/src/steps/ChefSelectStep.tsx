import type { ChefPersona } from "../types";
import { Button } from "../components/ui/Button";
import { Card, CardBody, CardHeader } from "../components/ui/Card";
import { Badge } from "../components/ui/Badge";

interface Props {
  chefs: ChefPersona[];
  premiumUnlocked: boolean;
  selectedChefId: string;
  hasExistingPlan?: boolean;
  onSelect: (chefId: string) => void;
  onBack?: () => void;
  onGenerate: () => void;
  loading: boolean;
  planProgress?: { done: number; total: number; message: string };
}

function ChefAvatar({
  chef,
  selected,
  locked,
  onClick,
}: {
  chef: ChefPersona;
  selected: boolean;
  locked: boolean;
  onClick: () => void;
}) {
  const isPremium = chef.tier === "premium";

  return (
    <button
      type="button"
      disabled={locked}
      onClick={onClick}
      className={`group flex flex-col items-center text-center transition-opacity ${
        locked ? "cursor-not-allowed opacity-60" : "cursor-pointer"
      }`}
    >
      <div
        className={`relative rounded-full p-1 ${
          isPremium ? "bg-gradient-to-br from-amber-300 via-yellow-400 to-amber-500 shadow-md" : ""
        } ${selected ? "ring-4 ring-[var(--ww-green)] ring-offset-2" : ""}`}
      >
        {chef.avatar_image ? (
          <img
            src={chef.avatar_image}
            alt={`${chef.name}, ${chef.title}`}
            className="h-24 w-24 rounded-full object-cover shadow-md sm:h-28 sm:w-28"
          />
        ) : (
          <div
            className="flex h-24 w-24 items-center justify-center rounded-full text-2xl font-bold text-white shadow-md sm:h-28 sm:w-28 sm:text-3xl"
            style={{
              background: `linear-gradient(135deg, ${chef.avatar_from}, ${chef.avatar_to})`,
            }}
          >
            {chef.avatar_initials}
          </div>
        )}
        {locked && (
          <span className="absolute inset-0 flex items-center justify-center rounded-full bg-black/40 text-2xl">
            🔒
          </span>
        )}
      </div>
      <p className="mt-3 font-semibold text-slate-900">{chef.name}</p>
      <p className="text-sm font-medium text-[var(--ww-green)]">{chef.title}</p>
      <p className="mt-1 max-w-[11rem] text-xs text-slate-500">{chef.tagline}</p>
      <p className="mt-1 text-xs text-slate-400">{chef.region}</p>
    </button>
  );
}

export function ChefSelectStep({
  chefs,
  premiumUnlocked,
  selectedChefId,
  hasExistingPlan = false,
  onSelect,
  onBack,
  onGenerate,
  loading,
  planProgress,
}: Props) {
  const basic = chefs.filter((c) => c.tier === "basic");
  const premium = chefs.filter((c) => c.tier === "premium");
  const selected = chefs.find((c) => c.id === selectedChefId);
  const progressPct =
    planProgress && planProgress.total
      ? Math.min(100, (planProgress.done / planProgress.total) * 100)
      : loading
        ? 15
        : 0;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-slate-900">Choose your chef</h2>
          <p className="text-sm text-slate-600 mt-1">
            All chefs use AI when OpenAI is configured. Basic is free and generalist; premium
            chefs specialise in a region or global fine dining.
          </p>
        </CardHeader>
      </Card>

      {loading && planProgress && (
        <Card>
          <CardBody>
            <p className="mb-2 text-sm text-slate-600">
              {planProgress.message || "Generating meal plan…"}
              {planProgress.total > 0 && (
                <>
                  {" "}
                  ({planProgress.done}/{planProgress.total})
                </>
              )}
            </p>
            <div className="h-2 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full bg-[var(--ww-green)] transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
          </CardBody>
        </Card>
      )}

      {!premiumUnlocked && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          Premium chefs are for subscribers.{" "}
          <strong>Sign in with a subscribed account</strong> to unlock Moana, Alex, Kenji, Elena,
          and Amara — or continue with Sam on Basic.
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold uppercase tracking-wide text-slate-500">Basic</h3>
              <Badge>Free</Badge>
            </div>
          </CardHeader>
          <CardBody className="flex justify-center py-8">
            {basic.map((chef) => (
              <ChefAvatar
                key={chef.id}
                chef={chef}
                selected={selectedChefId === chef.id}
                locked={false}
                onClick={() => onSelect(chef.id)}
              />
            ))}
          </CardBody>
        </Card>

        <Card>
          <CardHeader className="border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold uppercase tracking-wide text-amber-700">Premium</h3>
              <Badge tone="mandatory">Subscriber</Badge>
            </div>
          </CardHeader>
          <CardBody className="py-8">
            <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 sm:gap-6 lg:grid-cols-2 xl:grid-cols-3">
              {premium.map((chef) => (
                <ChefAvatar
                  key={chef.id}
                  chef={chef}
                  selected={selectedChefId === chef.id}
                  locked={!premiumUnlocked}
                  onClick={() => premiumUnlocked && onSelect(chef.id)}
                />
              ))}
            </div>
          </CardBody>
        </Card>
      </div>

      {selected && (
        <p className="text-center text-sm text-slate-600">
          Selected: <strong>{selected.name}</strong> — {selected.title}
        </p>
      )}

      <div className="flex justify-between">
        {onBack ? (
          <Button variant="secondary" onClick={onBack} disabled={loading}>
            ← Back to preferences
          </Button>
        ) : (
          <span />
        )}
        <Button onClick={onGenerate} disabled={loading || !selectedChefId}>
          {loading
            ? "Generating meal plan…"
            : hasExistingPlan
              ? "Continue to meal plan →"
              : "Generate meal plan →"}
        </Button>
      </div>
    </div>
  );
}
