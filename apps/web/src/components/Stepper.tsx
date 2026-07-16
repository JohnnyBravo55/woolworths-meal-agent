import { STEPS } from "../types";

interface Props {
  current: number;
}

export function Stepper({ current }: Props) {
  return (
    <div className="hidden md:flex items-center gap-2">
      {STEPS.map((step, idx) => (
        <div key={step.key} className="flex items-center gap-2">
          <div
            className={`flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold ${
              idx <= current
                ? "bg-[var(--ww-green)] text-white"
                : "bg-slate-200 text-slate-500"
            }`}
          >
            {idx + 1}
          </div>
          <span className={`text-sm ${idx <= current ? "text-slate-900 font-medium" : "text-slate-400"}`}>
            {step.label}
          </span>
          {idx < STEPS.length - 1 && (
            <div className={`mx-1 h-px w-8 ${idx < current ? "bg-[var(--ww-green)]" : "bg-slate-200"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

export function MobileStepper({ current }: Props) {
  const step = STEPS[current];
  return (
    <p className="md:hidden text-sm text-slate-600">
      Step {current + 1} of {STEPS.length} · <span className="font-medium text-slate-900">{step.label}</span>
    </p>
  );
}
