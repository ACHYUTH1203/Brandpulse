import json

import os

from datetime import datetime, timezone

from typing import Optional

import psycopg

from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, SystemMessage

from langchain_openai import ChatOpenAI

from psycopg.rows import dict_row

from pydantic import BaseModel, Field

import node_enricher

from state import InsightState, new_state

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set in .env")

if not OPENAI_API_KEY:
    raise SystemExit("OPENAI_API_KEY not set in .env")


class AnalyzerOutput(BaseModel):
    hypothesis: str = Field(
        ...,
        description=(
            "1-2 sentence cautious root-cause hypothesis. MUST use hedged "
            "language ('may be', 'appears to be', 'is consistent with'). "
            "Cite specific numbers from the facts. Never assert certainty."
        ),
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "How well the facts support the hypothesis. 0.8-1.0 = facts "
            "strongly point to one cause; 0.5-0.7 = plausible but ambiguous; "
            "below 0.5 = facts are unclear, do not recommend action."
        ),
    )


SYSTEM_PROMPT = """You are a careful analytics assistant for a D2C e-commerce founder.

You will be given a "leak" detected in the brand's ad-performance data. Your
job is to write a ROOT-CAUSE HYPOTHESIS explaining what may have caused it.

STYLE RULES (mandatory):
1. 1-2 sentences. No more.
2. Use HEDGED language: "may be", "appears to be", "is consistent with",
   "looks like", "suggests". NEVER assert a cause as certain.
3. Cite the specific numbers from the facts so the founder can verify.
4. Sound like a thoughtful analyst, not an AI assistant. No greetings,
   no "I am an AI" caveats, no bulleted lists.
5. Refer to the campaign/brand by name when one is available.

CONFIDENCE RUBRIC:
- 0.8-1.0: Facts strongly point to one cause. Example: spend held steady
  while conversions collapsed from a healthy baseline -> classic zombie.
- 0.5-0.7: Plausible single cause but other explanations are reasonable.
- 0.0-0.4: Facts are ambiguous; we should NOT recommend specific action.

Return ONLY structured JSON with fields {hypothesis, confidence}."""


def format_leak_for_llm(enriched: dict) -> str:
    brand = enriched["brand"]
    campaign = enriched.get("campaign")
    lines = [
        f"LEAK TYPE:        {enriched['leak_type']}",
        f"ESTIMATED IMPACT: ${enriched['dollar_impact']:,.2f}",
        f"PERIOD:           {enriched['period']['start']} to {enriched['period']['end']}",
        f"BRAND:            {brand['brand_name']}  "
        f"({brand['active_campaigns']} active campaigns, "
        f"${brand['total_spend_28d']:,.0f} 28d spend, "
        f"${brand['total_revenue_28d']:,.0f} 28d revenue)",
    ]
    if campaign:
        lines += [
            f"CAMPAIGN:         {campaign['campaign_name']}",
            f"  audience:       {campaign['audience_name']} ({campaign['audience_type']})",
            f"  creative:       {campaign['creative_name']} "
            f"({campaign['creative_age_days']}d old)",
            f"  daily budget:   ${campaign['daily_budget']:,.0f}",
        ]
    lines += ["", "FULL CONTEXT (JSON):", json.dumps(enriched, indent=2, default=str)]
    return "\n".join(lines)


_DEFAULT_LLM: Optional[ChatOpenAI] = None


def _get_llm() -> ChatOpenAI:
    global _DEFAULT_LLM
    if _DEFAULT_LLM is None:
        _DEFAULT_LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
    return _DEFAULT_LLM


def analyze(enriched: dict, llm: Optional[ChatOpenAI] = None) -> AnalyzerOutput:
    if llm is None:
        llm = _get_llm()
    structured = llm.with_structured_output(AnalyzerOutput)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=format_leak_for_llm(enriched)),
    ]
    return structured.invoke(messages)


def run(state: InsightState, llm: Optional[ChatOpenAI] = None) -> InsightState:
    started = datetime.now(timezone.utc).isoformat()
    output = analyze(state["enriched"], llm=llm)
    finished = datetime.now(timezone.utc).isoformat()
    trace_entry = {
        "node": "analyzer",
        "started_at": started,
        "finished_at": finished,
        "summary": f"hypothesized root cause (confidence {output.confidence:.2f})",
        "model": "gpt-4o-mini",
    }
    return {
        **state,
        "root_cause": output.hypothesis,
        "confidence": output.confidence,
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
        print(f"after enricher: keys = {sorted(state.keys())}")
        print("calling LLM (analyzer)... ", end="", flush=True)
        state = run(state)
        print("done\n")
    print(f"after analyzer: keys = {sorted(state.keys())}\n")
    print("=" * 70)
    print(
        f"LEAK         {state['enriched']['leak_type']}  "
        f"${state['enriched']['dollar_impact']:,.2f}"
    )
    print(f"CONFIDENCE   {state['confidence']:.2f}")
    print()
    print("ROOT CAUSE:")
    print(f"  {state['root_cause']}")
    print("=" * 70)
    print("\nTRACE:")
    for entry in state["trace"]:
        print(f"  - {entry['node']:<12} {entry['summary']}")


if __name__ == "__main__":
    main()
