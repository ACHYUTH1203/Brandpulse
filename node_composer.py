import os

from datetime import datetime, timezone

from typing import Callable

import psycopg

from dotenv import load_dotenv

from psycopg.rows import dict_row

import node_analyzer

import node_enricher

import node_recommender

from state import InsightState, new_state

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set in .env")


def _zombie_card(enriched: dict) -> tuple[str, str, list[dict]]:
    facts = enriched["facts"]
    campaign = facts["campaign_name"]
    title = f"Spend continues on '{campaign}' despite collapsed conversions"
    summary = (
        f"${facts['spend_7d']:,.0f} spent on '{campaign}' over the last 7 days "
        f"with only {facts['conversions_7d']} conversions, despite a historical "
        f"conversion rate of {facts['baseline_cvr'] * 100:.1f}%."
    )
    key_facts = [
        {"label": "Spend (last 7d)", "value": f"${facts['spend_7d']:,.0f}"},
        {"label": "Conversions (last 7d)", "value": str(facts["conversions_7d"])},
        {
            "label": "Historical conversion rate",
            "value": f"{facts['baseline_cvr'] * 100:.1f}%",
        },
        {"label": "Spend (last 28d)", "value": f"${facts['spend_28d']:,.0f}"},
    ]
    return title, summary, key_facts


def _creative_fatigue_card(enriched: dict) -> tuple[str, str, list[dict]]:
    facts = enriched["facts"]
    campaign = facts["campaign_name"]
    title = f"Creative fatigue on '{campaign}'"
    summary = (
        f"CTR on '{facts['creative_name']}' fell from "
        f"{facts['ctr_28d'] * 100:.2f}% (28d) to {facts['ctr_7d'] * 100:.2f}% "
        f"(7d) while frequency climbed to {facts['frequency_7d']:.1f}; "
        f"creative is {facts['creative_age_days']} days old."
    )
    key_facts = [
        {"label": "CTR ratio (7d / 28d)", "value": f"{facts['ctr_ratio']:.2f}x"},
        {"label": "Frequency (7d)", "value": f"{facts['frequency_7d']:.2f}"},
        {"label": "Creative age", "value": f"{facts['creative_age_days']} days"},
        {
            "label": "Est. lost conversions",
            "value": f"{facts['estimated_lost_conversions']:.0f}",
        },
    ]
    return title, summary, key_facts


def _cpa_creep_card(enriched: dict) -> tuple[str, str, list[dict]]:
    facts = enriched["facts"]
    campaign = facts["campaign_name"]
    title = f"Cost per conversion drifting up on '{campaign}'"
    summary = (
        f"CPA on '{campaign}' is ${facts['cpa_7d']:.2f} this week vs "
        f"${facts['cpa_baseline']:.2f} a month ago "
        f"({facts['cpa_ratio']:.2f}x), with ${facts['spend_7d']:,.0f} spent."
    )
    key_facts = [
        {"label": "CPA (last 7d)", "value": f"${facts['cpa_7d']:.2f}"},
        {
            "label": "CPA (28-35 days ago baseline)",
            "value": f"${facts['cpa_baseline']:.2f}",
        },
        {"label": "CPA ratio", "value": f"{facts['cpa_ratio']:.2f}x"},
        {"label": "Spend (last 7d)", "value": f"${facts['spend_7d']:,.0f}"},
    ]
    return title, summary, key_facts


def _audience_saturation_card(enriched: dict) -> tuple[str, str, list[dict]]:
    facts = enriched["facts"]
    members = ", ".join(f"'{c['campaign_name']}'" for c in facts["cluster_campaigns"])
    title = f"Audience saturation across {facts['cluster_size']} overlapping campaigns"
    summary = (
        f"{facts['cluster_size']} campaigns ({members}) are reaching overlapping "
        f"audiences at average frequency {facts['average_frequency_14d']:.2f}, "
        f"with ${facts['total_cluster_spend_14d']:,.0f} spent across them in the "
        f"last 14 days."
    )
    key_facts = [
        {"label": "Cluster size", "value": f"{facts['cluster_size']} campaigns"},
        {
            "label": "Avg frequency (14d)",
            "value": f"{facts['average_frequency_14d']:.2f}",
        },
        {
            "label": "Total cluster spend (14d)",
            "value": f"${facts['total_cluster_spend_14d']:,.0f}",
        },
    ]
    return title, summary, key_facts


def _budget_misallocation_card(enriched: dict) -> tuple[str, str, list[dict]]:
    facts = enriched["facts"]
    n_bottom = len(facts["bottom_quartile_campaigns"])
    title = f"Budget concentrated on {n_bottom} bottom-ROAS campaigns"
    summary = (
        f"Your bottom-quartile campaigns are absorbing "
        f"${facts['bottom_quartile_spend_28d']:,.0f} "
        f"({facts['bottom_quartile_share_of_spend'] * 100:.1f}%) of last-28d spend, "
        f"averaging ROAS {facts['avg_bottom_quartile_roas']:.3f} vs the brand "
        f"median of {facts['median_roas']:.2f}."
    )
    key_facts = [
        {
            "label": "Bottom-quartile share of spend",
            "value": f"{facts['bottom_quartile_share_of_spend'] * 100:.1f}%",
        },
        {
            "label": "Bottom-quartile spend (28d)",
            "value": f"${facts['bottom_quartile_spend_28d']:,.0f}",
        },
        {
            "label": "Avg ROAS in bottom quartile",
            "value": f"{facts['avg_bottom_quartile_roas']:.3f}",
        },
        {"label": "Brand median ROAS", "value": f"{facts['median_roas']:.2f}"},
    ]
    return title, summary, key_facts


CARD_BUILDERS: dict[str, Callable[[dict], tuple[str, str, list[dict]]]] = {
    "zombie": _zombie_card,
    "creative_fatigue": _creative_fatigue_card,
    "cpa_creep": _cpa_creep_card,
    "audience_saturation": _audience_saturation_card,
    "budget_misallocation": _budget_misallocation_card,
}


def compose(state: InsightState) -> dict:
    enriched = state["enriched"]
    leak_type = enriched["leak_type"]
    builder = CARD_BUILDERS.get(leak_type)
    if not builder:
        raise ValueError(f"no card builder registered for leak_type='{leak_type}'")
    title, summary, key_facts = builder(enriched)
    confidence = state.get("confidence", 0.0)
    recs = state.get("recommendations", [])
    needs_review = (confidence < node_recommender.CONFIDENCE_FLOOR) or (len(recs) == 0)
    campaign = enriched.get("campaign")
    return {
        "leak_id": enriched["leak_id"],
        "leak_type": leak_type,
        "title": title,
        "summary": summary,
        "severity": enriched["severity"],
        "dollar_impact": enriched["dollar_impact"],
        "period": enriched["period"],
        "scope": "campaign-level" if campaign else "brand-level",
        "campaign_name": campaign["campaign_name"] if campaign else None,
        "root_cause": state.get("root_cause", ""),
        "confidence": confidence,
        "needs_review": needs_review,
        "recommendations": recs,
        "key_facts": key_facts,
    }


def run(state: InsightState) -> InsightState:
    started = datetime.now(timezone.utc).isoformat()
    final_card = compose(state)
    finished = datetime.now(timezone.utc).isoformat()
    trace_entry = {
        "node": "composer",
        "started_at": started,
        "finished_at": finished,
        "summary": (
            f"composed insight card  severity={final_card['severity']}  "
            f"needs_review={final_card['needs_review']}  "
            f"key_facts={len(final_card['key_facts'])}"
        ),
    }
    return {
        **state,
        "final_card": final_card,
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
        state = node_enricher.run(state, conn)
        print(f"after enricher:    keys = {sorted(state.keys())}")
        print("calling LLM (analyzer)...    ", end="", flush=True)
        state = node_analyzer.run(state)
        print(f"done  confidence {state['confidence']:.2f}")
        print("calling LLM (recommender)... ", end="", flush=True)
        state = node_recommender.run(state)
        skipped = state["trace"][-1].get("skipped", False)
        print("skipped" if skipped else "done")
        print("composing final card...      ", end="", flush=True)
        state = run(state)
        print("done\n")
    card = state["final_card"]
    print("=" * 80)
    print(f"TITLE:        {card['title']}")
    print(f"SEVERITY:     {card['severity']}    (impact ${card['dollar_impact']:,.2f})")
    print(
        f"SCOPE:        {card['scope']}    ({card['campaign_name'] or 'brand-level'})"
    )
    print(f"PERIOD:       {card['period']['start']} -> {card['period']['end']}")
    print(
        f"CONFIDENCE:   {card['confidence']:.2f}    "
        f"needs_review = {card['needs_review']}"
    )
    print()
    print("SUMMARY:")
    print(f"  {card['summary']}")
    print()
    print("ROOT CAUSE (analyzer):")
    print(f"  {card['root_cause']}")
    print()
    print("KEY FACTS:")
    for f in card["key_facts"]:
        print(f"  - {f['label']:<40} {f['value']}")
    print()
    print("RECOMMENDATIONS:")
    if card["recommendations"]:
        for i, rec in enumerate(card["recommendations"], 1):
            print(f"  {i}. {rec['title']}")
            print(f"     action:    {rec['action']}")
            print(f"     rationale: {rec['rationale']}")
            print()
    else:
        print("  (none — needs_review)")
    print("=" * 80)
    print("\nTRACE:")
    for entry in state["trace"]:
        marker = " [skipped]" if entry.get("skipped") else ""
        print(f"  - {entry['node']:<12} {entry['summary']}{marker}")


if __name__ == "__main__":
    main()
