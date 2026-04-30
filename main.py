import os
from contextlib import asynccontextmanager
from typing import Any, Literal, Optional
from uuid import UUID
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pydantic import BaseModel, Field

import detection
import workflow

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set in .env")

db_pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=2,
    max_size=10,
    open=False,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_pool.open()
    try:
        yield
    finally:
        db_pool.close()


app = FastAPI(
    title="BrandPulse API",
    description="Detects ad-spend leaks for D2C brands and explains them via LangGraph.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    db: str


class BrandSummary(BaseModel):
    id: str
    name: str
    mrr_band: Optional[str]
    active_campaigns: int


class LeakListItem(BaseModel):
    leak_id: str
    leak_type: str
    severity: str
    dollar_impact: float
    period_start: str
    period_end: str
    campaign_name: Optional[str]
    title: Optional[str]
    summary: Optional[str]
    confidence: Optional[float]
    has_recommendations: bool


class BrandOverview(BaseModel):
    brand_id: str
    brand_name: str
    total_spend_28d: float
    total_revenue_28d: float
    total_leak_impact: float
    leak_count: int
    active_campaigns: int
    top_leaks: list[LeakListItem]
    spend_trend_30d: list[dict[str, Any]]


class LeakListResponse(BaseModel):
    total: int
    leaks: list[LeakListItem]


class LeakDetailResponse(BaseModel):
    leak: dict[str, Any]
    insight: Optional[dict[str, Any]]


class CampaignDetailResponse(BaseModel):
    campaign: dict[str, Any]
    daily_metrics_90d: list[dict[str, Any]]
    leaks: list[LeakListItem]


class CampaignListItem(BaseModel):
    id: str
    name: str
    objective: Optional[str]
    status: str
    daily_budget: float
    audience_name: Optional[str]
    creative_name: Optional[str]
    creative_age_days: int
    spend_28d: float
    revenue_28d: float
    roas_28d: Optional[float]
    leak_count: int


class InjectLeakRequest(BaseModel):
    scenario: Literal["zombie", "fatigue", "cpa_spike"] = Field(
        ..., description="What kind of leak to plant in the campaign's recent data."
    )
    campaign_id: Optional[str] = Field(
        None,
        description="Target campaign UUID. If omitted, picks a healthy random one.",
    )
    days_affected: int = Field(
        7, ge=3, le=21, description="How many recent days to modify."
    )


class InjectLeakResponse(BaseModel):
    status: str
    scenario: str
    campaign_id: str
    campaign_name: str
    days_affected: int
    rows_modified: int


class RunDetectionResponse(BaseModel):
    brand_id: str
    leaks_detected: int
    by_type: dict[str, int]
    total_estimated_impact: float


class RunWorkflowResponse(BaseModel):
    total_leaks: int
    high_confidence: int
    needs_review: int
    total_impact: float


@app.get("/", include_in_schema=False)
def root():
    return {"app": "BrandPulse API", "docs": "/docs", "health": "/health"}


@app.post("/admin/bootstrap")
def bootstrap():
    import psycopg

    import seed

    with psycopg.connect(DATABASE_URL) as conn:
        seed.apply_schema(conn)
        seed.seed_data(conn)

    with db_pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id FROM brands LIMIT 1")
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=500, detail="seed produced no brand")
        brand_id = row["id"]

    with db_pool.connection() as conn:
        candidates = detection.run_detection(conn, brand_id)

    with db_pool.connection() as conn:
        workflow.ensure_schema(conn)
        summary = workflow.process_all_leaks(conn)

    return {
        "status": "bootstrapped",
        "leaks_detected": len(candidates),
        "workflow": summary,
    }


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        with db_pool.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"db unreachable: {exc}")
    return HealthResponse(status="ok", db="connected")


@app.get("/brands", response_model=list[BrandSummary])
def list_brands() -> list[BrandSummary]:
    with db_pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                b.id, b.name, b.mrr_band,
                COUNT(DISTINCT c.id) FILTER (WHERE c.status = 'active') AS active_campaigns
            FROM brands b
            LEFT JOIN campaigns c ON c.brand_id = b.id
            GROUP BY b.id
            ORDER BY b.created_at
        """)
        return [
            BrandSummary(
                id=str(r["id"]),
                name=r["name"],
                mrr_band=r["mrr_band"],
                active_campaigns=int(r["active_campaigns"]),
            )
            for r in cur.fetchall()
        ]


@app.get("/brands/{brand_id}/overview", response_model=BrandOverview)
def brand_overview(brand_id: str) -> BrandOverview:
    try:
        bid = UUID(brand_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid brand_id")
    with db_pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                b.name AS brand_name,
                COUNT(DISTINCT c.id) FILTER (WHERE c.status = 'active') AS active_campaigns,
                COALESCE(SUM(dm.spend) FILTER (
                    WHERE dm.date >= CURRENT_DATE - INTERVAL '28 days'), 0) AS total_spend_28d,
                COALESCE(SUM(dm.revenue) FILTER (
                    WHERE dm.date >= CURRENT_DATE - INTERVAL '28 days'), 0) AS total_revenue_28d
            FROM brands b
            LEFT JOIN campaigns c     ON c.brand_id = b.id
            LEFT JOIN daily_metrics dm ON dm.campaign_id = c.id
            WHERE b.id = %s
            GROUP BY b.id, b.name
        """,
            (bid,),
        )
        bb = cur.fetchone()
        if not bb:
            raise HTTPException(status_code=404, detail="brand not found")
        cur.execute(
            """
            SELECT COUNT(*) AS n, COALESCE(SUM(dollar_impact), 0) AS total_impact
            FROM leaks WHERE brand_id = %s
        """,
            (bid,),
        )
        leaks_row = cur.fetchone()
        cur.execute(
            """
            SELECT
                l.id AS leak_id, l.leak_type, l.severity, l.dollar_impact,
                l.period_start, l.period_end,
                c.name AS campaign_name,
                i.confidence,
                i.card->>'title'   AS title,
                i.card->>'summary' AS summary,
                jsonb_array_length(COALESCE(i.recommendations, '[]'::jsonb)) AS n_recs
            FROM leaks l
            LEFT JOIN campaigns c  ON c.id = l.campaign_id
            LEFT JOIN insights i   ON i.leak_id = l.id
            WHERE l.brand_id = %s
            ORDER BY l.dollar_impact DESC
            LIMIT 3
        """,
            (bid,),
        )
        top_leaks = [_row_to_leak_list_item(r) for r in cur.fetchall()]
        cur.execute(
            """
            SELECT date,
                   COALESCE(SUM(dm.spend), 0)   AS spend,
                   COALESCE(SUM(dm.revenue), 0) AS revenue
            FROM campaigns c
            LEFT JOIN daily_metrics dm ON dm.campaign_id = c.id
            WHERE c.brand_id = %s
              AND dm.date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY dm.date
            ORDER BY dm.date
        """,
            (bid,),
        )
        trend = [
            {
                "date": r["date"].isoformat(),
                "spend": float(r["spend"]),
                "revenue": float(r["revenue"]),
            }
            for r in cur.fetchall()
            if r["date"]
        ]
    return BrandOverview(
        brand_id=str(bid),
        brand_name=bb["brand_name"],
        total_spend_28d=float(bb["total_spend_28d"]),
        total_revenue_28d=float(bb["total_revenue_28d"]),
        total_leak_impact=float(leaks_row["total_impact"]),
        leak_count=int(leaks_row["n"]),
        active_campaigns=int(bb["active_campaigns"]),
        top_leaks=top_leaks,
        spend_trend_30d=trend,
    )


@app.get("/brands/{brand_id}/campaigns", response_model=list[CampaignListItem])
def list_campaigns_for_brand(brand_id: str) -> list[CampaignListItem]:
    try:
        bid = UUID(brand_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid brand_id")
    with db_pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                c.id, c.name, c.objective, c.status, c.daily_budget,
                a.name AS audience_name,
                cr.name AS creative_name,
                COALESCE((CURRENT_DATE - cr.launched_at)::int, 0) AS creative_age_days,
                COALESCE(SUM(dm.spend)   FILTER (
                    WHERE dm.date >= CURRENT_DATE - INTERVAL '28 days'), 0) AS spend_28d,
                COALESCE(SUM(dm.revenue) FILTER (
                    WHERE dm.date >= CURRENT_DATE - INTERVAL '28 days'), 0) AS revenue_28d,
                COUNT(DISTINCT l.id) AS leak_count
            FROM campaigns c
            LEFT JOIN audiences a      ON a.id  = c.audience_id
            LEFT JOIN creatives cr     ON cr.id = c.creative_id
            LEFT JOIN daily_metrics dm ON dm.campaign_id = c.id
            LEFT JOIN leaks l          ON l.campaign_id = c.id
            WHERE c.brand_id = %s
            GROUP BY c.id, a.name, cr.name, cr.launched_at
            ORDER BY SUM(dm.spend) FILTER (
                WHERE dm.date >= CURRENT_DATE - INTERVAL '28 days') DESC NULLS LAST
        """,
            (bid,),
        )
        rows = cur.fetchall()
    out: list[CampaignListItem] = []
    for r in rows:
        spend = float(r["spend_28d"] or 0)
        revenue = float(r["revenue_28d"] or 0)
        out.append(
            CampaignListItem(
                id=str(r["id"]),
                name=r["name"],
                objective=r["objective"],
                status=r["status"],
                daily_budget=float(r["daily_budget"] or 0),
                audience_name=r["audience_name"],
                creative_name=r["creative_name"],
                creative_age_days=int(r["creative_age_days"] or 0),
                spend_28d=round(spend, 2),
                revenue_28d=round(revenue, 2),
                roas_28d=round(revenue / spend, 3) if spend > 0 else None,
                leak_count=int(r["leak_count"] or 0),
            )
        )
    return out


@app.get("/leaks", response_model=LeakListResponse)
def list_leaks(
    brand_id: Optional[str] = None,
    severity: Optional[Literal["low", "medium", "high"]] = None,
    leak_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> LeakListResponse:
    where = ["1 = 1"]
    params: list[Any] = []
    if brand_id:
        where.append("l.brand_id = %s")
        params.append(UUID(brand_id))
    if severity:
        where.append("l.severity = %s")
        params.append(severity)
    if leak_type:
        where.append("l.leak_type = %s")
        params.append(leak_type)
    where_sql = " AND ".join(where)
    with db_pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM leaks l WHERE {where_sql}", params)
        total = int(cur.fetchone()["n"])
        cur.execute(
            f"""
            SELECT
                l.id AS leak_id, l.leak_type, l.severity, l.dollar_impact,
                l.period_start, l.period_end,
                c.name AS campaign_name,
                i.confidence,
                i.card->>'title'   AS title,
                i.card->>'summary' AS summary,
                jsonb_array_length(COALESCE(i.recommendations, '[]'::jsonb)) AS n_recs
            FROM leaks l
            LEFT JOIN campaigns c ON c.id = l.campaign_id
            LEFT JOIN insights i  ON i.leak_id = l.id
            WHERE {where_sql}
            ORDER BY l.dollar_impact DESC
            LIMIT %s OFFSET %s
            """,
            [*params, limit, offset],
        )
        leaks = [_row_to_leak_list_item(r) for r in cur.fetchall()]
    return LeakListResponse(total=total, leaks=leaks)


@app.get("/leaks/{leak_id}", response_model=LeakDetailResponse)
def leak_detail(leak_id: str) -> LeakDetailResponse:
    try:
        lid = UUID(leak_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid leak_id")
    with db_pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                l.id, l.brand_id, l.campaign_id, l.leak_type, l.severity,
                l.dollar_impact, l.detected_at, l.period_start, l.period_end,
                l.facts, l.status,
                c.name AS campaign_name,
                b.name AS brand_name
            FROM leaks l
            LEFT JOIN campaigns c ON c.id = l.campaign_id
            JOIN brands b         ON b.id = l.brand_id
            WHERE l.id = %s
        """,
            (lid,),
        )
        leak_row = cur.fetchone()
        if not leak_row:
            raise HTTPException(status_code=404, detail="leak not found")
        cur.execute(
            """
            SELECT id, summary, root_cause, recommendations, confidence,
                   llm_model, trace, card, created_at
            FROM insights
            WHERE leak_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """,
            (lid,),
        )
        insight_row = cur.fetchone()
    leak_dict = {
        "id": str(leak_row["id"]),
        "brand_id": str(leak_row["brand_id"]),
        "brand_name": leak_row["brand_name"],
        "campaign_id": str(leak_row["campaign_id"])
        if leak_row["campaign_id"]
        else None,
        "campaign_name": leak_row["campaign_name"],
        "leak_type": leak_row["leak_type"],
        "severity": leak_row["severity"],
        "dollar_impact": float(leak_row["dollar_impact"]),
        "detected_at": leak_row["detected_at"].isoformat(),
        "period_start": leak_row["period_start"].isoformat(),
        "period_end": leak_row["period_end"].isoformat(),
        "facts": leak_row["facts"],
        "status": leak_row["status"],
    }
    insight_dict = None
    if insight_row:
        insight_dict = {
            "id": str(insight_row["id"]),
            "summary": insight_row["summary"],
            "root_cause": insight_row["root_cause"],
            "recommendations": insight_row["recommendations"],
            "confidence": float(insight_row["confidence"])
            if insight_row["confidence"] is not None
            else None,
            "llm_model": insight_row["llm_model"],
            "trace": insight_row["trace"],
            "card": insight_row["card"],
            "created_at": insight_row["created_at"].isoformat(),
        }
    return LeakDetailResponse(leak=leak_dict, insight=insight_dict)


@app.get("/campaigns/{campaign_id}", response_model=CampaignDetailResponse)
def campaign_detail(campaign_id: str) -> CampaignDetailResponse:
    try:
        cid = UUID(campaign_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid campaign_id")
    with db_pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT
                c.id, c.name, c.objective, c.status, c.daily_budget, c.started_at,
                a.id AS audience_id, a.name AS audience_name, a.type AS audience_type,
                a.size_estimate,
                cr.id AS creative_id, cr.name AS creative_name, cr.creative_type,
                cr.launched_at AS creative_launched_at,
                (CURRENT_DATE - cr.launched_at)::int AS creative_age_days,
                b.name AS brand_name
            FROM campaigns c
            LEFT JOIN audiences a  ON a.id = c.audience_id
            LEFT JOIN creatives cr ON cr.id = c.creative_id
            JOIN brands b          ON b.id = c.brand_id
            WHERE c.id = %s
        """,
            (cid,),
        )
        c = cur.fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="campaign not found")
        cur.execute(
            """
            SELECT date, spend, impressions, clicks, conversions, revenue, frequency
            FROM daily_metrics
            WHERE campaign_id = %s
              AND date >= CURRENT_DATE - INTERVAL '90 days'
            ORDER BY date
        """,
            (cid,),
        )
        metrics = [
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
        cur.execute(
            """
            SELECT
                l.id AS leak_id, l.leak_type, l.severity, l.dollar_impact,
                l.period_start, l.period_end,
                c.name AS campaign_name,
                i.confidence,
                i.card->>'title'   AS title,
                i.card->>'summary' AS summary,
                jsonb_array_length(COALESCE(i.recommendations, '[]'::jsonb)) AS n_recs
            FROM leaks l
            LEFT JOIN insights i  ON i.leak_id = l.id
            LEFT JOIN campaigns c ON c.id = l.campaign_id
            WHERE l.campaign_id = %s
            ORDER BY l.dollar_impact DESC
        """,
            (cid,),
        )
        leaks = [_row_to_leak_list_item(r) for r in cur.fetchall()]
    campaign_dict = {
        "id": str(c["id"]),
        "name": c["name"],
        "brand_name": c["brand_name"],
        "objective": c["objective"],
        "status": c["status"],
        "daily_budget": float(c["daily_budget"] or 0),
        "started_at": c["started_at"].isoformat() if c["started_at"] else None,
        "audience": {
            "id": str(c["audience_id"]) if c["audience_id"] else None,
            "name": c["audience_name"],
            "type": c["audience_type"],
            "size_estimate": int(c["size_estimate"] or 0),
        },
        "creative": {
            "id": str(c["creative_id"]) if c["creative_id"] else None,
            "name": c["creative_name"],
            "type": c["creative_type"],
            "launched_at": c["creative_launched_at"].isoformat()
            if c["creative_launched_at"]
            else None,
            "age_days": int(c["creative_age_days"] or 0),
        },
    }
    return CampaignDetailResponse(
        campaign=campaign_dict,
        daily_metrics_90d=metrics,
        leaks=leaks,
    )


@app.post("/admin/run-detection/{brand_id}", response_model=RunDetectionResponse)
def run_detection_endpoint(brand_id: str) -> RunDetectionResponse:
    try:
        bid = UUID(brand_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid brand_id")
    with db_pool.connection() as conn:
        candidates = detection.run_detection(conn, bid)
    by_type: dict[str, int] = {}
    total = 0.0
    for c in candidates:
        by_type[c.leak_type] = by_type.get(c.leak_type, 0) + 1
        total += c.dollar_impact
    return RunDetectionResponse(
        brand_id=str(bid),
        leaks_detected=len(candidates),
        by_type=by_type,
        total_estimated_impact=round(total, 2),
    )


@app.post("/admin/run-workflow", response_model=RunWorkflowResponse)
def run_workflow_endpoint() -> RunWorkflowResponse:
    with db_pool.connection() as conn:
        workflow.ensure_schema(conn)
        summary = workflow.process_all_leaks(conn)
    return RunWorkflowResponse(**summary)


@app.post("/admin/refresh/{brand_id}")
def refresh_brand(brand_id: str) -> dict:
    try:
        bid = UUID(brand_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid brand_id")
    with db_pool.connection() as conn:
        candidates = detection.run_detection(conn, bid)
        workflow.ensure_schema(conn)
        wf_summary = workflow.process_all_leaks(conn)
    return {
        "brand_id": str(bid),
        "detection": {
            "leaks_detected": len(candidates),
            "total_impact": round(sum(c.dollar_impact for c in candidates), 2),
        },
        "workflow": wf_summary,
    }


@app.post("/admin/inject-leak", response_model=InjectLeakResponse)
def inject_leak(req: InjectLeakRequest) -> InjectLeakResponse:
    with db_pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        if req.campaign_id:
            cur.execute(
                "SELECT id, name FROM campaigns WHERE id = %s",
                (UUID(req.campaign_id),),
            )
        else:
            cur.execute("""
                SELECT c.id, c.name
                FROM campaigns c
                JOIN daily_metrics dm ON dm.campaign_id = c.id
                WHERE c.status = 'active'
                  AND c.id NOT IN (
                      SELECT campaign_id FROM leaks WHERE campaign_id IS NOT NULL
                  )
                  AND dm.date <  CURRENT_DATE - INTERVAL '14 days'
                  AND dm.date >= CURRENT_DATE - INTERVAL '60 days'
                GROUP BY c.id, c.name
                HAVING SUM(dm.conversions)::numeric
                       / NULLIF(SUM(dm.clicks), 0) >= 0.015
                   AND SUM(dm.spend) > 1000
                ORDER BY random()
                LIMIT 1
            """)
        camp = cur.fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="no eligible campaign")
        cid = camp["id"]
        days = req.days_affected
        if req.scenario == "zombie":
            cur.execute(
                """
                UPDATE daily_metrics
                SET conversions = (random() * 1.5)::int,
                    revenue     = 0
                WHERE campaign_id = %s
                  AND date >= CURRENT_DATE - (INTERVAL '1 day' * %s)
                """,
                (cid, days),
            )
        elif req.scenario == "fatigue":
            cur.execute(
                """
                UPDATE daily_metrics
                SET clicks      = GREATEST(0, (clicks * 0.25)::int),
                    conversions = GREATEST(0, (conversions * 0.25)::int),
                    revenue     = revenue * 0.25,
                    frequency   = LEAST(5.5, frequency + 2.5)
                WHERE campaign_id = %s
                  AND date >= CURRENT_DATE - (INTERVAL '1 day' * %s)
                """,
                (cid, days),
            )
            cur.execute(
                """
                UPDATE creatives
                SET launched_at = CURRENT_DATE - INTERVAL '35 days'
                WHERE id = (SELECT creative_id FROM campaigns WHERE id = %s)
                """,
                (cid,),
            )
        elif req.scenario == "cpa_spike":
            cur.execute(
                """
                UPDATE daily_metrics
                SET conversions = GREATEST(1, (conversions * 0.4)::int),
                    revenue     = revenue * 0.4
                WHERE campaign_id = %s
                  AND date >= CURRENT_DATE - (INTERVAL '1 day' * %s)
                """,
                (cid, days),
            )
        rows_modified = cur.rowcount
        conn.commit()
    return InjectLeakResponse(
        status="ok",
        scenario=req.scenario,
        campaign_id=str(cid),
        campaign_name=camp["name"],
        days_affected=days,
        rows_modified=rows_modified,
    )


def _row_to_leak_list_item(r: dict) -> LeakListItem:
    return LeakListItem(
        leak_id=str(r["leak_id"]),
        leak_type=r["leak_type"],
        severity=r["severity"],
        dollar_impact=float(r["dollar_impact"]),
        period_start=r["period_start"].isoformat(),
        period_end=r["period_end"].isoformat(),
        campaign_name=r.get("campaign_name"),
        title=r.get("title"),
        summary=r.get("summary"),
        confidence=float(r["confidence"]) if r.get("confidence") is not None else None,
        has_recommendations=int(r.get("n_recs") or 0) > 0,
    )
