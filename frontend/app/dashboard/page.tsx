import { ArrowUpRight, TrendingUp } from "lucide-react";
import { LeakCard } from "@/components/leak-card";
import { RefreshAllButton } from "@/components/refresh-all-button";
import { TrendChart } from "@/components/trend-chart";
import { getBrandOverview, listBrands } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

export default async function DashboardPage() {
  const brands = await listBrands();
  if (brands.length === 0) {
    return (
      <div className="p-10">
        <h1 className="text-xl font-semibold">No brands found</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Run{" "}
          <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs">
            poetry run python seed.py
          </code>{" "}
          to seed Aurora Coffee Co.
        </p>
      </div>
    );
  }
  const brand = brands[0];
  const overview = await getBrandOverview(brand.id);

  const roas =
    overview.total_spend_28d > 0
      ? overview.total_revenue_28d / overview.total_spend_28d
      : 0;

  return (
    <div className="px-10 py-8 max-w-6xl mx-auto">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-zinc-400">
            Brand
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">
            {overview.brand_name}
          </h1>
          <p className="text-sm text-zinc-500">
            {overview.active_campaigns} active campaigns · last 28 days
          </p>
        </div>
        <RefreshAllButton brandId={overview.brand_id} />
      </header>
      <section className="mt-8 rounded-2xl bg-gradient-to-br from-violet-600 via-violet-500 to-orange-400 p-8 text-white shadow-md">
        <div className="flex items-start justify-between gap-6">
          <div>
            <p className="text-sm font-medium uppercase tracking-widest text-white/70">
              Estimated leak impact
            </p>
            <p className="mt-2 text-5xl font-semibold tracking-tight">
              {formatCurrency(overview.total_leak_impact)}
            </p>
            <p className="mt-2 text-sm text-white/80">
              across {overview.leak_count} detected leak
              {overview.leak_count === 1 ? "" : "s"}
              {overview.total_spend_28d > 0 && (
                <>
                  {" — "}
                  {(
                    (overview.total_leak_impact / overview.total_spend_28d) *
                    100
                  ).toFixed(1)}
                  % of last-28d spend
                </>
              )}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-x-8 gap-y-4 text-right">
            <Stat
              label="Spend (28d)"
              value={formatCurrency(overview.total_spend_28d)}
            />
            <Stat
              label="Revenue (28d)"
              value={formatCurrency(overview.total_revenue_28d)}
            />
            <Stat label="Blended ROAS" value={`${roas.toFixed(2)}x`} />
            <Stat
              label="Active campaigns"
              value={String(overview.active_campaigns)}
            />
          </div>
        </div>
      </section>
      <section className="mt-8 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-zinc-900">
              Daily spend vs revenue
            </h2>
            <p className="text-xs text-zinc-500">
              last 30 days · all campaigns
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <Legend color="#8b5cf6" label="Spend" />
            <Legend color="#fb923c" label="Revenue" />
          </div>
        </div>
        <div className="mt-4">
          <TrendChart data={overview.spend_trend_30d} />
        </div>
      </section>
      <section className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-900">
            Top leaks by estimated impact
          </h2>
          <a
            href="/leaks"
            className="inline-flex items-center gap-1 text-xs font-medium text-violet-700 hover:text-violet-800"
          >
            View all <ArrowUpRight className="h-3 w-3" />
          </a>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          {overview.top_leaks.length === 0 ? (
            <div className="col-span-3 rounded-xl border border-dashed border-zinc-300 p-10 text-center text-sm text-zinc-500">
              <TrendingUp className="mx-auto h-8 w-8 text-zinc-300" />
              <p className="mt-2">
                No leaks detected. Run detection to scan {overview.brand_name}.
              </p>
            </div>
          ) : (
            overview.top_leaks.map((leak) => (
              <LeakCard key={leak.leak_id} leak={leak} />
            ))
          )}
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-widest text-white/60">
        {label}
      </p>
      <p className="mt-1 text-base font-semibold">{value}</p>
    </div>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-zinc-600">
      <span className="h-2 w-2 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}
