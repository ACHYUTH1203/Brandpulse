import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, AlertCircle } from "lucide-react";
import { InsightChart } from "@/components/insight-chart";
import { InsightTrace } from "@/components/insight-trace";
import { RecommendationCard } from "@/components/recommendation-card";
import { RegenerateButton } from "@/components/regenerate-button";
import { SeverityBadge } from "@/components/severity-badge";
import { getCampaignDetail, getLeakDetail } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

const TYPE_LABEL: Record<string, string> = {
  zombie: "Zombie spend",
  creative_fatigue: "Creative fatigue",
  cpa_creep: "CPA creep",
  audience_saturation: "Audience saturation",
  budget_misallocation: "Budget misallocation",
};

export default async function InsightDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let detail;
  try {
    detail = await getLeakDetail(id);
  } catch {
    notFound();
  }

  const { leak, insight } = detail;

  const campaignDetail = leak.campaign_id
    ? await getCampaignDetail(leak.campaign_id).catch(() => null)
    : null;

  const card = insight?.card;

  return (
    <div className="px-10 py-8 max-w-6xl mx-auto">
      <Link
        href="/leaks"
        className="inline-flex items-center gap-1 text-xs font-medium text-zinc-500 hover:text-zinc-900"
      >
        <ArrowLeft className="h-3 w-3" />
        Back to leaks
      </Link>

      <header className="mt-4 flex items-start justify-between gap-6">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <SeverityBadge severity={leak.severity} />
            <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-zinc-600">
              {TYPE_LABEL[leak.leak_type] ?? leak.leak_type}
            </span>
            {insight?.confidence != null && (
              <span className="text-xs text-zinc-500">
                confidence {(insight.confidence * 100).toFixed(0)}%
              </span>
            )}
          </div>

          <h1 className="mt-3 text-2xl font-semibold tracking-tight text-zinc-900">
            {card?.title ?? leak.leak_type}
          </h1>

          <p className="mt-1 text-sm text-zinc-500">
            {leak.campaign_name ?? "brand-level"} · {leak.period_start} →{" "}
            {leak.period_end}
          </p>
        </div>

        <RegenerateButton />
      </header>
      <section className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="md:col-span-2 rounded-2xl bg-gradient-to-br from-violet-600 via-violet-500 to-orange-400 p-6 text-white shadow-md">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-white/70">
            Estimated impact
          </p>
          <p className="mt-1 text-4xl font-semibold tracking-tight">
            {formatCurrency(leak.dollar_impact)}
          </p>
          {card?.summary && (
            <p className="mt-3 text-sm text-white/90 leading-relaxed">
              {card.summary}
            </p>
          )}
        </div>

        <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-zinc-500">
            Key facts
          </p>
          {card?.key_facts && card.key_facts.length > 0 ? (
            <dl className="mt-3 space-y-2 text-sm">
              {card.key_facts.map((f, i) => (
                <div
                  key={i}
                  className="flex items-baseline justify-between gap-3"
                >
                  <dt className="text-zinc-600">{f.label}</dt>
                  <dd className="font-semibold tabular-nums text-zinc-900">
                    {f.value}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="mt-3 text-sm text-zinc-500">
              No key facts available.
            </p>
          )}
        </div>
      </section>
      {campaignDetail && campaignDetail.daily_metrics_90d.length > 0 && (
        <section className="mt-6 rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-zinc-900">
                Spend vs conversions · {campaignDetail.campaign.name}
              </h2>
              <p className="text-xs text-zinc-500">
                last 30 days · red shaded area = leak window
              </p>
            </div>
            <div className="flex items-center gap-4 text-xs">
              <Legend color="#8b5cf6" label="Spend" />
              <Legend color="#fb923c" label="Conversions" />
            </div>
          </div>
          <div className="mt-4">
            <InsightChart
              data={campaignDetail.daily_metrics_90d}
              periodStart={leak.period_start}
              periodEnd={leak.period_end}
            />
          </div>
        </section>
      )}
      <section className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <div className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-zinc-500">
              AI Hypothesis · Root cause
            </p>
            <p className="mt-3 text-base leading-relaxed text-zinc-800">
              {insight?.root_cause ?? (
                <span className="text-zinc-400">
                  No insight generated yet — click Regenerate.
                </span>
              )}
            </p>
            {card?.needs_review && (
              <div className="mt-4 flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-xs text-amber-800 ring-1 ring-amber-200">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>
                  Confidence is below threshold. Treat this as a flag for
                  review, not an action recommendation.
                </span>
              </div>
            )}
          </div>
          <div>
            <h2 className="text-sm font-semibold text-zinc-900">
              Recommended next steps
            </h2>
            {insight?.recommendations && insight.recommendations.length > 0 ? (
              <div className="mt-3 space-y-3">
                {insight.recommendations.map((rec, i) => (
                  <RecommendationCard key={i} index={i + 1} rec={rec} />
                ))}
              </div>
            ) : (
              <p className="mt-3 rounded-xl border border-dashed border-zinc-300 p-6 text-center text-sm text-zinc-500">
                No recommendations were generated for this leak.
              </p>
            )}
          </div>
        </div>
        <aside className="space-y-6">
          {campaignDetail && (
            <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-zinc-500">
                Campaign
              </p>
              <p className="mt-3 text-sm font-semibold text-zinc-900">
                {campaignDetail.campaign.name}
              </p>
              <dl className="mt-3 space-y-1.5 text-xs text-zinc-600">
                <Row
                  k="Audience"
                  v={campaignDetail.campaign.audience.name ?? "—"}
                />
                <Row
                  k="Audience type"
                  v={campaignDetail.campaign.audience.type ?? "—"}
                />
                <Row
                  k="Creative"
                  v={
                    campaignDetail.campaign.creative.name
                      ? `${campaignDetail.campaign.creative.name} (${campaignDetail.campaign.creative.age_days}d old)`
                      : "—"
                  }
                />
                <Row
                  k="Daily budget"
                  v={formatCurrency(campaignDetail.campaign.daily_budget)}
                />
                <Row
                  k="Objective"
                  v={campaignDetail.campaign.objective ?? "—"}
                />
                <Row k="Status" v={campaignDetail.campaign.status} />
              </dl>
            </div>
          )}

          {insight?.trace && insight.trace.length > 0 && (
            <InsightTrace trace={insight.trace} />
          )}
        </aside>
      </section>
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
