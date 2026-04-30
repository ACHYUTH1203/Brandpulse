import { cn } from "@/lib/utils";
import type { Severity } from "@/lib/api";

const STYLES: Record<Severity, string> = {
  high: "bg-red-50 text-red-700 ring-red-200",
  medium: "bg-amber-50 text-amber-700 ring-amber-200",
  low: "bg-emerald-50 text-emerald-700 ring-emerald-200",
};

export function SeverityBadge({
  severity,
  className,
}: {
  severity: Severity;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset uppercase tracking-wide",
        STYLES[severity],
        className,
      )}
    >
      {severity}
    </span>
  );
}
