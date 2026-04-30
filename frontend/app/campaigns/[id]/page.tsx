import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { LeakCard } from "@/components/leak-card";
import { TrendChart } from "@/components/trend-chart";
import { getCampaignDetail } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

export default async function CampaignDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let detail;
  try {
    detail = await getCampaignDetail(id);
  } catch {
    notFound();
  }
  const { campaign, daily_metrics_90d, leaks } = detail;

  const last28 = daily_metrics_90d.slice(-28);
  const sum = (k: keyof (typeof last28)[number]) =>
    last28.reduce((acc, r) => acc + Number(r[k] ?? 0), 0);

  const spend28 = sum("spend");
  const revenue28 = sum("revenue");
  const conv28 = sum("conversions");
  const clicks28 = sum("clicks");
  const roas = spend28 > 0 ? revenue28 / spend28 : 0;

  return (
    <div className="px-10 py-8 max-w-6xl mx-auto">
      <Link
        href="/campaigns"
        className="inline-flex items-center gap-1 text-xs font-medium text-zinc-500 hover:text-zinc-900"
      >
        <ArrowLeft className="h-3 w-3" />
        Back to campaigns
      </Link>

      <header className="mt-4">
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-400">
          Campaign · {campaign.brand_name}
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">
          {campaign.name}
        </h1>
        <p className="text-sm text-zinc-500">
          {campaign.objective ?? "—"} · {campaign.status} · daily budget{" "}
          {formatCurrency(campaign.daily_budget)}
        </p>
      </header>
      <section className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Spend (28d)" value={formatCurrency(spend28)} />
        <Stat label="Revenue (28d)" value={formatCurrency(revenue28)} />
        <Stat
          label="ROAS (28d)"
          value={`${roas.toFixed(2)}x`}
          tone={roas >= 1.5 ? "good" : roas >= 0.8 ? "neutral" : "bad"}
        />
        <Stat
          label="Conversions / clicks"
          value={`${conv28} / ${clicks28}`}
          subtitle={
            clicks28 > 0
              ? `${((conv28 / clicks28) * 100).toFixed(2)}% CVR`
              : undefined
          }
        />
      </section>
      <section className="mt-6 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-zinc-900">
              Daily spend vs revenue
            </h2>
            <p className="text-xs text-zinc-500">last 90 days</p>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <Legend color="#8b5cf6" label="Spend" />
            <Legend color="#fb923c" label="Revenue" />
          </div>
        </div>
        <div className="mt-4">
          <TrendChart data={daily_metrics_90d} />
        </div>
      </section>
      <section className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-zinc-500">
            Audience
          </p>
          <p className="mt-3 text-sm font-semibold text-zinc-900">
            {campaign.audience.name ?? "—"}
          </p>
          <dl className="mt-2 space-y-1 text-xs text-zinc-600">
            <Row k="Type" v={campaign.audience.type ?? "—"} />
            <Row
              k="Estimated size"
              v={
                campaign.audience.size_estimate
                  ? campaign.audience.size_estimate.toLocaleString()
                  : "—"
              }
            />
          </dl>
        </div>

        <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-zinc-500">
            Creative
          </p>
          <p className="mt-3 text-sm font-semibold text-zinc-900">
            {campaign.creative.name ?? "—"}
          </p>
          <dl className="mt-2 space-y-1 text-xs text-zinc-600">
            <Row k="Type" v={campaign.creative.type ?? "—"} />
            <Row k="Age" v={`${campaign.creative.age_days} days`} />
            <Row k="Launched" v={campaign.creative.launched_at ?? "—"} />
          </dl>
        </div>
      </section>
      <section className="mt-8">
        <h2 className="text-sm font-semibold text-zinc-900">
          Leaks against this campaign
        </h2>
        {leaks.length === 0 ? (
          <p className="mt-4 rounded-xl border border-dashed border-zinc-300 p-6 text-center text-sm text-zinc-500">
            No leaks detected against this campaign.
          </p>
        ) : (
          <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2">
            {leaks.map((leak) => (
              <LeakCard key={leak.leak_id} leak={leak} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  subtitle,
  tone,
}: {
  label: string;
  value: string;
  subtitle?: string;
  tone?: "good" | "bad" | "neutral";
}) {
  const valueClass =
    tone === "good"
      ? "text-emerald-700"
      : tone === "bad"
        ? "text-red-700"
        : "text-zinc-900";
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] font-medium uppercase tracking-widest text-zinc-500">
        {label}
      </p>
      <p className={`mt-1 text-xl font-semibold ${valueClass}`}>{value}</p>
      {subtitle && <p className="mt-0.5 text-xs text-zinc-500">{subtitle}</p>}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-zinc-500">{k}</dt>
      <dd className="font-medium text-zinc-800 truncate">{v}</dd>
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
