import type { HTMLAttributes } from "react";

export function Card({ className = "", children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`} {...props}>
      {children}
    </div>
  );
}

export function CardHeader({ className = "", children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`border-b border-slate-100 px-5 py-4 ${className}`} {...props}>
      {children}
    </div>
  );
}

export function CardBody({ className = "", children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`px-5 py-4 ${className}`} {...props}>
      {children}
    </div>
  );
}
