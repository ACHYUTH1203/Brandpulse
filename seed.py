import os

import random

import sys

import uuid

from dataclasses import dataclass

from datetime import date, timedelta

from pathlib import Path

from typing import Optional

import psycopg

from dotenv import load_dotenv

from psycopg.rows import dict_row

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set in .env")

RANDOM_SEED = 42

DAYS = 90

END_DATE = date.today()

START_DATE = END_DATE - timedelta(days=DAYS - 1)

BRAND_NAME = "Aurora Coffee Co."

BRAND_MRR_BAND = "$1M-$5M"

ZOMBIE_START_DAY = 60

FATIGUE_START_DAY = 45

CPA_CREEP_START_DAY = 68

SATURATION_LAST_DAYS = 14


@dataclass
class AudienceSpec:
    key: str
    name: str
    type: str
    size: int
    lookalike_pct: Optional[float] = None
    seed_audience_key: Optional[str] = None


@dataclass
class CreativeSpec:
    key: str
    name: str
    creative_type: str
    age_days: int


@dataclass
class CampaignSpec:
    key: str
    name: str
    objective: str
    audience_key: str
    creative_key: str
    daily_budget: float
    base_ctr: float
    base_cvr: float
    base_cpm: float
    base_aov: float
    base_frequency: float
    audience_size: int
    leak_type: Optional[str] = None


AUDIENCES = [
    AudienceSpec("aud_seed_purchasers", "Past Purchasers (seed)", "custom", 28_000),
    AudienceSpec(
        "aud_lal_1",
        "LAL 1% - Past Purchasers",
        "lookalike",
        1_500_000,
        1.0,
        "aud_seed_purchasers",
    ),
    AudienceSpec(
        "aud_lal_2",
        "LAL 2% - Past Purchasers",
        "lookalike",
        3_000_000,
        2.0,
        "aud_seed_purchasers",
    ),
    AudienceSpec(
        "aud_lal_3",
        "LAL 3% - Past Purchasers",
        "lookalike",
        4_500_000,
        3.0,
        "aud_seed_purchasers",
    ),
    AudienceSpec("aud_visitors_30d", "Site Visitors 30d", "retargeting", 250_000),
    AudienceSpec("aud_visitors_60d", "Site Visitors 60d", "retargeting", 400_000),
    AudienceSpec("aud_cart_abandon", "Cart Abandoners 14d", "retargeting", 80_000),
    AudienceSpec("aud_email_list", "Email Subscribers", "custom", 45_000),
    AudienceSpec("aud_broad_coffee", "Broad US - Coffee Interest", "broad", 25_000_000),
    AudienceSpec("aud_broad_us", "Broad US 25-54", "broad", 80_000_000),
]

CREATIVES = [
    CreativeSpec("cr_winter_promo", "Winter Promo - Lifestyle", "image", 12),
    CreativeSpec("cr_summer_sale", "Summer Sale Banner", "image", 14),
    CreativeSpec("cr_cold_brew_video", "Cold Brew - Video Ad", "video", 8),
    CreativeSpec("cr_retgt_old_v1", "Retargeting V1 - Mug Hero", "image", 31),
    CreativeSpec("cr_retgt_v2", "Retargeting V2 - Bean Story", "carousel", 9),
    CreativeSpec("cr_holiday_push", "Holiday Gift Bundle", "carousel", 6),
    CreativeSpec("cr_brand_story", "Brand Story Video", "video", 22),
    CreativeSpec("cr_recipe_content", "Recipe Carousel", "carousel", 18),
    CreativeSpec("cr_blog_post", "Blog Post Promo", "image", 15),
    CreativeSpec("cr_broad_v1", "Broad - Whole Bean", "image", 20),
]

CAMPAIGNS = [
    CampaignSpec(
        "cmp_lal1_winter",
        "Winter Promo - LAL 1%",
        "conversions",
        "aud_lal_1",
        "cr_winter_promo",
        daily_budget=350,
        base_ctr=0.011,
        base_cvr=0.022,
        base_cpm=14.0,
        base_aov=42.0,
        base_frequency=2.4,
        audience_size=1_500_000,
    ),
    CampaignSpec(
        "cmp_sat_lal1",
        "Cold Brew - LAL 1%",
        "conversions",
        "aud_lal_1",
        "cr_cold_brew_video",
        daily_budget=320,
        base_ctr=0.012,
        base_cvr=0.020,
        base_cpm=14.5,
        base_aov=44.0,
        base_frequency=2.6,
        audience_size=1_500_000,
        leak_type="saturation",
    ),
    CampaignSpec(
        "cmp_sat_lal2",
        "Cold Brew - LAL 2%",
        "conversions",
        "aud_lal_2",
        "cr_cold_brew_video",
        daily_budget=380,
        base_ctr=0.010,
        base_cvr=0.018,
        base_cpm=13.0,
        base_aov=44.0,
        base_frequency=2.5,
        audience_size=3_000_000,
        leak_type="saturation",
    ),
    CampaignSpec(
        "cmp_sat_lal3",
        "Cold Brew - LAL 3%",
        "conversions",
        "aud_lal_3",
        "cr_cold_brew_video",
        daily_budget=420,
        base_ctr=0.009,
        base_cvr=0.016,
        base_cpm=12.0,
        base_aov=44.0,
        base_frequency=2.4,
        audience_size=4_500_000,
        leak_type="saturation",
    ),
    CampaignSpec(
        "cmp_zombie_lal1",
        "Summer Sale - LAL 1%",
        "conversions",
        "aud_lal_1",
        "cr_summer_sale",
        daily_budget=400,
        base_ctr=0.011,
        base_cvr=0.021,
        base_cpm=14.0,
        base_aov=42.0,
        base_frequency=2.5,
        audience_size=1_500_000,
        leak_type="zombie",
    ),
    CampaignSpec(
        "cmp_fatigue_retgt",
        "Retargeting 30d - Mug Hero",
        "conversions",
        "aud_visitors_30d",
        "cr_retgt_old_v1",
        daily_budget=220,
        base_ctr=0.020,
        base_cvr=0.045,
        base_cpm=18.0,
        base_aov=46.0,
        base_frequency=2.8,
        audience_size=250_000,
        leak_type="fatigue",
    ),
    CampaignSpec(
        "cmp_retgt_60d",
        "Retargeting 60d - Bean Story",
        "conversions",
        "aud_visitors_60d",
        "cr_retgt_v2",
        daily_budget=180,
        base_ctr=0.018,
        base_cvr=0.040,
        base_cpm=16.0,
        base_aov=44.0,
        base_frequency=2.7,
        audience_size=400_000,
    ),
    CampaignSpec(
        "cmp_retgt_cart",
        "Retargeting - Cart Abandoners",
        "conversions",
        "aud_cart_abandon",
        "cr_retgt_v2",
        daily_budget=150,
        base_ctr=0.025,
        base_cvr=0.060,
        base_cpm=20.0,
        base_aov=48.0,
        base_frequency=3.4,
        audience_size=80_000,
    ),
    CampaignSpec(
        "cmp_retgt_email",
        "Retargeting - Email List",
        "conversions",
        "aud_email_list",
        "cr_holiday_push",
        daily_budget=120,
        base_ctr=0.022,
        base_cvr=0.055,
        base_cpm=18.0,
        base_aov=46.0,
        base_frequency=2.6,
        audience_size=45_000,
    ),
    CampaignSpec(
        "cmp_holiday",
        "Holiday Gift Bundle - LAL 1%",
        "conversions",
        "aud_lal_1",
        "cr_holiday_push",
        daily_budget=280,
        base_ctr=0.012,
        base_cvr=0.024,
        base_cpm=15.0,
        base_aov=58.0,
        base_frequency=2.5,
        audience_size=1_500_000,
    ),
    CampaignSpec(
        "cmp_cpa_creep",
        "Broad US - Coffee Interest",
        "conversions",
        "aud_broad_coffee",
        "cr_broad_v1",
        daily_budget=1500,
        base_ctr=0.008,
        base_cvr=0.018,
        base_cpm=10.0,
        base_aov=40.0,
        base_frequency=1.8,
        audience_size=25_000_000,
        leak_type="cpa_creep",
    ),
    CampaignSpec(
        "cmp_broad_us",
        "Broad US 25-54 - Whole Bean",
        "conversions",
        "aud_broad_us",
        "cr_broad_v1",
        daily_budget=800,
        base_ctr=0.008,
        base_cvr=0.020,
        base_cpm=9.5,
        base_aov=42.0,
        base_frequency=1.5,
        audience_size=80_000_000,
    ),
    CampaignSpec(
        "cmp_broad_espresso",
        "Broad US - Espresso Push",
        "conversions",
        "aud_broad_us",
        "cr_broad_v1",
        daily_budget=600,
        base_ctr=0.008,
        base_cvr=0.022,
        base_cpm=10.0,
        base_aov=44.0,
        base_frequency=1.6,
        audience_size=80_000_000,
    ),
    CampaignSpec(
        "cmp_broad_seasonal",
        "Broad US - Seasonal Drinks",
        "conversions",
        "aud_broad_coffee",
        "cr_holiday_push",
        daily_budget=700,
        base_ctr=0.009,
        base_cvr=0.020,
        base_cpm=10.0,
        base_aov=42.0,
        base_frequency=1.7,
        audience_size=25_000_000,
    ),
    CampaignSpec(
        "cmp_misalloc_awareness",
        "Awareness - Brand Story",
        "awareness",
        "aud_broad_us",
        "cr_brand_story",
        daily_budget=800,
        base_ctr=0.005,
        base_cvr=0.004,
        base_cpm=8.0,
        base_aov=38.0,
        base_frequency=1.4,
        audience_size=80_000_000,
        leak_type="misallocation",
    ),
    CampaignSpec(
        "cmp_misalloc_engage",
        "Engagement - Recipes",
        "engagement",
        "aud_broad_coffee",
        "cr_recipe_content",
        daily_budget=550,
        base_ctr=0.008,
        base_cvr=0.003,
        base_cpm=7.0,
        base_aov=35.0,
        base_frequency=1.6,
        audience_size=25_000_000,
        leak_type="misallocation",
    ),
    CampaignSpec(
        "cmp_misalloc_traffic",
        "Traffic - Blog Drive",
        "traffic",
        "aud_broad_us",
        "cr_blog_post",
        daily_budget=450,
        base_ctr=0.009,
        base_cvr=0.002,
        base_cpm=6.0,
        base_aov=32.0,
        base_frequency=1.3,
        audience_size=80_000_000,
        leak_type="misallocation",
    ),
    CampaignSpec(
        "cmp_misalloc_app",
        "App Installs - Loyalty App",
        "app_installs",
        "aud_broad_us",
        "cr_brand_story",
        daily_budget=350,
        base_ctr=0.006,
        base_cvr=0.005,
        base_cpm=11.0,
        base_aov=30.0,
        base_frequency=1.5,
        audience_size=80_000_000,
        leak_type="misallocation",
    ),
    CampaignSpec(
        "cmp_misalloc_lead",
        "Lead Gen - Newsletter",
        "lead_gen",
        "aud_broad_coffee",
        "cr_recipe_content",
        daily_budget=320,
        base_ctr=0.011,
        base_cvr=0.002,
        base_cpm=8.0,
        base_aov=28.0,
        base_frequency=1.7,
        audience_size=25_000_000,
        leak_type="misallocation",
    ),
    CampaignSpec(
        "cmp_misalloc_reach",
        "Reach - General Awareness",
        "awareness",
        "aud_broad_us",
        "cr_brand_story",
        daily_budget=500,
        base_ctr=0.004,
        base_cvr=0.003,
        base_cpm=7.5,
        base_aov=36.0,
        base_frequency=1.3,
        audience_size=80_000_000,
        leak_type="misallocation",
    ),
]

SKUS = [
    ("Whole Bean - Single Origin", 8.50, 24.00),
    ("Ground Coffee - Medium Roast", 7.20, 19.00),
    ("Espresso Beans - Dark Roast", 9.00, 26.00),
    ("Cold Brew Concentrate", 11.00, 32.00),
    ("Coffee Sampler Pack", 18.00, 48.00),
    ("Reusable Steel Tumbler", 6.50, 28.00),
    ("Pour Over Kit", 22.00, 65.00),
    ("Holiday Gift Bundle", 28.00, 78.00),
]

PLANTED_OVERLAPS = [
    ("aud_lal_1", "aud_lal_2", 65.0),
    ("aud_lal_2", "aud_lal_3", 70.0),
    ("aud_lal_1", "aud_lal_3", 50.0),
    ("aud_visitors_30d", "aud_visitors_60d", 75.0),
    ("aud_visitors_30d", "aud_cart_abandon", 30.0),
]


def gen_daily_row(spec: CampaignSpec) -> dict:
    spend = spec.daily_budget * random.uniform(0.85, 1.10)
    cpm = spec.base_cpm * random.uniform(0.92, 1.08)
    impressions = max(1, int((spend / cpm) * 1000))
    ctr = spec.base_ctr * random.uniform(0.85, 1.15)
    clicks = int(impressions * ctr)
    cvr = spec.base_cvr * random.uniform(0.85, 1.15)
    conversions = int(clicks * cvr)
    aov = spec.base_aov * random.uniform(0.92, 1.08)
    revenue = round(conversions * aov, 2)
    frequency = round(max(1.0, spec.base_frequency + random.uniform(-0.3, 0.3)), 2)
    reach = max(1, int(impressions / max(frequency, 1.0)))
    return {
        "spend": round(spend, 2),
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "revenue": revenue,
        "frequency": frequency,
        "reach": reach,
    }


def apply_zombie(day_index: int, m: dict, spec: CampaignSpec) -> dict:
    if day_index >= ZOMBIE_START_DAY:
        m["clicks"] = int(m["clicks"] * random.uniform(0.55, 0.85))
        m["conversions"] = random.choices([0, 1], weights=[0.85, 0.15])[0]
        m["revenue"] = round(
            m["conversions"] * spec.base_aov * random.uniform(0.9, 1.1), 2
        )
    return m


def apply_fatigue(day_index: int, m: dict, spec: CampaignSpec) -> dict:
    if day_index >= FATIGUE_START_DAY:
        progress = (day_index - FATIGUE_START_DAY) / (DAYS - 1 - FATIGUE_START_DAY)
        ctr_factor = 1.0 - 0.85 * progress
        m["clicks"] = max(0, int(m["clicks"] * ctr_factor))
        m["conversions"] = max(
            0, int(m["clicks"] * spec.base_cvr * random.uniform(0.85, 1.15))
        )
        m["revenue"] = round(
            m["conversions"] * spec.base_aov * random.uniform(0.92, 1.08), 2
        )
        m["frequency"] = round(
            spec.base_frequency + 2.7 * progress + random.uniform(-0.2, 0.2), 2
        )
        m["reach"] = max(1, int(m["impressions"] / max(m["frequency"], 1.0)))
    return m


def apply_cpa_creep(day_index: int, m: dict, spec: CampaignSpec) -> dict:
    if day_index >= CPA_CREEP_START_DAY:
        weeks_in = (day_index - CPA_CREEP_START_DAY) / 7.0
        cpa_inflation = 1.10**weeks_in
        new_conv = max(1, int(m["conversions"] / cpa_inflation))
        m["conversions"] = new_conv
        m["revenue"] = round(new_conv * spec.base_aov * random.uniform(0.92, 1.08), 2)
    return m


def apply_saturation(day_index: int, m: dict, spec: CampaignSpec) -> dict:
    days_from_end = (DAYS - 1) - day_index
    if days_from_end <= SATURATION_LAST_DAYS:
        m["frequency"] = round(random.uniform(4.2, 4.8), 2)
        m["reach"] = max(1, int(m["impressions"] / m["frequency"]))
    return m


LEAK_MODIFIERS = {
    "zombie": apply_zombie,
    "fatigue": apply_fatigue,
    "cpa_creep": apply_cpa_creep,
    "saturation": apply_saturation,
    "misallocation": None,
}

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def apply_schema(conn: psycopg.Connection) -> None:
    print("applying schema...")
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def seed_data(conn: psycopg.Connection) -> None:
    print(f"seeding {BRAND_NAME} ({START_DATE} -> {END_DATE}, {DAYS} days)...")
    with conn.cursor() as cur:
        cur.execute("""
            TRUNCATE digests, insights, leaks, audience_overlap, daily_metrics,
                     campaigns, creatives, audiences, skus, brands
            RESTART IDENTITY CASCADE
        """)
        cur.execute(
            "INSERT INTO brands (name, mrr_band) VALUES (%s, %s) RETURNING id",
            (BRAND_NAME, BRAND_MRR_BAND),
        )
        brand_id = cur.fetchone()[0]
        audience_ids: dict[str, uuid.UUID] = {}
        for a in AUDIENCES:
            cur.execute(
                """INSERT INTO audiences (brand_id, name, type, size_estimate, lookalike_pct)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (brand_id, a.name, a.type, a.size, a.lookalike_pct),
            )
            audience_ids[a.key] = cur.fetchone()[0]
        for a in AUDIENCES:
            if a.seed_audience_key:
                cur.execute(
                    "UPDATE audiences SET seed_audience_id = %s WHERE id = %s",
                    (audience_ids[a.seed_audience_key], audience_ids[a.key]),
                )
        for a_key, b_key, pct in PLANTED_OVERLAPS:
            a_id, b_id = audience_ids[a_key], audience_ids[b_key]
            if a_id > b_id:
                a_id, b_id = b_id, a_id
            cur.execute(
                "INSERT INTO audience_overlap (audience_a, audience_b, overlap_pct) VALUES (%s, %s, %s)",
                (a_id, b_id, pct),
            )
        creative_ids: dict[str, uuid.UUID] = {}
        for c in CREATIVES:
            cur.execute(
                """INSERT INTO creatives (brand_id, name, creative_type, launched_at)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (
                    brand_id,
                    c.name,
                    c.creative_type,
                    END_DATE - timedelta(days=c.age_days),
                ),
            )
            creative_ids[c.key] = cur.fetchone()[0]
        for name, cost, price in SKUS:
            cur.execute(
                "INSERT INTO skus (brand_id, name, cost, price) VALUES (%s, %s, %s, %s)",
                (brand_id, name, cost, price),
            )
        campaign_ids: dict[str, uuid.UUID] = {}
        for spec in CAMPAIGNS:
            cur.execute(
                """INSERT INTO campaigns
                   (brand_id, name, objective, status, audience_id, creative_id,
                    daily_budget, started_at)
                   VALUES (%s, %s, %s, 'active', %s, %s, %s, %s) RETURNING id""",
                (
                    brand_id,
                    spec.name,
                    spec.objective,
                    audience_ids[spec.audience_key],
                    creative_ids[spec.creative_key],
                    spec.daily_budget,
                    START_DATE,
                ),
            )
            campaign_ids[spec.key] = cur.fetchone()[0]
        rows: list[tuple] = []
        for spec in CAMPAIGNS:
            cid = campaign_ids[spec.key]
            modifier = LEAK_MODIFIERS.get(spec.leak_type) if spec.leak_type else None
            for day_index in range(DAYS):
                metric_date = START_DATE + timedelta(days=day_index)
                m = gen_daily_row(spec)
                if modifier:
                    m = modifier(day_index, m, spec)
                rows.append(
                    (
                        cid,
                        metric_date,
                        m["spend"],
                        m["impressions"],
                        m["clicks"],
                        m["conversions"],
                        m["revenue"],
                        m["frequency"],
                        m["reach"],
                    )
                )
        cur.executemany(
            """INSERT INTO daily_metrics
               (campaign_id, date, spend, impressions, clicks,
                conversions, revenue, frequency, reach)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            rows,
        )
    conn.commit()
    print(
        f"  inserted: 1 brand, {len(AUDIENCES)} audiences, {len(CREATIVES)} creatives, "
        f"{len(SKUS)} SKUs, {len(CAMPAIGNS)} campaigns, {len(rows)} daily_metrics"
    )


def verify_leaks(conn: psycopg.Connection) -> bool:
    print("\nverifying planted leaks:")
    fails = 0
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                COALESCE(SUM(dm.spend) FILTER (
                    WHERE dm.date >= CURRENT_DATE - INTERVAL '7 days'), 0) AS spend_7d,
                COALESCE(SUM(dm.conversions) FILTER (
                    WHERE dm.date >= CURRENT_DATE - INTERVAL '7 days'), 0) AS conv_7d
            FROM campaigns c
            JOIN daily_metrics dm ON dm.campaign_id = c.id
            WHERE c.name = %s
        """,
            ("Summer Sale - LAL 1%",),
        )
        row = cur.fetchone()
        ok = row and float(row["spend_7d"]) > 500 and int(row["conv_7d"]) < 2
        fails += print_check(
            "zombie spend on 'Summer Sale - LAL 1%'",
            ok,
            f"spend_7d=${float(row['spend_7d']):.0f}, conv_7d={int(row['conv_7d'])}",
        )
        cur.execute(
            """
            WITH win_7 AS (
                SELECT campaign_id,
                       SUM(clicks)::numeric / NULLIF(SUM(impressions), 0) AS ctr,
                       AVG(frequency) AS freq
                FROM daily_metrics
                WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY campaign_id
            ),
            win_28 AS (
                SELECT campaign_id,
                       SUM(clicks)::numeric / NULLIF(SUM(impressions), 0) AS ctr
                FROM daily_metrics
                WHERE date >= CURRENT_DATE - INTERVAL '28 days'
                GROUP BY campaign_id
            )
            SELECT w7.ctr AS ctr_7d, w28.ctr AS ctr_28d, w7.freq AS freq_7d,
                   (CURRENT_DATE - cr.launched_at) AS creative_age
            FROM campaigns c
            JOIN win_7  w7  ON w7.campaign_id  = c.id
            JOIN win_28 w28 ON w28.campaign_id = c.id
            JOIN creatives cr ON cr.id = c.creative_id
            WHERE c.name = %s
        """,
            ("Retargeting 30d - Mug Hero",),
        )
        row = cur.fetchone()
        if row and row["ctr_28d"] and float(row["ctr_28d"]) > 0:
            ratio = float(row["ctr_7d"]) / float(row["ctr_28d"])
            ok = (
                ratio < 0.5
                and float(row["freq_7d"]) > 4
                and int(row["creative_age"]) > 14
            )
            fails += print_check(
                "creative fatigue on 'Retargeting 30d - Mug Hero'",
                ok,
                f"ctr ratio={ratio:.2f}, freq_7d={float(row['freq_7d']):.2f}, "
                f"creative_age={int(row['creative_age'])}d",
            )
        else:
            fails += print_check(
                "creative fatigue on 'Retargeting 30d - Mug Hero'",
                False,
                "no row or ctr_28d=0",
            )
        cur.execute(
            """
            WITH cpa_7 AS (
                SELECT campaign_id,
                       SUM(spend) / NULLIF(SUM(conversions), 0) AS cpa,
                       SUM(spend) AS spend_7d
                FROM daily_metrics
                WHERE date >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY campaign_id
            ),
            cpa_base AS (
                SELECT campaign_id,
                       SUM(spend) / NULLIF(SUM(conversions), 0) AS cpa
                FROM daily_metrics
                WHERE date >= CURRENT_DATE - INTERVAL '35 days'
                  AND date <  CURRENT_DATE - INTERVAL '28 days'
                GROUP BY campaign_id
            )
            SELECT cpa_7.cpa AS cpa_7d, cpa_base.cpa AS cpa_base, cpa_7.spend_7d
            FROM campaigns c
            JOIN cpa_7    ON cpa_7.campaign_id    = c.id
            JOIN cpa_base ON cpa_base.campaign_id = c.id
            WHERE c.name = %s
        """,
            ("Broad US - Coffee Interest",),
        )
        row = cur.fetchone()
        if row and row["cpa_base"]:
            ratio = float(row["cpa_7d"]) / float(row["cpa_base"])
            ok = ratio > 1.20 and float(row["spend_7d"]) > 1000
            fails += print_check(
                "CPA creep on 'Broad US - Coffee Interest'",
                ok,
                f"cpa ratio={ratio:.2f}, spend_7d=${float(row['spend_7d']):.0f}",
            )
        else:
            fails += print_check(
                "CPA creep on 'Broad US - Coffee Interest'", False, "no baseline row"
            )
        cur.execute(
            """
            SELECT c.name, AVG(dm.frequency) AS freq_14d
            FROM campaigns c
            JOIN daily_metrics dm ON dm.campaign_id = c.id
            WHERE c.name = ANY(%s)
              AND dm.date >= CURRENT_DATE - INTERVAL '14 days'
            GROUP BY c.id, c.name
        """,
            (["Cold Brew - LAL 1%", "Cold Brew - LAL 2%", "Cold Brew - LAL 3%"],),
        )
        freq_rows = cur.fetchall()
        cur.execute("""
            SELECT COUNT(*) AS n
            FROM audience_overlap ao
            WHERE ao.overlap_pct >= 40
              AND ao.audience_a IN (SELECT id FROM audiences WHERE lookalike_pct IS NOT NULL)
              AND ao.audience_b IN (SELECT id FROM audiences WHERE lookalike_pct IS NOT NULL)
        """)
        overlap_count = cur.fetchone()["n"]
        all_high = len(freq_rows) == 3 and all(
            float(r["freq_14d"]) > 4 for r in freq_rows
        )
        ok = all_high and overlap_count >= 3
        freqs = ", ".join(f"{r['name']}={float(r['freq_14d']):.2f}" for r in freq_rows)
        fails += print_check(
            "audience saturation on 3 Cold Brew LALs",
            ok,
            f"{freqs}; overlap_pairs(>=40%)={overlap_count}",
        )
        cur.execute("""
            WITH perf AS (
                SELECT c.id,
                       SUM(dm.spend) AS spend_28d,
                       SUM(dm.revenue) / NULLIF(SUM(dm.spend), 0) AS roas
                FROM campaigns c
                JOIN daily_metrics dm ON dm.campaign_id = c.id
                WHERE dm.date >= CURRENT_DATE - INTERVAL '28 days'
                GROUP BY c.id
            ),
            ranked AS (
                SELECT *, NTILE(4) OVER (ORDER BY roas) AS q FROM perf
            )
            SELECT
                COALESCE(SUM(spend_28d) FILTER (WHERE q = 1), 0) AS bottom,
                COALESCE(SUM(spend_28d), 0)                       AS total
            FROM ranked
        """)
        row = cur.fetchone()
        bottom = float(row["bottom"] or 0)
        total = float(row["total"] or 1)
        share = bottom / total
        ok = share > 0.25
        fails += print_check(
            "budget misallocation (bottom-quartile share)",
            ok,
            f"${bottom:,.0f} / ${total:,.0f} = {share * 100:.1f}%",
        )
    return fails == 0


def print_check(name: str, ok: bool, detail: str) -> int:
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}")
    print(f"         {detail}")
    return 0 if ok else 1


def main() -> None:
    random.seed(RANDOM_SEED)
    print(f"connecting to {DATABASE_URL.split('@')[-1]}\n")
    with psycopg.connect(DATABASE_URL) as conn:
        apply_schema(conn)
        seed_data(conn)
        all_ok = verify_leaks(conn)
    print()
    if all_ok:
        print("OK: all 5 planted leaks are present and detectable.")
    else:
        print("FAILED: one or more planted leaks are not detectable.")
        sys.exit(1)


if __name__ == "__main__":
    main()
