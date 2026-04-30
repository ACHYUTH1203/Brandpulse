import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { SeverityBadge } from "@/components/severity-badge";
import { listLeaks } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

const TYPE_LABEL: Record<string, string> = {
  zombie: "Zombie spend",
  creative_fatigue: "Creative fatigue",
  cpa_creep: "CPA creep",
  audience_saturation: "Audience saturation",
  budget_misallocation: "Budget misallocation",
};

export default async function LeaksPage() {
  const { total, leaks } = await listLeaks({ limit: 100 });

  return (
    <div className="px-10 py-8 max-w-6xl mx-auto">
      <header>
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-400">
          All detected leaks
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">
          Leaks · <span className="text-zinc-400 font-normal">{total}</span>
        </h1>
        <p className="text-sm text-zinc-500">
          Sorted by estimated dollar impact. Click any row to open the full
          insight.
        </p>
      </header>

      <div className="mt-6 overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-5 py-3 text-left font-medium">Type</th>
              <th className="px-5 py-3 text-left font-medium">Severity</th>
              <th className="px-5 py-3 text-right font-medium">Impact</th>
              <th className="px-5 py-3 text-left font-medium">Campaign</th>
              <th className="px-5 py-3 text-left font-medium">Summary</th>
              <th className="px-5 py-3 text-right font-medium">Conf.</th>
              <th className="px-5 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {leaks.map((l) => (
              <tr key={l.leak_id} className="group transition hover:bg-zinc-50">
                <td className="px-5 py-4 font-medium text-zinc-900">
                  {TYPE_LABEL[l.leak_type] ?? l.leak_type}
                </td>
                <td className="px-5 py-4">
                  <SeverityBadge severity={l.severity} />
                </td>
                <td className="px-5 py-4 text-right font-semibold tabular-nums text-zinc-900">
                  {formatCurrency(l.dollar_impact)}
                </td>
                <td className="px-5 py-4 text-zinc-600">
                  {l.campaign_name ?? (
                    <span className="text-zinc-400">brand-level</span>
                  )}
                </td>
                <td className="px-5 py-4 text-zinc-600 max-w-xl">
                  <p className="line-clamp-2">{l.summary ?? "—"}</p>
                </td>
                <td className="px-5 py-4 text-right text-zinc-500 tabular-nums">
                  {l.confidence != null
                    ? `${(l.confidence * 100).toFixed(0)}%`
                    : "—"}
                </td>
                <td className="px-5 py-4 text-right">
                  <Link
                    href={`/insights/${l.leak_id}`}
                    className="inline-flex items-center gap-1 text-xs font-medium text-violet-700 hover:text-violet-800"
                  >
                    Open <ArrowRight className="h-3 w-3" />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {leaks.length === 0 && (
          <div className="p-10 text-center text-sm text-zinc-500">
            No leaks yet. Run detection to scan campaigns.
          </div>
        )}
      </div>
    </div>
  );
}
