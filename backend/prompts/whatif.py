from __future__ import annotations

import json
from typing import Any, Dict

from models import EventState
from prompts._context import INDIA_CONTEXT

WHATIF_SYSTEM_PROMPT = (
    "You are a predictive event scenario modelling engine for the Indian event market. "
    "You simulate financial and operational ripple effects when hypothetical changes "
    "are applied — always using realistic ₹ (INR) pricing for Bangalore / South India. "
    "You always return strictly valid JSON — no markdown, no prose."
)


def whatif_prompt(state: EventState, delta: Dict[str, Any]) -> str:
    """
    Prompt for simulating a 'What If' scenario.

    Sends a compact state summary + the proposed delta.
    Calculates financial impact with realistic Bangalore vendor pricing.
    Preserves verified vendor amounts; only re-estimates unverified items.
    """
    state_json = state.model_dump_json(indent=2)
    delta_json = json.dumps(delta, indent=2)
    config = state.config

    return f"""{INDIA_CONTEXT}

FULL EVENT STATE:
{state_json}

PROPOSED HYPOTHETICAL CHANGE (DELTA):
{delta_json}

SIMULATION INSTRUCTIONS:

1. SCENARIO SUMMARY ('scenario_summary'):
   Explain in 2–3 sentences what this change means for the event in practical
   Indian / Bangalore terms (e.g., "Adding 50 guests to a Bangalore community hall
   event increases per-plate catering cost from ₹350 to ₹320 at scale, but may
   require a larger hall with ₹25,000 extra rental").

2. FINANCIAL IMPACT ('financial_impact'):
   Itemise every expense category affected (in ₹ INR). Use Bangalore market rates
   from the pricing guide above. Show:
   - What changes (+ or −)
   - New estimated cost per category
   - Net delta (positive = more spend, negative = savings)

3. UPDATED BUDGET ('updated_budget'):
   - If delta specifies a new total_budget or guest_count, treat those as authoritative.
   - Recalculate 'allocated' and 'estimated' for each BudgetItem in ₹.
   - PRESERVE all 'verified' amounts — do not reduce signed contract values.
   - Compute new remaining, overage, is_over_budget.
   - Do NOT introduce Western-only expense categories.

4. AFFECTED TASKS & RECOMMENDATIONS:
   - 'affected_tasks': list of task ids / titles that need amendment.
   - 'recommendations': 2–4 concrete, pragmatic mitigations suited to the Indian /
     Bangalore market (e.g., "Book a larger AC hall in Indiranagar — ₹10,000 more
     but comfortably seats 200 guests").

Return ONLY valid JSON with keys:
  scenario_summary, financial_impact, updated_budget, affected_tasks, recommendations

No markdown. No explanation.
"""
