const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type Severity = "low" | "medium" | "high";

export type LeakType =
  | "zombie"
  | "creative_fatigue"
  | "cpa_creep"
  | "audience_saturation"
  | "budget_misallocation";

export interface BrandSummary {
  id: string;
  name: string;
  mrr_band: string | null;
  active_campaigns: number;
}

export interface LeakListItem {
  leak_id: string;
  leak_type: LeakType;
  severity: Severity;
  dollar_impact: number;
  period_start: string;
  period_end: string;
  campaign_name: string | null;
  title: string | null;
  summary: string | null;
  confidence: number | null;
  has_recommendations: boolean;
}

export interface BrandOverview {
  brand_id: string;
  brand_name: string;
  total_spend_28d: number;
  total_revenue_28d: number;
  total_leak_impact: number;
  leak_count: number;
  active_campaigns: number;
  top_leaks: LeakListItem[];
  spend_trend_30d: { date: string; spend: number; revenue: number }[];
}

export interface LeakListResponse {
  total: number;
  leaks: LeakListItem[];
}

export interface Recommendation {
  title: string;
  action: string;
  rationale: string;
}

export interface InsightCard {
  leak_id: string;
  leak_type: LeakType;
  title: string;
  summary: string;
  severity: Severity;
  dollar_impact: number;
  period: { start: string; end: string };
  scope: "brand-level" | "campaign-level";
  campaign_name: string | null;
  root_cause: string;
  confidence: number;
  needs_review: boolean;
  recommendations: Recommendation[];
  key_facts: { label: string; value: string }[];
}

export interface TraceEntry {
  node: string;
  started_at: string;
  finished_at: string;
  summary: string;
  skipped?: boolean;
  model?: string;
}

export interface LeakDetail {
  leak: {
    id: string;
    brand_id: string;
    brand_name: string;
    campaign_id: string | null;
    campaign_name: string | null;
    leak_type: LeakType;
    severity: Severity;
    dollar_impact: number;
    detected_at: string;
    period_start: string;
    period_end: string;
    facts: Record<string, unknown>;
    status: string;
  };
  insight: {
    id: string;
    summary: string;
    root_cause: string;
    recommendations: Recommendation[];
    confidence: number | null;
    llm_model: string | null;
    trace: TraceEntry[];
    card: InsightCard;
    created_at: string;
  } | null;
}

export interface CampaignListItem {
  id: string;
  name: string;
  objective: string | null;
  status: string;
  daily_budget: number;
  audience_name: string | null;
  creative_name: string | null;
  creative_age_days: number;
  spend_28d: number;
  revenue_28d: number;
  roas_28d: number | null;
  leak_count: number;
}

export interface CampaignDetail {
  campaign: {
    id: string;
    name: string;
    brand_name: string;
    objective: string | null;
    status: string;
    daily_budget: number;
    started_at: string | null;
    audience: {
      id: string | null;
      name: string | null;
      type: string | null;
      size_estimate: number;
    };
    creative: {
      id: string | null;
      name: string | null;
      type: string | null;
      launched_at: string | null;
      age_days: number;
    };
  };
  daily_metrics_90d: {
    date: string;
    spend: number;
    impressions: number;
    clicks: number;
    conversions: number;
    revenue: number;
    frequency: number;
  }[];
  leaks: LeakListItem[];
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    cache: "no-store",
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${path} — ${body}`);
  }
  return res.json() as Promise<T>;
}

export const listBrands = () => api<BrandSummary[]>("/brands");

export const getBrandOverview = (brandId: string) =>
  api<BrandOverview>(`/brands/${brandId}/overview`);

export const listLeaks = (params: {
  brand_id?: string;
  severity?: Severity;
  leak_type?: LeakType;
  limit?: number;
  offset?: number;
}) => {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null) qs.set(k, String(v));
  }
  return api<LeakListResponse>(`/leaks?${qs.toString()}`);
};

export const getLeakDetail = (leakId: string) =>
  api<LeakDetail>(`/leaks/${leakId}`);

export const getCampaignDetail = (campaignId: string) =>
  api<CampaignDetail>(`/campaigns/${campaignId}`);

export const listCampaignsForBrand = (brandId: string) =>
  api<CampaignListItem[]>(`/brands/${brandId}/campaigns`);

export const refreshBrand = (brandId: string) =>
  api<unknown>(`/admin/refresh/${brandId}`, { method: "POST" });

export const runDetection = (brandId: string) =>
  api<unknown>(`/admin/run-detection/${brandId}`, { method: "POST" });

export const runWorkflow = () =>
  api<unknown>(`/admin/run-workflow`, { method: "POST" });

export const injectLeak = (body: {
  scenario: "zombie" | "fatigue" | "cpa_spike";
  campaign_id?: string;
  days_affected?: number;
}) =>
  api<unknown>(`/admin/inject-leak`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
