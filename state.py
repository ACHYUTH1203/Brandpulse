from typing import Any, TypedDict


class InsightState(TypedDict, total=False):
    leak: dict
    enriched: dict
    root_cause: str
    confidence: float
    recommendations: list[dict]
    final_card: dict
    trace: list[dict]


def new_state(leak: dict) -> InsightState:
    return {"leak": leak, "trace": []}
