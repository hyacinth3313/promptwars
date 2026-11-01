from __future__ import annotations

from models import EventState
from prompts._context import INDIA_CONTEXT

TRADEOFF_SYSTEM_PROMPT = (
    "You are an expert Indian event cost optimisation advisor specialising in the "
    "Bangalore market. You identify concrete, realistic trade-off options that resolve "
    "budget overages while preserving cultural authenticity, guest experience, and the "
    "host's core priorities. All savings must be grounded in real Bangalore vendor pricing. "
    "You always return strictly valid JSON — no markdown, no prose."
)


def tradeoff_prompt(state: EventState, overage: float) -> str:
    """
    Prompt for generating 2–3 concrete trade-off packages when over budget.

    Rules:
    - All suggestions must be India / Bangalore appropriate.
    - Do NOT suggest cuts to mandatory Indian cultural elements (mandap for weddings,
      birthday cake for birthdays, etc.).
    - Do NOT introduce new Western-only categories as replacements.
    - Savings must be grounded in real Bangalore vendor market rates.
    - Respect verified vendor contracts — only target estimated (unverified) items.
    """
    state_json = state.model_dump_json(indent=2)
    reduced_guests = max(int(state.config.guest_count * 0.85), 20)

    return f"""{INDIA_CONTEXT}

FULL EVENT STATE:
{state_json}

BUDGET DEFICIT TO RESOLVE:
- Total Budget  : ₹{state.budget.total_budget:,.0f}
- Current Overage: ₹{overage:,.0f}  ← must be eliminated or reduced to zero
- Event         : {state.config.event_type} in {state.config.location}
  for {state.config.guest_count} guests

TASK — Generate 2 to 3 trade-off packages:

Each option must have:
  "title"                    : numbered headline, e.g. "Option 1: Menu Rationalisation"
  "description"              : 2–3 sentence strategic summary (India-specific)
  "total_savings_inr"        : total ₹ savings (float)
  "impact_on_other_categories": downstream effects on other line items
  "recommended"              : true for the single best option, false for others
  "tradeoffs"                : list of TradeoffItem, each with:
      "category"             : affected expense category
      "action"               : specific measurable change (e.g.,
                               "Reduce guest count from {state.config.guest_count} → {reduced_guests}")
      "savings_inr"          : exact ₹ savings (float)
      "impact_description"   : effect on guest experience / aesthetic

INDIA-SPECIFIC TRADE-OFF IDEAS (pick the most relevant):
  - Replace imported florals with seasonal Indian blooms (marigold, tuberose, jasmine)
  - Consolidate mithai / dessert spread to 4 items instead of 8
  - Reduce guest count by 10–15 % (saves catering + seating + return gifts)
  - Switch from printed invitations to WhatsApp digital invites only
  - Reduce sound-system from full DJ rig to background music setup
  - Opt for a smaller theme cake + one cutting cake instead of multi-tier display
  - Use a community hall or clubhouse instead of a hotel banquet
  - Reduce photography package from 2-person crew to 1 candid photographer

RULES:
- Only target 'estimated' items (verified contracts are binding — do NOT cut those).
- Do NOT remove mandatory culturally essential items (mandap / purohit for weddings;
  birthday cake for birthdays; catering for any event).
- Do NOT introduce airport pickups, makeup artists (for non-wedding events),
  valet, or alcohol as suggestions.

Return ONLY valid JSON with a top-level "options" array.
No markdown. No explanation.
"""
