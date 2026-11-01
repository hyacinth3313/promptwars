from __future__ import annotations

import json
from backend.models import EventState
from backend.prompts._context import INDIA_CONTEXT

PLANNER_SYSTEM_PROMPT = (
    "You are an expert Indian event planner operating in Bangalore, India. "
    "You produce culturally accurate, realistic budget recalculations and task lists "
    "for Indian events. You never suggest Western-only items. "
    "You always use ₹ (INR) pricing calibrated to the Bangalore market. "
    "You always return strictly valid JSON — no markdown, no prose."
)


def budget_prompt(state: EventState) -> str:
    """
    Prompt for recalculating / optimising BudgetBreakdown from current EventState.
    Preserves verified vendor amounts; re-estimates everything else using
    realistic Bangalore / South-India market rates.
    """
    state_json = state.model_dump_json(indent=2)
    config = state.config

    return f"""{INDIA_CONTEXT}

FULL EVENT STATE:
{state_json}

BUDGET RECALCULATION TASK:
- Event: {config.event_type} in {config.location} for {config.guest_count} guests.
- Total budget: ₹{config.total_budget:,.0f}
- Priority weights: {json.dumps(config.priorities)}

Instructions:
1. Use the pricing guide in the context block above for realistic Bangalore market estimates.
2. PRESERVE verified amounts that already exist in state — do not reduce those.
3. Re-estimate all non-verified (estimated-only) line items using current market rates.
4. The sum of 'allocated' values MUST equal ₹{config.total_budget:,.0f}.
5. Calculate remaining, overage, and is_over_budget correctly.
6. Do NOT add any Western-only expense categories. Stick to categories relevant to
   a {config.event_type} as described in the context above.

Return ONLY valid JSON matching the BudgetBreakdown schema. No markdown, no explanation.
"""


def tasks_prompt(state: EventState) -> str:
    """
    Prompt for creating / regenerating TaskList from current EventState.
    Strongly grounds tasks to Indian / Bangalore context and the allowed
    category list for the given event type.
    """
    state_json = state.model_dump_json(indent=2)
    config = state.config

    task_range = {
        "birthday": "8 to 12",
        "wedding": "14 to 18",
        "corporate": "10 to 14",
        "community": "10 to 14",
        "other": "10 to 14",
    }.get(config.event_type, "10 to 14")

    # Import the per-event task menu from intake for consistency
    from backend.prompts.intake import _event_task_menu
    task_menu = _event_task_menu(config.event_type)

    return f"""{INDIA_CONTEXT}

FULL EVENT STATE:
{state_json}

{task_menu}

TASK LIST GENERATION:
- Event: {config.event_type} on {config.event_date} in {config.location}.
- Generate EXACTLY {task_range} tasks drawn ONLY from the allowed categories above.
- Milestones relative to event date {config.event_date}:
    '3_months'  → vendor shortlisting, booking, deposits
    '1_month'   → confirmations, invitations, secondary bookings
    '1_week'    → final headcount lock, vendor briefing, prep
    'day_of'    → setup, execution, settlement
- Each task: unique id (kebab-case), title (≤ 8 words), description (1–2 sentences,
  Bangalore-specific), due_date (YYYY-MM-DD ≤ {config.event_date}), depends_on list,
  status "pending", estimated_cost in ₹ or null.

Return ONLY valid JSON matching the TaskList schema. No markdown, no explanation.
"""


def chat_user_prompt(state: EventState, message: str) -> str:
    """
    Conversational assistant prompt with full state context.
    The system prompt already contains the INDIA_CONTEXT grounding rules,
    so we only inject state + the user's message here.
    """
    state_json = state.model_dump_json(indent=2)
    return f"""CURRENT EVENT STATE:
{state_json}

USER QUESTION / INSTRUCTION:
{message}

Remember: all suggestions must be India-appropriate (Bangalore market, ₹ pricing).
Do NOT recommend Western-only vendors, airport pickups, DJ packages for birthday
parties, makeup artists (unless it is a wedding), valet parking, or alcohol bars.
"""
