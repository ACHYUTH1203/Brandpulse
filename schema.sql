CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS brands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    mrr_band TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audiences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    size_estimate INTEGER,
    seed_audience_id UUID REFERENCES audiences(id),
    lookalike_pct NUMERIC(5,2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audiences_brand ON audiences(brand_id);

CREATE TABLE IF NOT EXISTS audience_overlap (
    audience_a UUID NOT NULL REFERENCES audiences(id) ON DELETE CASCADE,
    audience_b UUID NOT NULL REFERENCES audiences(id) ON DELETE CASCADE,
    overlap_pct NUMERIC(5,2) NOT NULL,
    PRIMARY KEY (audience_a, audience_b),
    CHECK (audience_a < audience_b)
);

CREATE TABLE IF NOT EXISTS creatives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    creative_type TEXT,
    launched_at DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_creatives_brand ON creatives(brand_id);

CREATE TABLE IF NOT EXISTS campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    objective TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    audience_id UUID REFERENCES audiences(id),
    creative_id UUID REFERENCES creatives(id),
    daily_budget NUMERIC(10,2),
    started_at DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_campaigns_brand ON campaigns(brand_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_audience ON campaigns(audience_id);
CREATE INDEX IF NOT EXISTS idx_campaigns_creative ON campaigns(creative_id);

CREATE TABLE IF NOT EXISTS daily_metrics (
    id BIGSERIAL PRIMARY KEY,
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    spend NUMERIC(10,2) NOT NULL DEFAULT 0,
    impressions INTEGER NOT NULL DEFAULT 0,
    clicks INTEGER NOT NULL DEFAULT 0,
    conversions INTEGER NOT NULL DEFAULT 0,
    revenue NUMERIC(10,2) NOT NULL DEFAULT 0,
    frequency NUMERIC(4,2) NOT NULL DEFAULT 0,
    reach INTEGER NOT NULL DEFAULT 0,
    UNIQUE (campaign_id, date)
);
CREATE INDEX IF NOT EXISTS idx_daily_metrics_campaign_date
    ON daily_metrics(campaign_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_metrics_date ON daily_metrics(date DESC);

CREATE TABLE IF NOT EXISTS skus (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    cost NUMERIC(10,2) NOT NULL,
    price NUMERIC(10,2) NOT NULL,
    margin_pct NUMERIC(5,2) GENERATED ALWAYS AS
        (((price - cost) / NULLIF(price, 0)) * 100) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_skus_brand ON skus(brand_id);

CREATE TABLE IF NOT EXISTS leaks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    leak_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    dollar_impact NUMERIC(10,2) NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    facts JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'open'
);
CREATE INDEX IF NOT EXISTS idx_leaks_brand_detected ON leaks(brand_id, detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_leaks_dollar_impact ON leaks(dollar_impact DESC);
CREATE INDEX IF NOT EXISTS idx_leaks_type ON leaks(leak_type);

CREATE TABLE IF NOT EXISTS insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    leak_id UUID NOT NULL REFERENCES leaks(id) ON DELETE CASCADE,
    summary TEXT,
    root_cause TEXT,
    recommendations JSONB DEFAULT '[]'::jsonb,
    confidence NUMERIC(3,2),
    llm_model TEXT,
    tokens_used INTEGER,
    cost_usd NUMERIC(10,4),
    trace JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_insights_leak ON insights(leak_id);

ALTER TABLE insights ADD COLUMN IF NOT EXISTS card JSONB DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS digests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
    sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    channel TEXT NOT NULL,
    leak_ids UUID[] NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_digests_brand ON digests(brand_id, sent_at DESC);
