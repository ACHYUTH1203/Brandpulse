import os
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID
import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from state import InsightState, new_state

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set in .env")


def fetch_brand_context(cur, brand_id: UUID) -> dict:
    cur.execute(
        """
        SELECT
            b.name     AS brand_name,
            b.mrr_band,
            COUNT(DISTINCT c.id) FILTER (WHERE c.status = 'active') AS active_campaigns,
            COALESCE(SUM(dm.spend) FILTER (
                WHERE dm.date >= CURRENT_DATE - INTERVAL '28 days'), 0) AS total_spend_28d,
            COALESCE(SUM(dm.revenue) FILTER (
                WHERE dm.date >= CURRENT_DATE - INTERVAL '28 days'), 0) AS total_revenue_28d
        FROM brands b
        LEFT JOIN campaigns c     ON c.brand_id = b.id
        LEFT JOIN daily_metrics dm ON dm.campaign_id = c.id
        WHERE b.id = %s
        GROUP BY b.id, b.name, b.mrr_band
    """,
        (brand_id,),
    )
    row = cur.fetchone()
    if not row:
        return {}
    return {
        "brand_name": row["brand_name"],
        "mrr_band": row["mrr_band"],
        "active_campaigns": int(row["active_campaigns"] or 0),
        "total_spend_28d": round(float(row["total_spend_28d"]), 2),
        "total_revenue_28d": round(float(row["total_revenue_28d"]), 2),
    }


def fetch_campaign_context(cur, campaign_id: UUID) -> Optional[dict]:
    cur.execute(
        """
        SELECT
            c.name      AS campaign_name,
            c.objective,
            c.daily_budget,
            c.started_at,
            a.name      AS audience_name,
            a.type      AS audience_type,
            a.size_estimate,
            cr.name     AS creative_name,
            cr.creative_type,
            cr.launched_at AS creative_launched_at,
            (CURRENT_DATE - cr.launched_at)::int AS creative_age_days
        FROM campaigns c
        LEFT JOIN audiences a  ON a.id  = c.audience_id
        LEFT JOIN creatives cr ON cr.id = c.creative_id
        WHERE c.id = %s
    """,
        (campaign_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "campaign_name": row["campaign_name"],
        "objective": row["objective"],
        "daily_budget": float(row["daily_budget"] or 0),
        "started_at": row["started_at"].isoformat() if row["started_at"] else None,
        "audience_name": row["audience_name"],
        "audience_type": row["audience_type"],
        "audience_size": int(row["size_estimate"] or 0),
        "creative_name": row["creative_name"],
        "creative_type": row["creative_type"],
        "creative_launched_at": row["creative_launched_at"].isoformat()
        if row["creative_launched_at"]
        else None,
        "creative_age_days": int(row["creative_age_days"] or 0),
    }


def fetch_daily_trend(cur, campaign_id: UUID, days: int = 28) -> list[dict]:
    cur.execute(
        f"""
        SELECT date, spend, impressions, clicks, conversions, revenue, frequency
        FROM daily_metrics
        WHERE campaign_id = %s
          AND date >= CURRENT_DATE - INTERVAL '{int(days)} days'
        ORDER BY date
    """,
        (campaign_id,),
    )
    return [
        {
            "date": r["date"].isoformat(),
            "spend": float(r["spend"]),
            "impressions": int(r["impressions"]),
            "clicks": int(r["clicks"]),
            "conversions": int(r["conversions"]),
            "revenue": float(r["revenue"]),
            "frequency": float(r["frequency"]),
        }
        for r in cur.fetchall()
    ]


def fetch_top_performers(cur, brand_id: UUID, limit: int = 3) -> list[dict]:
    cur.execute(
        """
        SELECT
            c.name,
            SUM(dm.spend)   AS spend_28d,
            SUM(dm.revenue) AS revenue_28d,
            SUM(dm.revenue) / NULLIF(SUM(dm.spend), 0) AS roas
        FROM campaigns c
        JOIN daily_metrics dm ON dm.campaign_id = c.id
        WHERE c.brand_id = %s AND c.status = 'active'
          AND dm.date >= CURRENT_DATE - INTERVAL '28 days'
        GROUP BY c.id, c.name
        ORDER BY roas DESC NULLS LAST
        LIMIT %s
    """,
        (brand_id, limit),
    )
    return [
        {
            "campaign_name": r["name"],
            "roas_28d": round(float(r["roas"] or 0), 3),
            "spend_28d": round(float(r["spend_28d"]), 2),
            "revenue_28d": round(float(r["revenue_28d"]), 2),
        }
        for r in cur.fetchall()
    ]


def enrich_leak(conn: psycopg.Connection, leak: dict) -> dict:
    with conn.cursor(row_factory=dict_row) as cur:
        brand_ctx = fetch_brand_context(cur, leak["brand_id"])
        campaign_ctx: Optional[dict] = None
        daily_trend: list[dict] = []
        if leak.get("campaign_id"):
            campaign_ctx = fetch_campaign_context(cur, leak["campaign_id"])
            daily_trend = fetch_daily_trend(cur, leak["campaign_id"], days=28)
        extras: dict[str, Any] = {}
        if leak["leak_type"] == "budget_misallocation":
            extras["top_performers"] = fetch_top_performers(
                cur, leak["brand_id"], limit=3
            )
    return {
        "leak_id": str(leak["id"]),
        "leak_type": leak["leak_type"],
        "severity": leak["severity"],
        "dollar_impact": float(leak["dollar_impact"]),
        "period": {
            "start": leak["period_start"].isoformat(),
            "end": leak["period_end"].isoformat(),
        },
        "facts": leak["facts"],
        "brand": brand_ctx,
        "campaign": campaign_ctx,
        "daily_trend_28d": daily_trend,
        "extras": extras,
    }


def run(state: InsightState, conn: psycopg.Connection) -> InsightState:
    leak = state["leak"]
    started = datetime.now(timezone.utc).isoformat()
    enriched = enrich_leak(conn, leak)
    finished = datetime.now(timezone.utc).isoformat()
    trace_entry = {
        "node": "enricher",
        "started_at": started,
        "finished_at": finished,
        "summary": (
            f"enriched {leak['leak_type']} leak with brand + "
            f"{'campaign + 28d trend' if leak.get('campaign_id') else 'top-performers'} context"
        ),
    }
    return {
        **state,
        "enriched": enriched,
        "trace": (state.get("trace") or []) + [trace_entry],
    }


def main() -> None:
    print(f"connecting to {DATABASE_URL.split('@')[-1]}\n")
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM leaks ORDER BY dollar_impact DESC LIMIT 1")
            leak = cur.fetchone()
        if not leak:
            raise SystemExit("no leaks found - run detection.py first")
        state = new_state(leak)
        print(f"BEFORE enricher — state keys: {sorted(state.keys())}\n")
        state = run(state, conn)
    print(f"AFTER enricher  — state keys: {sorted(state.keys())}\n")
    enriched = state["enriched"]
    print("enriched summary:")
    print(f"  leak_type        {enriched['leak_type']}")
    print(f"  dollar_impact    ${enriched['dollar_impact']:,.2f}")
    print(
        f"  brand            {enriched['brand']['brand_name']}  "
        f"({enriched['brand']['active_campaigns']} active campaigns, "
        f"${enriched['brand']['total_spend_28d']:,.0f} 28d spend)"
    )
    if enriched["campaign"]:
        print(
            f"  campaign         {enriched['campaign']['campaign_name']}  "
            f"(audience: {enriched['campaign']['audience_name']}, "
            f"creative: {enriched['campaign']['creative_name']}, "
            f"age {enriched['campaign']['creative_age_days']}d)"
        )
    else:
        print(f"  campaign         (brand-level — no specific campaign)")
    print(f"  daily_trend_28d  {len(enriched['daily_trend_28d'])} rows")
    print(f"  extras           {list(enriched['extras'].keys()) or '(none)'}")
    print("\ntrace:")
    for entry in state["trace"]:
        print(f"  - {entry['node']:<12} {entry['summary']}")


if __name__ == "__main__":
    main()
