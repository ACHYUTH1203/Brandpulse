import os

from pathlib import Path

import psycopg

from dotenv import load_dotenv

from langgraph.graph import END, START, StateGraph

from psycopg.rows import dict_row

from psycopg.types.json import Jsonb

import node_analyzer

import node_composer

import node_enricher

import node_recommender

from state import InsightState, new_state

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set in .env")

if not OPENAI_API_KEY:
    raise SystemExit("OPENAI_API_KEY not set in .env")

LLM_MODEL_NAME = "gpt-4o-mini"

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _route_after_analyzer(state: InsightState) -> str:
    return (
        "recommender"
        if state.get("confidence", 0.0) >= node_recommender.CONFIDENCE_FLOOR
        else "composer"
    )


def build_graph(conn: psycopg.Connection):
    def enricher_step(state: InsightState) -> InsightState:
        return node_enricher.run(state, conn)

    def analyzer_step(state: InsightState) -> InsightState:
        return node_analyzer.run(state)

    def recommender_step(state: InsightState) -> InsightState:
        return node_recommender.run(state)

    def composer_step(state: InsightState) -> InsightState:
        return node_composer.run(state)

    graph = StateGraph(InsightState)
    graph.add_node("enricher", enricher_step)
    graph.add_node("analyzer", analyzer_step)
    graph.add_node("recommender", recommender_step)
    graph.add_node("composer", composer_step)
    graph.add_edge(START, "enricher")
    graph.add_edge("enricher", "analyzer")
    graph.add_conditional_edges(
        "analyzer",
        _route_after_analyzer,
        {"recommender": "recommender", "composer": "composer"},
    )
    graph.add_edge("recommender", "composer")
    graph.add_edge("composer", END)
    return graph.compile()


def ensure_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()


def persist_insight(conn: psycopg.Connection, state: InsightState) -> None:
    leak_id = state["leak"]["id"]
    card = state["final_card"]
    with conn.cursor() as cur:
        cur.execute("DELETE FROM insights WHERE leak_id = %s", (leak_id,))
        cur.execute(
            """INSERT INTO insights
                 (leak_id, summary, root_cause, recommendations, confidence,
                  llm_model, trace, card)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                leak_id,
                card["summary"],
                state.get("root_cause", ""),
                Jsonb(state.get("recommendations", [])),
                state.get("confidence", 0.0),
                LLM_MODEL_NAME,
                Jsonb(state.get("trace", [])),
                Jsonb(card),
            ),
        )
    conn.commit()


def process_all_leaks(conn: psycopg.Connection) -> dict:
    graph = build_graph(conn)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT * FROM leaks ORDER BY dollar_impact DESC")
        leaks = cur.fetchall()
    if not leaks:
        raise SystemExit("no leaks found - run detection.py first")
    print(f"processing {len(leaks)} leaks through the workflow:\n")
    n_high_conf = 0
    n_review = 0
    total_impact = 0.0
    for i, leak in enumerate(leaks, 1):
        prefix = (
            f"  [{i}/{len(leaks)}] {leak['leak_type']:<22} "
            f"${float(leak['dollar_impact']):>10,.2f}  "
        )
        print(prefix, end="", flush=True)
        try:
            final_state: InsightState = graph.invoke(new_state(leak))
            persist_insight(conn, final_state)
            conf = final_state.get("confidence", 0.0)
            n_recs = len(final_state.get("recommendations", []))
            needs_review = final_state["final_card"]["needs_review"]
            tag = "needs_review" if needs_review else "ok"
            print(f"conf={conf:.2f}  recs={n_recs}  [{tag}]")
            if needs_review:
                n_review += 1
            else:
                n_high_conf += 1
            total_impact += float(leak["dollar_impact"])
        except Exception as exc:
            print(f"FAILED: {exc}")
    return {
        "total_leaks": len(leaks),
        "high_confidence": n_high_conf,
        "needs_review": n_review,
        "total_impact": total_impact,
    }


def print_insights_summary(conn: psycopg.Connection) -> None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                l.leak_type,
                l.severity,
                l.dollar_impact,
                i.confidence,
                jsonb_array_length(i.recommendations) AS n_recs,
                i.card->>'title'    AS title,
                i.card->>'summary'  AS summary,
                (i.card->>'needs_review')::boolean AS needs_review
            FROM leaks l
            JOIN insights i ON i.leak_id = l.id
            ORDER BY l.dollar_impact DESC
        """)
        rows = cur.fetchall()
    print("\n" + "=" * 80)
    print(f"INSIGHTS WRITTEN ({len(rows)} rows in `insights`):")
    print("=" * 80)
    for r in rows:
        review = "  [needs review]" if r["needs_review"] else ""
        print(
            f"\n  {r['leak_type']:<22} {r['severity']:<7} "
            f"${float(r['dollar_impact']):>10,.2f}   "
            f"conf={float(r['confidence']):.2f}  recs={r['n_recs']}{review}"
        )
        print(f"  TITLE:   {r['title']}")
        print(f"  SUMMARY: {r['summary']}")
    print("\n" + "=" * 80)


def main() -> None:
    print(f"connecting to {DATABASE_URL.split('@')[-1]}\n")
    with psycopg.connect(DATABASE_URL) as conn:
        ensure_schema(conn)
        summary = process_all_leaks(conn)
        print(
            f"\n{summary['total_leaks']} leaks processed   "
            f"high-conf={summary['high_confidence']}   "
            f"needs_review={summary['needs_review']}   "
            f"total_impact=${summary['total_impact']:,.2f}"
        )
        print_insights_summary(conn)


if __name__ == "__main__":
    main()
