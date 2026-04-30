import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { SeverityBadge } from "@/components/severity-badge";
import { formatCurrency } from "@/lib/utils";
import type { LeakListItem } from "@/lib/api";

const TYPE_LABEL: Record<string, string> = {
  zombie: "Zombie spend",
  creative_fatigue: "Creative fatigue",
  cpa_creep: "CPA creep",
  audience_saturation: "Audience saturation",
  budget_misallocation: "Budget misallocation",
};

export function LeakCard({ leak }: { leak: LeakListItem }) {
  return (
    <Link
      href={`/insights/${leak.leak_id}`}
      className="group flex flex-col rounded-xl border border-zinc-200 bg-white p-5 shadow-sm transition hover:shadow-md hover:-translate-y-0.5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium uppercase tracking-wide text-zinc-400">
            {TYPE_LABEL[leak.leak_type] ?? leak.leak_type}
          </span>
          <span className="text-2xl font-semibold tracking-tight text-zinc-900">
            {formatCurrency(leak.dollar_impact)}
          </span>
        </div>
        <SeverityBadge severity={leak.severity} />
      </div>

      {leak.title && (
        <p className="mt-4 text-sm font-semibold text-zinc-900 line-clamp-2">
          {leak.title}
        </p>
      )}
      {leak.summary && (
        <p className="mt-2 text-sm text-zinc-600 line-clamp-3">
          {leak.summary}
        </p>
      )}

      <div className="mt-4 flex items-center justify-between text-xs text-zinc-500">
        <span>
          {leak.campaign_name ?? "brand-level"}
          {leak.confidence != null && (
            <> · conf {(leak.confidence * 100).toFixed(0)}%</>
          )}
        </span>
        <span className="inline-flex items-center gap-1 font-medium text-zinc-700 group-hover:text-violet-600">
          View <ArrowRight className="h-3 w-3" />
        </span>
      </div>
    </Link>
  );
}
