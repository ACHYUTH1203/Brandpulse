import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any
from uuid import UUID
import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set in .env")

ZOMBIE_MIN_SPEND_7D = 500

ZOMBIE_MAX_CONV_7D = 2

ZOMBIE_MIN_BASELINE_CVR = 0.01

ZOMBIE_MIN_BASELINE_CLICKS = 100

FATIGUE_CTR_RATIO_MAX = 0.5

FATIGUE_FREQ_MIN = 4.0

FATIGUE_CREATIVE_AGE_MIN = 14

CPA_RATIO_MIN = 1.20

CPA_MIN_SPEND_7D = 1000

SAT_FREQ_MIN = 4.0

SAT_OVERLAP_MIN = 40.0

MISALLOC_BOTTOM_SHARE_MIN = 0.25


@dataclass
class LeakCandidate:
    brand_id: UUID
    campaign_id: UUID | None
    leak_type: str
    severity: str
    dollar_impact: float
    period_start: date
    period_end: date
    facts: dict[str, Any] = field(default_factory=dict)


def detect_zombie(cur, brand_id: UUID) -> list[LeakCandidate]:
    cur.execute(
        """
        WITH agg AS (
            SELECT
                c.id   AS campaign_id,
                c.name AS campaign_name,
                COALESCE(SUM(dm.spend) FILTER (
                    WHERE dm.date >= CURRENT_DATE - INTERVAL '7 days'), 0)        AS spend_7d,
                COALESCE(SUM(dm.conversions) FILTER (
                    WHERE dm.date >= CURRENT_DATE - INTERVAL '7 days'), 0)        AS conv_7d,
                COALESCE(SUM(dm.spend) FILTER (
                    WHERE dm.date >= CURRENT_DATE - INTERVAL '28 days'), 0)       AS spend_28d,
                -- baseline window: everything older than 14 days (clean of recent collapse)
                COALESCE(SUM(dm.clicks)      FILTER (WHERE dm.date <  CURRENT_DATE - INTERVAL '14 days'), 0) AS clicks_baseline,
                COALESCE(SUM(dm.conversions) FILTER (WHERE dm.date <  CURRENT_DATE - INTERVAL '14 days'), 0) AS conv_baseline
            FROM campaigns c
            LEFT JOIN daily_metrics dm ON dm.campaign_id = c.id
            WHERE c.brand_id = %s AND c.status = 'active'
            GROUP BY c.id, c.name
        )
        SELECT *,
            (conv_baseline::numeric / NULLIF(clicks_baseline, 0)) AS cvr_baseline
        FROM agg
        WHERE spend_7d > %s
          AND conv_7d  < %s
          AND clicks_baseline >= %s
          AND (conv_baseline::numeric / NULLIF(clicks_baseline, 0)) >= %s
    """,
        (
            brand_id,
            ZOMBIE_MIN_SPEND_7D,
            ZOMBIE_MAX_CONV_7D,
            ZOMBIE_MIN_BASELINE_CLICKS,
            ZOMBIE_MIN_BASELINE_CVR,
        ),
    )
    end = date.today()
    start = end - timedelta(days=7)
    out: list[LeakCandidate] = []
    for row in cur.fetchall():
        impact = float(row["spend_7d"])
        out.append(
            LeakCandidate(
                brand_id=brand_id,
                campaign_id=row["campaign_id"],
                leak_type="zombie",
                severity="high" if impact > 2000 else "medium",
                dollar_impact=round(impact, 2),
                period_start=start,
                period_end=end,
                facts={
                    "campaign_name": row["campaign_name"],
                    "spend_7d": float(row["spend_7d"]),
                    "spend_28d": float(row["spend_28d"]),
                    "conversions_7d": int(row["conv_7d"]),
                    "baseline_clicks": int(row["clicks_baseline"]),
                    "baseline_conversions": int(row["conv_baseline"]),
                    "baseline_cvr": round(float(row["cvr_baseline"]), 4),
                },
            )
        )
    return out


def detect_creative_fatigue(cur, brand_id: UUID) -> list[LeakCandidate]:
    cur.execute(
        """
        WITH agg AS (
            SELECT
                c.id    AS campaign_id,
                c.name  AS campaign_name,
                cr.id   AS creative_id,
                cr.name AS creative_name,
                (CURRENT_DATE - cr.launched_at)::int AS creative_age,
                SUM(dm.clicks)      FILTER (WHERE dm.date >= CURRENT_DATE - INTERVAL '7 days')  AS clicks_7d,
                SUM(dm.impressions) FILTER (WHERE dm.date >= CURRENT_DATE - INTERVAL '7 days')  AS imp_7d,
                SUM(dm.clicks)      FILTER (WHERE dm.date >= CURRENT_DATE - INTERVAL '28 days') AS clicks_28d,
                SUM(dm.impressions) FILTER (WHERE dm.date >= CURRENT_DATE - INTERVAL '28 days') AS imp_28d,
                SUM(dm.conversions) FILTER (WHERE dm.date >= CURRENT_DATE - INTERVAL '7 days')  AS conv_7d,
                SUM(dm.conversions) FILTER (WHERE dm.date >= CURRENT_DATE - INTERVAL '28 days') AS conv_28d,
                SUM(dm.revenue)     FILTER (WHERE dm.date >= CURRENT_DATE - INTERVAL '28 days') AS rev_28d,
                AVG(dm.frequency)   FILTER (WHERE dm.date >= CURRENT_DATE - INTERVAL '7 days')  AS freq_7d
            FROM campaigns c
            JOIN creatives cr      ON cr.id = c.creative_id
            LEFT JOIN daily_metrics dm ON dm.campaign_id = c.id
            WHERE c.brand_id = %s AND c.status = 'active'
            GROUP BY c.id, c.name, cr.id, cr.name, cr.launched_at
        )
        SELECT *,
            (clicks_7d::numeric  / NULLIF(imp_7d, 0))    AS ctr_7d,
            (clicks_28d::numeric / NULLIF(imp_28d, 0))   AS ctr_28d,
            (conv_28d::numeric   / NULLIF(clicks_28d, 0)) AS cvr_28d,
            (rev_28d::numeric    / NULLIF(conv_28d, 0))  AS aov_28d
        FROM agg
        WHERE imp_7d > 0 AND imp_28d > 0 AND creative_age > %s
    """,
        (brand_id, FATIGUE_CREATIVE_AGE_MIN),
    )
    end = date.today()
    start = end - timedelta(days=7)
    out: list[LeakCandidate] = []
    for row in cur.fetchall():
        ctr_7d = float(row["ctr_7d"] or 0)
        ctr_28d = float(row["ctr_28d"] or 0)
        if ctr_28d == 0:
            continue
        ratio = ctr_7d / ctr_28d
        freq_7d = float(row["freq_7d"] or 0)
        if not (ratio < FATIGUE_CTR_RATIO_MAX and freq_7d > FATIGUE_FREQ_MIN):
            continue
        cvr_28d = float(row["cvr_28d"] or 0)
        aov_28d = float(row["aov_28d"] or 0)
        expected_conv = float(row["imp_7d"]) * ctr_28d * cvr_28d
        actual_conv = float(row["conv_7d"] or 0)
        lost_conv = max(0.0, expected_conv - actual_conv)
        impact = lost_conv * aov_28d
        out.append(
            LeakCandidate(
                brand_id=brand_id,
                campaign_id=row["campaign_id"],
                leak_type="creative_fatigue",
                severity="high" if impact > 2000 else "medium",
                dollar_impact=round(impact, 2),
                period_start=start,
                period_end=end,
                facts={
                    "campaign_name": row["campaign_name"],
                    "creative_name": row["creative_name"],
                    "creative_age_days": int(row["creative_age"]),
                    "ctr_7d": round(ctr_7d, 4),
                    "ctr_28d": round(ctr_28d, 4),
                    "ctr_ratio": round(ratio, 2),
                    "frequency_7d": round(freq_7d, 2),
                    "estimated_lost_conversions": round(lost_conv, 1),
                    "average_order_value_28d": round(aov_28d, 2),
                },
            )
        )
    return out


def detect_cpa_creep(cur, brand_id: UUID) -> list[LeakCandidate]:
    cur.execute(
        """
        WITH agg AS (
            SELECT
                c.id   AS campaign_id,
                c.name AS campaign_name,
                SUM(dm.spend)       FILTER (WHERE dm.date >= CURRENT_DATE - INTERVAL '7 days')  AS spend_7d,
                SUM(dm.conversions) FILTER (WHERE dm.date >= CURRENT_DATE - INTERVAL '7 days')  AS conv_7d,
                SUM(dm.spend)       FILTER (WHERE dm.date >= CURRENT_DATE - INTERVAL '35 days'
                                              AND dm.date <  CURRENT_DATE - INTERVAL '28 days') AS spend_base,
                SUM(dm.conversions) FILTER (WHERE dm.date >= CURRENT_DATE - INTERVAL '35 days'
                                              AND dm.date <  CURRENT_DATE - INTERVAL '28 days') AS conv_base
            FROM campaigns c
            LEFT JOIN daily_metrics dm ON dm.campaign_id = c.id
            WHERE c.brand_id = %s AND c.status = 'active'
            GROUP BY c.id, c.name
        )
        SELECT *,
            spend_7d   / NULLIF(conv_7d, 0)   AS cpa_7d,
            spend_base / NULLIF(conv_base, 0) AS cpa_base
        FROM agg
        WHERE spend_7d > %s AND conv_7d > 0 AND conv_base > 0
    """,
        (brand_id, CPA_MIN_SPEND_7D),
    )
    end = date.today()
    start = end - timedelta(days=7)
    out: list[LeakCandidate] = []
    for row in cur.fetchall():
        cpa_7d = float(row["cpa_7d"])
        cpa_base = float(row["cpa_base"])
        if cpa_base == 0:
            continue
        ratio = cpa_7d / cpa_base
        if ratio <= CPA_RATIO_MIN:
            continue
        extra_per_conv = cpa_7d - cpa_base
        conv_7d = int(row["conv_7d"])
        impact = extra_per_conv * conv_7d
        out.append(
            LeakCandidate(
                brand_id=brand_id,
                campaign_id=row["campaign_id"],
                leak_type="cpa_creep",
                severity="high" if ratio > 1.40 else "medium",
                dollar_impact=round(impact, 2),
                period_start=start,
                period_end=end,
                facts={
                    "campaign_name": row["campaign_name"],
                    "cpa_7d": round(cpa_7d, 2),
                    "cpa_baseline": round(cpa_base, 2),
                    "cpa_ratio": round(ratio, 2),
                    "spend_7d": float(row["spend_7d"]),
                    "conversions_7d": conv_7d,
                    "extra_cost_per_conversion": round(extra_per_conv, 2),
                },
            )
        )
    return out


def detect_audience_saturation(cur, brand_id: UUID) -> list[LeakCandidate]:
    cur.execute(
        """
        SELECT
            c.id   AS campaign_id,
            c.name AS campaign_name,
            c.audience_id,
            a.name AS audience_name,
            SUM(dm.spend)     AS spend_14d,
            AVG(dm.frequency) AS freq_14d
        FROM campaigns c
        JOIN audiences a       ON a.id = c.audience_id
        JOIN daily_metrics dm  ON dm.campaign_id = c.id
        WHERE c.brand_id = %s
          AND c.status = 'active'
          AND dm.date >= CURRENT_DATE - INTERVAL '14 days'
        GROUP BY c.id, c.name, c.audience_id, a.name
        HAVING AVG(dm.frequency) > %s
    """,
        (brand_id, SAT_FREQ_MIN),
    )
    high_freq = cur.fetchall()
    if len(high_freq) < 2:
        return []
    audience_ids = list({c["audience_id"] for c in high_freq})
    cur.execute(
        """
        SELECT audience_a, audience_b, overlap_pct
        FROM audience_overlap
        WHERE overlap_pct >= %s
          AND audience_a = ANY(%s)
          AND audience_b = ANY(%s)
    """,
        (SAT_OVERLAP_MIN, audience_ids, audience_ids),
    )
    overlap_pairs = cur.fetchall()
    parent: dict[UUID, UUID] = {a: a for a in audience_ids}

    def find(x: UUID) -> UUID:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: UUID, y: UUID) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for pair in overlap_pairs:
        union(pair["audience_a"], pair["audience_b"])
    clusters: dict[UUID, list[dict]] = {}
    for c in high_freq:
        clusters.setdefault(find(c["audience_id"]), []).append(c)
    end = date.today()
    start = end - timedelta(days=14)
    out: list[LeakCandidate] = []
    for cluster in clusters.values():
        if len(cluster) < 2:
            continue
        primary = max(cluster, key=lambda c: float(c["spend_14d"]))
        total_spend = sum(float(c["spend_14d"]) for c in cluster)
        avg_freq = sum(float(c["freq_14d"]) for c in cluster) / len(cluster)
        impact = max(0.0, total_spend * (1.0 - SAT_FREQ_MIN / avg_freq))
        out.append(
            LeakCandidate(
                brand_id=brand_id,
                campaign_id=primary["campaign_id"],
                leak_type="audience_saturation",
                severity="high" if len(cluster) >= 3 else "medium",
                dollar_impact=round(impact, 2),
                period_start=start,
                period_end=end,
                facts={
                    "primary_campaign_name": primary["campaign_name"],
                    "cluster_size": len(cluster),
                    "cluster_campaigns": [
                        {
                            "campaign_id": str(c["campaign_id"]),
                            "campaign_name": c["campaign_name"],
                            "audience_name": c["audience_name"],
                            "frequency_14d": round(float(c["freq_14d"]), 2),
                            "spend_14d": round(float(c["spend_14d"]), 2),
                        }
                        for c in cluster
                    ],
                    "total_cluster_spend_14d": round(total_spend, 2),
                    "average_frequency_14d": round(avg_freq, 2),
                },
            )
        )
    return out


def detect_budget_misallocation(cur, brand_id: UUID) -> list[LeakCandidate]:
    cur.execute(
        """
        WITH perf AS (
            SELECT
                c.id   AS campaign_id,
                c.name AS campaign_name,
                SUM(dm.spend)   AS spend_28d,
                SUM(dm.revenue) AS revenue_28d,
                SUM(dm.revenue) / NULLIF(SUM(dm.spend), 0) AS roas
            FROM campaigns c
            JOIN daily_metrics dm ON dm.campaign_id = c.id
            WHERE c.brand_id = %s AND c.status = 'active'
              AND dm.date >= CURRENT_DATE - INTERVAL '28 days'
            GROUP BY c.id, c.name
        )
        SELECT *,
            NTILE(4) OVER (ORDER BY roas) AS roas_quartile
        FROM perf
        ORDER BY roas
    """,
        (brand_id,),
    )
    rows = cur.fetchall()
    if len(rows) < 4:
        return []
    total_spend = sum(float(r["spend_28d"]) for r in rows)
    if total_spend <= 0:
        return []
    bottom_q = [r for r in rows if r["roas_quartile"] == 1]
    bottom_spend = sum(float(r["spend_28d"]) for r in bottom_q)
    bottom_share = bottom_spend / total_spend
    if bottom_share <= MISALLOC_BOTTOM_SHARE_MIN:
        return []
    sorted_roas = sorted(float(r["roas"] or 0) for r in rows)
    n = len(sorted_roas)
    median_roas = (
        sorted_roas[n // 2]
        if n % 2
        else (sorted_roas[n // 2 - 1] + sorted_roas[n // 2]) / 2
    )
    avg_bottom_roas = sum(float(r["roas"] or 0) for r in bottom_q) / len(bottom_q)
    if median_roas > 0:
        efficiency_gap = max(0.0, (median_roas - avg_bottom_roas) / median_roas)
        impact = bottom_spend * efficiency_gap
    else:
        impact = 0.0
    end = date.today()
    start = end - timedelta(days=28)
    return [
        LeakCandidate(
            brand_id=brand_id,
            campaign_id=None,
            leak_type="budget_misallocation",
            severity="high" if bottom_share > 0.30 else "medium",
            dollar_impact=round(impact, 2),
            period_start=start,
            period_end=end,
            facts={
                "bottom_quartile_share_of_spend": round(bottom_share, 4),
                "total_spend_28d": round(total_spend, 2),
                "bottom_quartile_spend_28d": round(bottom_spend, 2),
                "median_roas": round(median_roas, 3),
                "avg_bottom_quartile_roas": round(avg_bottom_roas, 3),
                "bottom_quartile_campaigns": [
                    {
                        "campaign_id": str(r["campaign_id"]),
                        "campaign_name": r["campaign_name"],
                        "roas_28d": round(float(r["roas"] or 0), 3),
                        "spend_28d": round(float(r["spend_28d"]), 2),
                        "share_of_total_spend": round(
                            float(r["spend_28d"]) / total_spend, 4
                        ),
                    }
                    for r in bottom_q
                ],
            },
        )
    ]


def run_detection(
    conn: psycopg.Connection,
    brand_id: UUID,
    *,
    replace: bool = True,
) -> list[LeakCandidate]:
    with conn.cursor(row_factory=dict_row) as cur:
        zombie = detect_zombie(cur, brand_id)
        fatigue = detect_creative_fatigue(cur, brand_id)
        sat = detect_audience_saturation(cur, brand_id)
        cpa_raw = detect_cpa_creep(cur, brand_id)
        misalloc = detect_budget_misallocation(cur, brand_id)
    suppressed: set[UUID] = set()
    for leak in zombie + fatigue:
        if leak.campaign_id is not None:
            suppressed.add(leak.campaign_id)
    for leak in sat:
        for member in leak.facts.get("cluster_campaigns", []):
            suppressed.add(UUID(member["campaign_id"]))
    cpa = [c for c in cpa_raw if c.campaign_id not in suppressed]
    candidates: list[LeakCandidate] = zombie + fatigue + cpa + sat + misalloc
    with conn.cursor() as cur:
        if replace:
            cur.execute("DELETE FROM leaks WHERE brand_id = %s", (brand_id,))
        for c in candidates:
            cur.execute(
                """INSERT INTO leaks (brand_id, campaign_id, leak_type, severity,
                                      dollar_impact, period_start, period_end, facts)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    c.brand_id,
                    c.campaign_id,
                    c.leak_type,
                    c.severity,
                    c.dollar_impact,
                    c.period_start,
                    c.period_end,
                    Jsonb(c.facts),
                ),
            )
    conn.commit()
    return candidates


def main() -> None:
    print(f"connecting to {DATABASE_URL.split('@')[-1]}\n")
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, name FROM brands ORDER BY created_at")
            brands = cur.fetchall()
        if not brands:
            raise SystemExit("no brands found - run seed.py first")
        for brand in brands:
            print(f"detecting for: {brand['name']}")
            candidates = run_detection(conn, brand["id"])
            counts = Counter(c.leak_type for c in candidates)
            total = sum(c.dollar_impact for c in candidates)
            print(f"  {len(candidates)} leaks, total estimated impact ${total:,.2f}\n")
            for c in sorted(candidates, key=lambda x: -x.dollar_impact):
                where = (
                    c.facts.get("campaign_name")
                    or c.facts.get("primary_campaign_name")
                    or "(brand-level)"
                )
                print(
                    f"  - {c.leak_type:<22} {c.severity:<7} "
                    f"${c.dollar_impact:>12,.2f}  on {where}"
                )
            print()


if __name__ == "__main__":
    main()
