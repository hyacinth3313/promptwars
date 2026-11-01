from __future__ import annotations

from backend.models import EventConfig
from backend.prompts._context import INDIA_CONTEXT

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

INTAKE_SYSTEM_PROMPT = (
    "You are an expert Indian event planner operating in Bangalore, India. "
    "You produce precise, culturally accurate budget breakdowns and task lists "
    "for Indian events. You never suggest Western-style items unless explicitly "
    "requested. You always use realistic INR pricing for the Bangalore market. "
    "You always return strictly valid JSON — no markdown, no prose."
)


# ---------------------------------------------------------------------------
# Per-event-type task menu
# ---------------------------------------------------------------------------

_BIRTHDAY_TASK_MENU = """\
BIRTHDAY PARTY — ALLOWED TASK CATEGORIES (use only these 8 categories):
  1. venue          – Book community hall / clubhouse / hotel banquet room
  2. catering       – Indian snacks (chaat, sandwiches, pakoras), South-Indian meal for adults
  3. birthday_cake  – Custom theme cake from local Bangalore bakery
  4. decoration     – Balloon setup, theme backdrop, flower decoration, string lights
  5. photography    – Candid photographer / short video package for memories
  6. return_gifts   – Goody bags / chocolates / small toys for children guests
  7. invitations    – WhatsApp digital invite (mandatory) + optional printed card
  8. sound_system   – Background music / light DJ set (NO full rave rig, NO MC)

DO NOT add: makeup artist, guest airport pickups, valet parking, imported florals,
alcohol bar, cocktail counter, gift-hamper for adults, mehndi, or any Western-only item.
"""

_WEDDING_TASK_MENU = """\
WEDDING — TASK CATEGORIES TO COVER:
  1. venue          – Banquet hall / marriage hall / resort
  2. catering       – Full Indian vegetarian + optional non-veg menu with live counters
  3. decoration     – Mandap, floral (marigold / tuberose / jasmine), entry décor, stage
  4. photography    – Photography + videography + drone (candid + traditional)
  5. invitations    – Printed wedding cards + digital WhatsApp invite
  6. mehendi        – Mehendi artist for bride (and ladies if requested)
  7. sangeet        – Stage program, choreographer, sound & lights
  8. priest         – Purohit / pandit booking, muhurtham confirmation
  9. logistics      – Baraat transport, local transfers for close family
  10. attire        – Bridal and groom attire coordination (NOT a makeup-artist line item)
"""

_CORPORATE_TASK_MENU = """\
CORPORATE EVENT — TASK CATEGORIES TO COVER:
  1. venue          – Conference room / hotel ballroom / banquet
  2. catering       – Vegetarian snacks, lunch / dinner buffet (South-Indian + North-Indian)
  3. av_setup       – Projector, PA system, microphones, stage lighting
  4. branding       – Standees, banners, flex boards, table runners
  5. photography    – Event photographer / videographer
  6. gifting        – Corporate gift boxes / mementos for attendees
  7. emcee          – Professional event anchor
  8. invitations    – Email / WhatsApp digital invite + printed passes if needed
"""

_COMMUNITY_TASK_MENU = """\
COMMUNITY / FESTIVAL EVENT — TASK CATEGORIES TO COVER:
  1. venue          – Open ground / community hall / school auditorium
  2. catering       – Mass vegetarian meal (₹150–₹350 per plate typical)
  3. stage          – Stage construction, PA sound system, lighting
  4. cultural       – Cultural performances, coordination with artists
  5. volunteers     – Volunteer roster, duty assignments
  6. decoration     – Basic pandal / hall decoration
  7. invitations    – Poster / pamphlet distribution + WhatsApp group invites
  8. photography    – Event photographer
"""


def _event_task_menu(event_type: str) -> str:
    mapping = {
        "birthday": _BIRTHDAY_TASK_MENU,
        "wedding": _WEDDING_TASK_MENU,
        "corporate": _CORPORATE_TASK_MENU,
        "community": _COMMUNITY_TASK_MENU,
    }
    return mapping.get(event_type, _CORPORATE_TASK_MENU)


# ---------------------------------------------------------------------------
# Main prompt function
# ---------------------------------------------------------------------------

def intake_prompt(config: EventConfig) -> str:
    """
    Build the intake prompt for generating BudgetBreakdown + TaskList.

    Rules:
    - Injects INDIA_CONTEXT for strict cultural grounding.
    - Injects per-event-type allowed task menu so the model cannot hallucinate
      Western-only items.
    - Demands BudgetBreakdown where allocated amounts sum exactly to total_budget.
    - Demands 10–15 TaskItems (fewer for simple birthday parties, more for weddings)
      with realistic Bangalore due_dates, depends_on chains, and INR estimated_cost.
    - All verified values must be null at intake.
    - Returns ONLY valid JSON — no markdown, no explanation.
    """
    config_json = config.model_dump_json(indent=2)
    task_menu = _event_task_menu(config.event_type)

    # Determine sensible task count range by event type
    task_range = {
        "birthday": "8 to 12",
        "wedding": "14 to 18",
        "corporate": "10 to 14",
        "community": "10 to 14",
        "other": "10 to 14",
    }.get(config.event_type, "10 to 14")

    return f"""{INDIA_CONTEXT}

EVENT CONFIGURATION:
{config_json}

{task_menu}

INSTRUCTIONS — GENERATE TWO THINGS:

─────────────────────────────────────
1. BUDGET BREAKDOWN (BudgetBreakdown)
─────────────────────────────────────
- Total budget: ₹{config.total_budget:,.0f} for {config.guest_count} guests in {config.location}.
- Distribute the budget across categories matching the priorities provided: {config.priorities}.
- The sum of all 'allocated' amounts MUST equal EXACTLY ₹{config.total_budget:,.0f}.
- Set 'estimated' to realistic Bangalore market cost for each category.
  Use the pricing guide in the INDIA_CONTEXT above.
- Set 'verified' to null for every item (nothing is confirmed at intake).
- Calculate:
    remaining = total_budget − sum(estimated)     [0 if estimated > budget]
    overage   = sum(estimated) − total_budget     [0 if under budget]
    is_over_budget = true if overage > 0, else false

─────────────────────────────────────
2. TASK LIST (TaskList)
─────────────────────────────────────
- Event date: {config.event_date}
- Generate EXACTLY {task_range} tasks drawn ONLY from the allowed categories above.
- Distribute tasks across milestones relative to event date:
    '3_months'  (earliest)  : major bookings and vendor shortlisting
    '1_month'               : confirmations, invitations, deposits
    '1_week'                : final headcount, vendor briefing, rehearsal
    'day_of'    (latest)    : setup, execution, vendor settlement
- For each task:
    * id           : kebab-case string, e.g. "task-venue-book", "task-cake-order"
    * title        : short, actionable (max 8 words)
    * description  : 1–2 sentences, specific to Indian / Bangalore context
    * milestone    : one of '3_months', '1_month', '1_week', 'day_of'
    * due_date     : realistic YYYY-MM-DD on or before {config.event_date}
    * depends_on   : list of task ids that must complete first (empty list if none)
    * status       : "pending"
    * estimated_cost : ₹ amount (float) or null if no direct spend

Return ONLY a single valid JSON object with exactly these two top-level keys:
  "budget"  → BudgetBreakdown object
  "tasks"   → TaskList object  (field "tasks" containing list of TaskItem)

No markdown. No explanation. No extra keys.
"""
