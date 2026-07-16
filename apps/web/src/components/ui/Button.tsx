import type { ButtonHTMLAttributes } from "react";
import { forwardRef } from "react";

const variants = {
  primary: "bg-[var(--ww-green)] text-white hover:bg-[var(--ww-green-dark)]",
  secondary: "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50",
  ghost: "bg-transparent text-slate-600 hover:bg-slate-100",
  danger: "bg-red-600 text-white hover:bg-red-700",
};

const sizes = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-3 text-base",
};

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
}

export const Button = forwardRef<HTMLButtonElement, Props>(
  ({ variant = "primary", size = "md", className = "", disabled, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled}
      className={`inline-flex items-center justify-center rounded-lg font-medium transition disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    />
  ),
);
Button.displayName = "Button";
