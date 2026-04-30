import os

from datetime import datetime, timezone

from typing import Optional

import psycopg

from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, SystemMessage

from langchain_openai import ChatOpenAI

from psycopg.rows import dict_row

from pydantic import BaseModel, Field

import node_analyzer

import node_enricher

from state import InsightState, new_state

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DATABASE_URL:
    raise SystemExit("DATABASE_URL not set in .env")

if not OPENAI_API_KEY:
    raise SystemExit("OPENAI_API_KEY not set in .env")

CONFIDENCE_FLOOR = 0.6


class Recommendation(BaseModel):
    title: str = Field(
        ...,
        min_length=4,
        max_length=80,
        description=(
            "Short verb-led label, 4-8 words, no trailing punctuation. "
            "Example: 'Pause and refresh creative'."
        ),
    )
    action: str = Field(
        ...,
        description=(
            "1-2 sentence specific instruction. Reference campaign / audience "
            "names from the facts. Use hedged language ('consider', 'as a "
            "first step'). Prefer reversible actions."
        ),
    )
    rationale: str = Field(
        ...,
        description=(
            "1 sentence explaining WHY this helps, citing a specific number "
            "from the facts."
        ),
    )


class RecommenderOutput(BaseModel):
    recommendations: list[Recommendation] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Exactly two recommendations. Different purposes — see system prompt.",
    )


SYSTEM_PROMPT = """You are a careful analytics assistant for a D2C e-commerce founder.

You have just received a detected leak in the brand's ad-performance data and
a root-cause hypothesis written by an upstream analyzer. Your job is to write
EXACTLY 2 next-step recommendations the founder can act on this week.

THE FOUNDER'S CONTEXT:
They run a $1M-$20M D2C brand. They have 30 minutes today. They are skeptical
of dashboards that just say "optimize" — they need concrete, scoped actions.
They will personally execute these in Meta Ads Manager. They distrust AI that
sounds certain. They have been burned by tools that said "pause this!" and
then it turned out to be a tracking issue.

STYLE RULES (mandatory):
1. CONCRETE and SCOPED. Always reference a specific campaign, audience, or
   creative by name. Never say "optimize" / "review strategy" / "monitor
   closely" — those are useless words.
2. HEDGED tone. Use "consider", "as a first step", "you might want to",
   "before scaling further". Never command ("Pause this now!"). Phrasing
   should sound like a senior analyst making a suggestion.
3. REVERSIBLE before destructive. Prefer "pause for 3 days and observe"
   over "kill the campaign". Prefer "test 2 new creatives at $50/day"
   over "rebuild your creative strategy".
4. EACH RECOMMENDATION SERVES A DIFFERENT PURPOSE. Default pattern:
     - Recommendation 1: TACTICAL — something to do today that contains
       the bleed (pause, cap budget, swap creative, consolidate).
     - Recommendation 2: DIAGNOSTIC — something to investigate before
       making bigger decisions (check attribution, audit overlap, look at
       landing page bounce, compare to a peer campaign).
   Do NOT make both recommendations the same kind.
5. CITE SPECIFIC NUMBERS from the facts in the rationale. ("$3,058 over
   the past 7 days", "CTR fell from 1.4% to 0.5%", "frequency reached 5.34")
6. NO greetings, NO "I am an AI", NO bulleted lists inside the action text.

DOMAIN HEURISTICS BY LEAK TYPE (use as a starting point, not a script):
- ZOMBIE: pause the campaign / verify attribution / check for tracking break.
- CREATIVE_FATIGUE: refresh creative with 2-3 fresh variants / drop
  frequency cap / pause and let audience cool off.
- CPA_CREEP: investigate audience exhaustion / lower bid or budget / try
  narrower targeting.
- AUDIENCE_SATURATION: consolidate the cluster (pause all but the highest-
  ROAS one) / refresh the seed audience / build new lookalikes.
- BUDGET_MISALLOCATION: cap bottom-quartile campaigns / reallocate to the
  named top performers in the context / set a stricter ROAS floor.

OUTPUT:
Return ONLY structured JSON: { recommendations: [Recommendation, Recommendation] }
where each Recommendation has { title, action, rationale }."""


def format_input_for_llm(enriched: dict, root_cause: str) -> str:
    base = node_analyzer.format_leak_for_llm(enriched)
    return base + (
        "\n\nUPSTREAM ANALYZER HYPOTHESIS (treat as your starting point, "
        "not as ground truth):\n"
        f"  {root_cause}"
    )


_DEFAULT_LLM: Optional[ChatOpenAI] = None


def _get_llm() -> ChatOpenAI:
    global _DEFAULT_LLM
    if _DEFAULT_LLM is None:
        _DEFAULT_LLM = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    return _DEFAULT_LLM


def recommend(
    enriched: dict,
    root_cause: str,
    llm: Optional[ChatOpenAI] = None,
) -> RecommenderOutput:
    if llm is None:
        llm = _get_llm()
    structured = llm.with_structured_output(RecommenderOutput)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=format_input_for_llm(enriched, root_cause)),
    ]
    return structured.invoke(messages)


def run(state: InsightState, llm: Optional[ChatOpenAI] = None) -> InsightState:
    started = datetime.now(timezone.utc).isoformat()
    confidence = state.get("confidence", 0.0)
    if confidence < CONFIDENCE_FLOOR:
        finished = datetime.now(timezone.utc).isoformat()
        trace_entry = {
            "node": "recommender",
            "started_at": started,
            "finished_at": finished,
            "summary": (
                f"skipped — confidence {confidence:.2f} below floor "
                f"{CONFIDENCE_FLOOR} (insight will be tagged 'needs review')"
            ),
            "skipped": True,
        }
        return {
            **state,
            "trace": (state.get("trace") or []) + [trace_entry],
        }
    output = recommend(state["enriched"], state["root_cause"], llm=llm)
    finished = datetime.now(timezone.utc).isoformat()
    recs_as_dicts = [r.model_dump() for r in output.recommendations]
    trace_entry = {
        "node": "recommender",
        "started_at": started,
        "finished_at": finished,
        "summary": f"generated {len(recs_as_dicts)} recommendations",
        "model": "gpt-4o-mini",
    }
    return {
        **state,
        "recommendations": recs_as_dicts,
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
        print("calling LLM (analyzer)... ", end="", flush=True)
        state = node_analyzer.run(state)
        print(f"done — confidence {state['confidence']:.2f}")
        print("calling LLM (recommender)... ", end="", flush=True)
        state = run(state)
        skipped = state["trace"][-1].get("skipped", False)
        print("skipped" if skipped else "done")
    print(f"\nfinal state keys = {sorted(state.keys())}\n")
    print("=" * 72)
    print(
        f"LEAK         {state['enriched']['leak_type']}  "
        f"${state['enriched']['dollar_impact']:,.2f}"
    )
    print(f"CONFIDENCE   {state['confidence']:.2f}")
    print()
    print("ROOT CAUSE:")
    print(f"  {state['root_cause']}")
    print()
    print("RECOMMENDATIONS:")
    if "recommendations" in state:
        for i, rec in enumerate(state["recommendations"], 1):
            print(f"  {i}. {rec['title']}")
            print(f"     action:    {rec['action']}")
            print(f"     rationale: {rec['rationale']}")
            print()
    else:
        print("  (skipped — confidence below floor)")
    print("=" * 72)
    print("\nTRACE:")
    for entry in state["trace"]:
        marker = " [skipped]" if entry.get("skipped") else ""
        print(f"  - {entry['node']:<12} {entry['summary']}{marker}")


if __name__ == "__main__":
    main()
