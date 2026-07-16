import type { HTMLAttributes } from "react";

const styles = {
  default: "bg-slate-100 text-slate-700",
  success: "bg-green-100 text-green-800",
  warning: "bg-amber-100 text-amber-900",
  danger: "bg-red-100 text-red-800",
  mandatory: "bg-purple-100 text-purple-800",
};

export function Badge({
  tone = "default",
  className = "",
  children,
}: HTMLAttributes<HTMLSpanElement> & { tone?: keyof typeof styles }) {
  return (
    <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[tone]} ${className}`}>
      {children}
    </span>
  );
}
