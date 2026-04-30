import { CheckCircle2, Plug } from "lucide-react";
import { listBrands, listCampaignsForBrand } from "@/lib/api";

export default async function ConnectionsPage() {
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
    <div className="px-10 py-8 max-w-4xl mx-auto">
      <header>
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-400">
          Connections
        </p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">
          Data sources
        </h1>
        <p className="text-sm text-zinc-500">
          Where BrandPulse pulls your campaign data from.
        </p>
      </header>
      <section className="mt-8 overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm">
        <div className="flex items-center gap-4 border-b border-zinc-100 px-6 py-5">
          <div className="grid h-12 w-12 place-items-center rounded-xl bg-gradient-to-br from-blue-500 to-violet-500 text-white shadow-sm">
            <span className="text-xl font-bold">M</span>
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-base font-semibold text-zinc-900">Meta Ads</p>
            <p className="text-xs text-zinc-500">{brand.name}</p>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Connected
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4 px-6 py-5 md:grid-cols-4">
          <Stat label="Campaigns" value={campaigns.length.toString()} />
          <Stat
            label="Last sync"
            value="2 minutes ago"
            subtitle="next in 22m"
          />
          <Stat label="Sync status" value="Healthy" tone="good" />
          <Stat label="Permissions" value="Read-only" />
        </div>

        <div className="border-t border-zinc-100 bg-zinc-50 px-6 py-3 text-xs text-zinc-500">
          <p>
            Permissions:{" "}
            <code className="rounded bg-white px-1.5 py-0.5 ring-1 ring-zinc-200">
              ads_read
            </code>{" "}
            <code className="rounded bg-white px-1.5 py-0.5 ring-1 ring-zinc-200">
              ads_management
            </code>{" "}
            <code className="rounded bg-white px-1.5 py-0.5 ring-1 ring-zinc-200">
              business_management
            </code>
          </p>
        </div>
      </section>
      <section className="mt-8">
        <h2 className="text-sm font-semibold text-zinc-900">
          Available connectors
        </h2>
        <p className="text-xs text-zinc-500 mt-0.5">
          More integrations are coming. Each one feeds the same detection +
          insight pipeline.
        </p>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
          <Placeholder name="Google Ads" letter="G" />
          <Placeholder name="Shopify" letter="S" />
          <Placeholder name="TikTok Ads" letter="T" />
        </div>
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
  tone?: "good";
}) {
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-widest text-zinc-500">
        {label}
      </p>
      <p
        className={`mt-1 text-base font-semibold ${
          tone === "good" ? "text-emerald-700" : "text-zinc-900"
        }`}
      >
        {value}
      </p>
      {subtitle && <p className="text-xs text-zinc-500">{subtitle}</p>}
    </div>
  );
}

function Placeholder({ name, letter }: { name: string; letter: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-dashed border-zinc-300 bg-white px-4 py-3 opacity-70">
      <div className="grid h-9 w-9 place-items-center rounded-lg bg-zinc-100 text-sm font-bold text-zinc-500">
        {letter}
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-zinc-700">{name}</p>
        <p className="text-xs text-zinc-400">Coming soon</p>
      </div>
      <Plug className="h-4 w-4 text-zinc-400" />
    </div>
  );
}
