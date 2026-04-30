import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { listBrands, listCampaignsForBrand } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

export default async function CampaignsPage() {
  const brands = await listBrands();
  if (brands.length === 0) {
    return (
      <div className="p-10 text-sm text-zinc-600">
        No brands found. Run{" "}
        <code className="rounded bg-zinc-100 px-1.5">
          poetry run python seed.py
        </code>
        .
      </div>
    );
  }
  const brand = brands[0];
  const campaigns = await listCampaignsForBrand(brand.id);

  return (
    <div className="px-10 py-8 max-w-6xl mx-auto">
      <header>
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-400">
          Campaigns · {brand.name}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">
          {campaigns.length} campaigns
        </h1>
        <p className="text-sm text-zinc-500">
          Sorted by 28-day spend. Click any row for the campaign deep-dive.
        </p>
      </header>

      <div className="mt-6 overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
        <table className="w-full text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="px-5 py-3 text-left font-medium">Name</th>
              <th className="px-5 py-3 text-left font-medium">
                Audience / Creative
              </th>
              <th className="px-5 py-3 text-right font-medium">Spend (28d)</th>
              <th className="px-5 py-3 text-right font-medium">Revenue</th>
              <th className="px-5 py-3 text-right font-medium">ROAS</th>
              <th className="px-5 py-3 text-right font-medium">Leaks</th>
              <th className="px-5 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100">
            {campaigns.map((c) => (
              <tr key={c.id} className="group transition hover:bg-zinc-50">
                <td className="px-5 py-4">
                  <p className="font-medium text-zinc-900">{c.name}</p>
                  <p className="text-xs text-zinc-500">
                    {c.objective ?? "—"} · {c.status}
                  </p>
                </td>
                <td className="px-5 py-4 text-zinc-600">
                  <p className="truncate max-w-xs">{c.audience_name ?? "—"}</p>
                  <p className="truncate max-w-xs text-xs text-zinc-500">
                    {c.creative_name ?? "—"}
                    {c.creative_age_days > 0 && (
                      <> · {c.creative_age_days}d old</>
                    )}
                  </p>
                </td>
                <td className="px-5 py-4 text-right tabular-nums font-semibold text-zinc-900">
                  {formatCurrency(c.spend_28d)}
                </td>
                <td className="px-5 py-4 text-right tabular-nums text-zinc-700">
                  {formatCurrency(c.revenue_28d)}
                </td>
                <td className="px-5 py-4 text-right tabular-nums">
                  <RoasCell roas={c.roas_28d} />
                </td>
                <td className="px-5 py-4 text-right">
                  {c.leak_count > 0 ? (
                    <span className="inline-flex items-center rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-700 ring-1 ring-red-200">
                      {c.leak_count}
                    </span>
                  ) : (
                    <span className="text-zinc-300">—</span>
                  )}
                </td>
                <td className="px-5 py-4 text-right">
                  <Link
                    href={`/campaigns/${c.id}`}
                    className="inline-flex items-center gap-1 text-xs font-medium text-violet-700 hover:text-violet-800"
                  >
                    Open <ArrowRight className="h-3 w-3" />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RoasCell({ roas }: { roas: number | null }) {
  if (roas == null) return <span className="text-zinc-300">—</span>;
  const cls =
    roas >= 1.5
      ? "text-emerald-700"
      : roas >= 0.8
        ? "text-zinc-700"
        : "text-red-700";
  return <span className={`font-medium ${cls}`}>{roas.toFixed(2)}x</span>;
}
