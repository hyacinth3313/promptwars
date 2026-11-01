from __future__ import annotations

import json
from typing import Any, Dict

from models import EventState

WHATIF_SYSTEM_PROMPT = (
    "You simulate event budget scenarios using realistic INR pricing for Bangalore / South India. "
    "Return only valid JSON matching the supplied schema."
)


def whatif_prompt(state: EventState, delta: Dict[str, Any]) -> str:
    """Send only baseline totals, category allocations, and the tested changes."""
    context = {
        "total_budget": state.config.total_budget,
        "guest_count": state.config.guest_count,
        "event_date": state.config.event_date.isoformat(),
        "budget_items": [
            {"category": item.category, "allocated": item.allocated}
            for item in state.budget.items
        ],
        "delta": {
            key: value for key, value in delta.items()
            if key in {"budget_change", "guest_count_delta", "new_date", "total_budget", "guest_count"}
        },
    }
    return (
        "SCENARIO CONTEXT:\n"
        + json.dumps(context, separators=(",", ":"), ensure_ascii=False)
        + "\n\nApply budget_change/guest_count_delta relative to the baseline; "
        "total_budget/guest_count in delta are absolute overrides; new_date replaces event_date. "
        "Estimate costs from allocations and the delta. Keep category names. "
        "Return the required JSON schema, including brief scenario_summary, financial_impact "
        "in INR, updated_budget, and 2-4 recommendations. Set verified=null. "
        "Return affected_tasks=[]: the server shifts task dates and preserves confirmed costs."
    )
