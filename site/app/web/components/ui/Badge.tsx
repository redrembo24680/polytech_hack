import { cn } from "@/lib/cn";

export type BadgeColor = "gray" | "green" | "red" | "amber" | "blue" | "accent";

const COLORS: Record<BadgeColor, string> = {
  gray: "bg-slate-100 text-slate-700 ring-slate-200",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  red: "bg-red-50 text-red-700 ring-red-200",
  amber: "bg-amber-50 text-amber-800 ring-amber-200",
  blue: "bg-sky-50 text-sky-700 ring-sky-200",
  accent: "bg-accent-50 text-accent-700 ring-accent-200",
};

export interface BadgeProps {
  color?: BadgeColor;
  className?: string;
  children: React.ReactNode;
}

export function Badge({ color = "gray", className, children }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        COLORS[color],
        className,
      )}
    >
      {children}
    </span>
  );
}
