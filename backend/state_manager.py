from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import settings
from backend.models import (
    BudgetBreakdown,
    BudgetItem,
    EventConfig,
    EventState,
    TaskItem,
    TaskList,
    TradeoffItem,
    TradeoffOption,
    TradeoffResponse,
)

logger = logging.getLogger("state_manager")


def _get_session_path(session_id: str) -> Path:
    """Resolve and validate the JSON file path for a session ID."""
    clean_id = session_id.strip().replace("..", "").replace("/", "").replace("\\", "")
    if not clean_id:
        raise ValueError("Invalid session_id provided")
    return settings.state_dir / f"{clean_id}.json"


def _deep_update(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively update a dictionary without losing nested keys."""
    for key, value in updates.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            base[key] = _deep_update(base[key], value)
        else:
            base[key] = value
    return base


def recalculate_budget(budget: BudgetBreakdown) -> BudgetBreakdown:
    """
    Recalculate remaining, overage, and is_over_budget for a BudgetBreakdown.

    Separates estimated vs verified costs:
    - If verified is not None, the verified contract cost is committed.
    - Otherwise, estimated cost is projected.
    """
    total_effective_cost = 0.0
    for item in budget.items:
        cost = item.verified if item.verified is not None else item.estimated
        total_effective_cost += cost

    total_effective_cost = round(total_effective_cost, 2)
    total_budget = round(budget.total_budget, 2)

    if total_effective_cost > total_budget:
        budget.is_over_budget = True
        budget.overage = round(total_effective_cost - total_budget, 2)
        budget.remaining = 0.0
    else:
        budget.is_over_budget = False
        budget.overage = 0.0
        budget.remaining = round(total_budget - total_effective_cost, 2)

    return budget


def create_session() -> str:
    """
    Generate a new unique session identifier.

    Returns:
        str: A unique session ID formatted as 'sess_<uuid_hex>'.
    """
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    logger.info(f"Created new session ID: {session_id}")
    return session_id


def get_state(session_id: str) -> Optional[EventState]:
    """
    Retrieve and parse the EventState for a given session.

    Args:
        session_id: The session identifier.

    Returns:
        EventState if found and valid, otherwise None.
    """
    try:
        path = _get_session_path(session_id)
        if not path.is_file():
            return None
        content = path.read_text(encoding="utf-8")
        return EventState.model_validate_json(content)
    except Exception as exc:
        logger.error(f"Failed to read state for session '{session_id}': {exc}", exc_info=True)
        return None


def save_state(session_id: str, state: EventState) -> None:
    """
    Persist the EventState to a JSON file in the state directory.

    Args:
        session_id: The session identifier.
        state: The validated EventState model.
    """
    path = _get_session_path(session_id)
    # Always refresh the updated_at timestamp upon saving
    state.updated_at = datetime.now(timezone.utc)
    json_data = state.model_dump_json(indent=2)

    # Write atomically via temp file to avoid partial corruption
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json_data, encoding="utf-8")
    temp_path.replace(path)
    logger.info(f"Saved state for session '{session_id}' to {path}")


def update_state(session_id: str, partial: Dict[str, Any]) -> EventState:
    """
    Apply a partial update dictionary to an existing session's EventState.
    Auto-recalculates budget metrics if budget or items were modified.

    Args:
        session_id: The session identifier.
        partial: Dictionary containing updated fields/sub-fields.

    Returns:
        The updated EventState instance.

    Raises:
        FileNotFoundError: If session state does not exist.
        ValidationError: If resulting merged data is invalid.
    """
    current_state = get_state(session_id)
    if current_state is None:
        raise FileNotFoundError(f"Session '{session_id}' not found in state storage.")

    # Convert existing state to dict (with JSON-compatible values for dates/enums)
    base_dict = json.loads(current_state.model_dump_json())

    # Deep update with partial changes
    updated_dict = _deep_update(base_dict, partial)
    updated_dict["updated_at"] = datetime.now(timezone.utc).isoformat()

    # Revalidate using Pydantic v2
    new_state = EventState.model_validate(updated_dict)

    # Auto-recalculate budget breakdown to ensure integrity
    new_state.budget = recalculate_budget(new_state.budget)

    save_state(session_id, new_state)
    return new_state


def list_sessions() -> List[str]:
    """Return all active session IDs found in the state directory."""
    try:
        files = settings.state_dir.glob("*.json")
        return [f.stem for f in files if not f.name.endswith(".tmp")]
    except Exception as exc:
        logger.error(f"Error listing sessions: {exc}")
        return []


def delete_session(session_id: str) -> bool:
    """
    Delete a session file if it exists.

    Returns:
        True if deleted, False if not found.
    """
    try:
        path = _get_session_path(session_id)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted session '{session_id}'")
            return True
        return False
    except Exception as exc:
        logger.error(f"Error deleting session '{session_id}': {exc}")
        return False


def _birthday_tasks(config: EventConfig) -> List[TaskItem]:
    """
    Deterministic fallback task list for birthday parties (Indian / Bangalore context).
    8 focused tasks covering venue, catering, cake, decoration, photography,
    return gifts, invitations, and sound system.
    No Western-only items (no DJ packages, no airport pickups, no makeup artists).
    """
    ev_date = config.event_date
    today = date.today()

    def _sd(days_before: int) -> date:
        calculated = ev_date - timedelta(days=days_before)
        return max(today, calculated) if ev_date > today else ev_date

    total = config.total_budget
    p = config.priorities
    n = config.guest_count
    loc = config.location

    return [
        # ── 3_months ───────────────────────────────────────────────────────
        TaskItem(
            id="task-venue-book",
            title="Book Birthday Venue",
            description=(
                f"Book a community hall, clubhouse, or hotel banquet room in {loc} "
                f"suitable for {n} guests. Pay advance and collect booking confirmation."
            ),
            milestone="3_months",
            due_date=_sd(60),
            depends_on=[],
            status="pending",
            estimated_cost=round(total * p.get("venue", 0.25), 2),
        ),
        TaskItem(
            id="task-photo-hire",
            title="Book Candid Photographer",
            description=(
                "Hire a candid photographer for the birthday event. Confirm coverage "
                "hours, deliverables (edited photos + short video reel), and advance payment."
            ),
            milestone="3_months",
            due_date=_sd(45),
            depends_on=[],
            status="pending",
            estimated_cost=round(total * p.get("photography", 0.1), 2),
        ),
        # ── 1_month ────────────────────────────────────────────────────────
        TaskItem(
            id="task-invites-send",
            title="Send WhatsApp & Printed Invitations",
            description=(
                f"Design and dispatch digital WhatsApp invitation to all {n} guests. "
                "Order printed invitation cards from a local Bangalore printer if needed."
            ),
            milestone="1_month",
            due_date=_sd(30),
            depends_on=["task-venue-book"],
            status="pending",
            estimated_cost=round(total * p.get("invitations", 0.02), 2),
        ),
        TaskItem(
            id="task-caterer-book",
            title="Finalise Caterer & Menu",
            description=(
                f"Book a local caterer for {n} guests. Confirm South-Indian snack menu "
                "(sandwiches, pakoras, chaat) and a hot meal for adults. Lock per-plate rate."
            ),
            milestone="1_month",
            due_date=_sd(21),
            depends_on=["task-venue-book"],
            status="pending",
            estimated_cost=round(total * p.get("catering", 0.35), 2),
        ),
        TaskItem(
            id="task-cake-order",
            title="Order Custom Birthday Cake",
            description=(
                "Place a custom theme cake order with a local Bangalore bakery "
                "(1–3 kg depending on guest count). Confirm design, flavour, and delivery time."
            ),
            milestone="1_month",
            due_date=_sd(14),
            depends_on=[],
            status="pending",
            estimated_cost=round(total * p.get("birthday_cake", 0.05), 2),
        ),
        TaskItem(
            id="task-return-gifts",
            title="Purchase Return Gifts / Goody Bags",
            description=(
                f"Buy return gifts for approximately {n} child guests — small goody bags, "
                "chocolates, or small toys. Source from local Bangalore wholesale markets."
            ),
            milestone="1_month",
            due_date=_sd(14),
            depends_on=["task-invites-send"],
            status="pending",
            estimated_cost=round(total * p.get("return_gifts", 0.05), 2),
        ),
        # ── 1_week ─────────────────────────────────────────────────────────
        TaskItem(
            id="task-decor-setup",
            title="Arrange Decoration & Sound System",
            description=(
                "Confirm balloon decoration, theme backdrop, and basic flower arrangement "
                "with the decorator. Book a light background music / sound system (NOT a "
                "full DJ rig). Do a venue walk-through to verify setup plan."
            ),
            milestone="1_week",
            due_date=_sd(5),
            depends_on=["task-venue-book"],
            status="pending",
            estimated_cost=round(
                total * p.get("decoration", 0.1) + total * p.get("sound_system", 0.03), 2
            ),
        ),
        # ── day_of ─────────────────────────────────────────────────────────
        TaskItem(
            id="task-day-execution",
            title="Day-of Setup, Execution & Vendor Settlement",
            description=(
                "Arrive early to verify decoration, catering setup, cake delivery, and "
                "sound system. Manage guest welcome, cake-cutting ceremony, and photography. "
                "Settle final vendor payments and collect receipts."
            ),
            milestone="day_of",
            due_date=ev_date,
            depends_on=["task-decor-setup", "task-caterer-book", "task-cake-order"],
            status="pending",
            estimated_cost=0.0,
        ),
    ]


def _wedding_tasks(config: EventConfig) -> List[TaskItem]:
    """
    Deterministic fallback tasks for Indian weddings (Bangalore context).
    Covers mandap, catering, decor, photography, invitations, mehendi, sangeet,
    purohit, baraat logistics.
    """
    ev_date = config.event_date
    today = date.today()

    def _sd(days_before: int) -> date:
        calculated = ev_date - timedelta(days=days_before)
        return max(today, calculated) if ev_date > today else ev_date

    total = config.total_budget
    p = config.priorities

    return [
        TaskItem(
            id="task-venue-book",
            title="Book Marriage Hall / Banquet",
            description=(
                f"Inspect and book a marriage hall or hotel banquet in {config.location} "
                f"for {config.guest_count} guests. Sign contract and pay advance."
            ),
            milestone="3_months",
            due_date=_sd(90),
            depends_on=[],
            status="pending",
            estimated_cost=round(total * p.get("venue", 0.25), 2),
        ),
        TaskItem(
            id="task-caterer-taste",
            title="Caterer Tasting & Menu Lock",
            description=(
                "Shortlist 2–3 Bangalore caterers. Attend tasting session, finalize "
                "full South-Indian vegetarian + non-veg menu with live counters."
            ),
            milestone="3_months",
            due_date=_sd(75),
            depends_on=["task-venue-book"],
            status="pending",
            estimated_cost=round(total * p.get("catering", 0.35), 2),
        ),
        TaskItem(
            id="task-photo-hire",
            title="Book Photography & Videography Crew",
            description=(
                "Book a candid + traditional photography crew and videographer. "
                "Confirm drone coverage, pre-wedding shoot, and highlight reel delivery."
            ),
            milestone="3_months",
            due_date=_sd(75),
            depends_on=[],
            status="pending",
            estimated_cost=round(total * p.get("photography", 0.1), 2),
        ),
        TaskItem(
            id="task-decor-concept",
            title="Mandap & Floral Decor Finalisation",
            description=(
                "Confirm mandap design, entry arch, stage floral arrangement (marigold / "
                "tuberose / jasmine), and hall draping with the decorator."
            ),
            milestone="3_months",
            due_date=_sd(60),
            depends_on=["task-venue-book"],
            status="pending",
            estimated_cost=round(total * p.get("decor", 0.15), 2),
        ),
        TaskItem(
            id="task-purohit-book",
            title="Book Purohit & Confirm Muhurtham",
            description=(
                "Book a pandit / purohit, confirm auspicious muhurtham date and time, "
                "and collect list of puja samagri requirements."
            ),
            milestone="3_months",
            due_date=_sd(60),
            depends_on=[],
            status="pending",
            estimated_cost=5000.0,
        ),
        TaskItem(
            id="task-invites-send",
            title="Dispatch Wedding Invitations",
            description=(
                "Send printed wedding invitation cards (courier for outstation guests) "
                "and WhatsApp digital invite. Collect RSVPs."
            ),
            milestone="1_month",
            due_date=_sd(30),
            depends_on=["task-venue-book"],
            status="pending",
            estimated_cost=round(total * 0.015, 2),
        ),
        TaskItem(
            id="task-mehendi-sangeet",
            title="Confirm Mehendi Artist & Sangeet Programme",
            description=(
                "Book mehendi artist for bride and bridesmaids. Plan sangeet programme — "
                "confirm choreographer, sound setup, and stage lighting for the evening."
            ),
            milestone="1_month",
            due_date=_sd(21),
            depends_on=["task-venue-book"],
            status="pending",
            estimated_cost=round(total * 0.04, 2),
        ),
        TaskItem(
            id="task-baraat-logistics",
            title="Arrange Baraat & Close-Family Transfers",
            description=(
                "Book decorated baraat vehicle (horse / car / band) and arrange "
                "local AC cab transfers for close family members on wedding day."
            ),
            milestone="1_month",
            due_date=_sd(14),
            depends_on=["task-invites-send"],
            status="pending",
            estimated_cost=round(total * p.get("logistics", 0.05), 2),
        ),
        TaskItem(
            id="task-rsvp-lock",
            title="Lock Final Headcount with Caterer",
            description=(
                "Confirm final guest count with caterer, add 10% buffer, "
                "and lock guaranteed plate count and seating arrangement."
            ),
            milestone="1_week",
            due_date=_sd(7),
            depends_on=["task-invites-send", "task-caterer-taste"],
            status="pending",
            estimated_cost=0.0,
        ),
        TaskItem(
            id="task-vendor-sync",
            title="Final Vendor Briefing & Run-Sheet",
            description=(
                "Issue detailed minute-by-minute run-sheet to caterer, decorator, "
                "photographer, purohit, sound team, and baraat coordinator."
            ),
            milestone="1_week",
            due_date=_sd(3),
            depends_on=["task-rsvp-lock", "task-decor-concept"],
            status="pending",
            estimated_cost=0.0,
        ),
        TaskItem(
            id="task-morning-inspect",
            title="Morning Setup Inspection",
            description=(
                "Inspect mandap floral freshness, seating readiness, catering counter "
                "layout, AC, sound check, and hygiene before guests arrive."
            ),
            milestone="day_of",
            due_date=ev_date,
            depends_on=["task-vendor-sync"],
            status="pending",
            estimated_cost=0.0,
        ),
        TaskItem(
            id="task-vendor-settle",
            title="Vendor Settlement & Sign-Off",
            description=(
                "Audit all delivered services, collect completion receipts, "
                "and disburse final balance payments to all vendors."
            ),
            milestone="day_of",
            due_date=ev_date,
            depends_on=["task-morning-inspect"],
            status="pending",
            estimated_cost=round(total * 0.15, 2),
        ),
    ]


def _generic_tasks(config: EventConfig) -> List[TaskItem]:
    """
    Deterministic fallback tasks for corporate / community / other events (Bangalore).
    Culturally appropriate — no Western-only items.
    """
    ev_date = config.event_date
    today = date.today()

    def _sd(days_before: int) -> date:
        calculated = ev_date - timedelta(days=days_before)
        return max(today, calculated) if ev_date > today else ev_date

    total = config.total_budget
    p = config.priorities
    n = config.guest_count
    loc = config.location

    return [
        TaskItem(
            id="task-venue-book",
            title=f"Book Venue in {loc}",
            description=(
                f"Confirm venue / conference hall in {loc} with capacity for {n} attendees. "
                "Sign agreement and pay advance."
            ),
            milestone="3_months",
            due_date=_sd(60),
            depends_on=[],
            status="pending",
            estimated_cost=round(total * p.get("venue", 0.25), 2),
        ),
        TaskItem(
            id="task-caterer-book",
            title="Book Catering & Finalize Menu",
            description=(
                f"Book caterer for {n} guests. Confirm vegetarian South-Indian / "
                "North-Indian buffet menu and per-plate rate."
            ),
            milestone="3_months",
            due_date=_sd(45),
            depends_on=["task-venue-book"],
            status="pending",
            estimated_cost=round(total * p.get("catering", 0.35), 2),
        ),
        TaskItem(
            id="task-photo-hire",
            title="Book Event Photographer",
            description=(
                "Hire a candid event photographer. Confirm coverage duration, "
                "deliverables, and advance payment schedule."
            ),
            milestone="3_months",
            due_date=_sd(45),
            depends_on=[],
            status="pending",
            estimated_cost=round(total * p.get("photography", 0.08), 2),
        ),
        TaskItem(
            id="task-decor-book",
            title="Confirm Stage & Hall Decoration",
            description=(
                "Finalize stage backdrop, floral decoration (Indian marigold / tuberose), "
                "branding standees, and hall draping with decorator."
            ),
            milestone="3_months",
            due_date=_sd(30),
            depends_on=["task-venue-book"],
            status="pending",
            estimated_cost=round(total * p.get("decor", 0.1), 2),
        ),
        TaskItem(
            id="task-invites-send",
            title="Dispatch Invitations",
            description=(
                f"Send WhatsApp / email digital invitations to all {n} attendees. "
                "Issue printed passes for walk-in management if needed."
            ),
            milestone="1_month",
            due_date=_sd(21),
            depends_on=["task-venue-book"],
            status="pending",
            estimated_cost=round(total * 0.015, 2),
        ),
        TaskItem(
            id="task-sound-av",
            title="Book Sound System & AV Setup",
            description=(
                "Confirm PA sound system, microphones, projector / LED screen, "
                "and stage lighting. Book generator backup."
            ),
            milestone="1_month",
            due_date=_sd(14),
            depends_on=["task-venue-book"],
            status="pending",
            estimated_cost=round(total * p.get("logistics", 0.05), 2),
        ),
        TaskItem(
            id="task-rsvp-lock",
            title="Lock Final Headcount",
            description=(
                "Confirm final attendee count. Lock guaranteed plate count with "
                "caterer (+10% buffer). Finalize seating / floor arrangement."
            ),
            milestone="1_week",
            due_date=_sd(7),
            depends_on=["task-invites-send", "task-caterer-book"],
            status="pending",
            estimated_cost=0.0,
        ),
        TaskItem(
            id="task-vendor-sync",
            title="Vendor Briefing & Run-Sheet",
            description=(
                "Issue run-sheet to caterer, decorator, AV team, and photographer. "
                "Confirm arrival times, setup sequence, and payment schedule."
            ),
            milestone="1_week",
            due_date=_sd(3),
            depends_on=["task-rsvp-lock", "task-decor-book"],
            status="pending",
            estimated_cost=0.0,
        ),
        TaskItem(
            id="task-morning-inspect",
            title="Day-of Setup Inspection",
            description=(
                "Inspect hall decoration, AV setup, catering counter layout, "
                "and hygiene before guests arrive. Brief on-ground team."
            ),
            milestone="day_of",
            due_date=ev_date,
            depends_on=["task-vendor-sync"],
            status="pending",
            estimated_cost=0.0,
        ),
        TaskItem(
            id="task-vendor-settle",
            title="Vendor Settlement & Sign-Off",
            description=(
                "Audit delivered services, collect completion receipts, and "
                "disburse final balance payments to all vendors."
            ),
            milestone="day_of",
            due_date=ev_date,
            depends_on=["task-morning-inspect"],
            status="pending",
            estimated_cost=round(total * 0.15, 2),
        ),
    ]


def build_default_state(config: EventConfig) -> EventState:
    """
    Construct a deterministic default EventState from EventConfig.

    Produces:
    - A mathematically balanced BudgetBreakdown (allocated = total_budget).
    - A culturally accurate, India / Bangalore-grounded TaskList:
      * birthday → 8 focused tasks (venue, catering, cake, decor, photo,
                   return gifts, invitations, sound system)
      * wedding  → 12 tasks (mandap, catering, decor, photo, invitations,
                   mehendi, sangeet, purohit, baraat, etc.)
      * other    → 10 generic South-Indian appropriate tasks
    - No Western-only items (no airport pickups, no DJ packages for birthdays,
      no makeup artists for non-wedding events, no valet, no alcohol bars).
    """
    # ── 1. Budget breakdown based on priorities ───────────────────────────
    budget_items: List[BudgetItem] = []
    total_budget = config.total_budget

    for category, weight in config.priorities.items():
        allocated = round(total_budget * weight, 2)
        budget_items.append(
            BudgetItem(
                category=category,
                allocated=allocated,
                estimated=allocated,
                verified=None,
                notes=(
                    f"Initial allocation based on {weight * 100:.1f}% priority weight "
                    f"for {config.location} market rates."
                ),
            )
        )

    budget = BudgetBreakdown(
        total_budget=total_budget,
        items=budget_items,
        remaining=0.0,
        overage=0.0,
        is_over_budget=False,
    )
    budget = recalculate_budget(budget)

    # ── 2. Event-type-aware task list ─────────────────────────────────────
    if config.event_type == "birthday":
        task_items = _birthday_tasks(config)
    elif config.event_type == "wedding":
        task_items = _wedding_tasks(config)
    else:
        task_items = _generic_tasks(config)

    tasks = TaskList(tasks=task_items)

    now = datetime.now(timezone.utc)
    return EventState(
        config=config,
        budget=budget,
        tasks=tasks,
        vendors=[],
        tradeoff_options=[],
        applied_tradeoffs=[],
        created_at=now,
        updated_at=now,
    )


def generate_default_tradeoffs(state: EventState, overage: float) -> TradeoffResponse:
    """
    Generate 2–3 concrete, India / Bangalore-appropriate trade-off options
    deterministically when AI generation is unavailable.

    - Birthday events: focus on venue downgrade, cake size, return gifts, and headcount.
    - Weddings: focus on floral substitution, menu rationalisation, and headcount.
    - Others: generic catering + decor + headcount options.
    All savings are calibrated to realistic Bangalore market rates.
    """
    event_type = state.config.event_type
    guest_count = state.config.guest_count
    reduced_guests = max(int(guest_count * 0.85), 20)
    guest_diff = guest_count - reduced_guests
    total = state.budget.total_budget

    # Per-plate catering estimate (realistic Bangalore rates)
    approx_per_plate = round(total * 0.35 / max(guest_count, 1), 2)
    guest_savings = round(guest_diff * approx_per_plate, 2)

    decor_savings = round(min(overage * 0.5, total * 0.07), 2)
    catering_savings = round(min(overage * 0.45, total * 0.08), 2)
    photo_savings = round(min(overage * 0.3, total * 0.04), 2)

    # ── Option 1: Catering & Decoration rationalisation ──────────────────
    if event_type == "birthday":
        opt1_title = "Option 1: Smaller Venue + Streamlined Decoration"
        opt1_desc = (
            "Downgrade from a hotel banquet to a clubhouse or community hall "
            "and simplify the balloon / theme décor package. Saves significantly "
            "without affecting the core birthday experience."
        )
        opt1_tradeoffs = [
            TradeoffItem(
                category="venue",
                action="Switch from hotel banquet to community hall or clubhouse in the same area",
                savings_inr=round(decor_savings * 1.2, 2),
                impact_description="Clubhouses in Bangalore cost ₹5,000–₹20,000 vs ₹30,000+ for hotel banquets.",
            ),
            TradeoffItem(
                category="decoration",
                action="Use balloon arch + printed backdrop instead of full floral + balloon setup",
                savings_inr=decor_savings,
                impact_description="Still creates a vibrant photo-friendly backdrop at half the cost.",
            ),
        ]
        opt1_impact = "Smaller hall reduces catering layout complexity and vendor coordination time."
    else:
        opt1_title = "Option 1: Menu Rationalisation & Indian Floral Substitution"
        opt1_desc = (
            "Replace imported exotic florals with seasonal Indian blooms and "
            "consolidate the dessert / mithai spread — no compromise on visual appeal."
        )
        opt1_tradeoffs = [
            TradeoffItem(
                category="decor",
                action="Replace imported hydrangeas / orchids with marigold, tuberose, and jasmine garlands",
                savings_inr=decor_savings,
                impact_description="Traditional Indian blooms are equally lush and cost 60–70% less than imports.",
            ),
            TradeoffItem(
                category="catering",
                action="Reduce dessert spread from 8 items to 4 Indian mithai + 1 live ice-cream counter",
                savings_inr=round(catering_savings * 0.6, 2),
                impact_description="Reduces food wastage; guests prefer quality over quantity in desserts.",
            ),
        ]
        opt1_impact = "Lowers decorator setup time; frees floor space for additional seating."

    option_1 = TradeoffOption(
        title=opt1_title,
        description=opt1_desc,
        total_savings_inr=round(
            sum(t.savings_inr for t in opt1_tradeoffs), 2
        ),
        tradeoffs=opt1_tradeoffs,
        impact_on_other_categories=opt1_impact,
        recommended=True,
    )

    # ── Option 2: Guest count reduction ──────────────────────────────────
    option_2 = TradeoffOption(
        title=f"Option 2: Guest Count Right-Sizing ({guest_count} → {reduced_guests} guests)",
        description=(
            f"Reduce the invitation list by {guest_diff} guests to cut catering, "
            "return gifts, and seating costs proportionally."
        ),
        total_savings_inr=guest_savings,
        tradeoffs=[
            TradeoffItem(
                category="catering",
                action=(
                    f"Reduce confirmed guest count from {guest_count} → {reduced_guests}; "
                    f"saves ~₹{approx_per_plate}/plate × {guest_diff} guests"
                ),
                savings_inr=guest_savings,
                impact_description=(
                    f"Direct per-plate saving of ~₹{approx_per_plate} across all served meals."
                ),
            ),
        ],
        impact_on_other_categories=(
            "Fewer guests also reduces return gift count and printed invitation cost."
        ),
        recommended=False,
    )

    # ── Option 3: Photography trim + Digital invitations ──────────────────
    invite_savings = round(min(total * 0.015, 3000.0), 2)
    option_3 = TradeoffOption(
        title="Option 3: Photography Package Trim + Digital-Only Invitations",
        description=(
            "Reduce photography to a single candid photographer (drop the video reel "
            "or second shooter) and switch fully to WhatsApp digital invitations."
        ),
        total_savings_inr=round(photo_savings + invite_savings, 2),
        tradeoffs=[
            TradeoffItem(
                category="photography",
                action=(
                    "Retain one candid photographer; remove second shooter / "
                    "highlight video reel; deliver edited photos via cloud gallery"
                ),
                savings_inr=photo_savings,
                impact_description="Primary memories still captured; album printing cost eliminated.",
            ),
            TradeoffItem(
                category="invitations",
                action="Switch from printed cards to WhatsApp digital invite only",
                savings_inr=invite_savings,
                impact_description=(
                    "Digital invites are faster, free to duplicate, and eco-friendly. "
                    "Bangalore guests are comfortable with WhatsApp invitations."
                ),
            ),
        ],
        impact_on_other_categories="Reduces courier cost and postal lead-time pressure.",
        recommended=False,
    )

    return TradeoffResponse(
        overage_amount=round(overage, 2),
        options=[option_1, option_2, option_3],
        guidance_notes=(
            "Option 1 is recommended — it preserves guest headcount and cultural "
            "essentials while resolving the overage through smart venue and decor choices."
        ),
    )


def apply_tradeoff_to_state(state: EventState, option: TradeoffOption) -> EventState:
    """
    Apply a selected TradeoffOption to the EventState:
    - Lowers estimated expenditure on matching budget items
    - Adds an audit note to each modified budget line item
    - Creates corresponding actionable TaskItems in the task list
    - Recalculates remaining, overage, and is_over_budget
    - Saves the applied option to history
    """
    for tradeoff in option.tradeoffs:
        target_cat = tradeoff.category.strip().lower()

        # Update matching budget item
        matched_item = None
        for item in state.budget.items:
            if target_cat in item.category.lower() or item.category.lower() in target_cat:
                matched_item = item
                break

        if matched_item:
            # Reduce estimated cost by savings
            matched_item.estimated = max(0.0, round(matched_item.estimated - tradeoff.savings_inr, 2))
            tradeoff_note = f"[Trade-off: {tradeoff.action} (-₹{tradeoff.savings_inr:,.0f})]"
            if tradeoff_note not in matched_item.notes:
                matched_item.notes = (matched_item.notes + " " + tradeoff_note).strip()
        else:
            # If no exact category matches, apply to the largest estimated category or create adjustment
            logger.info(f"Tradeoff category '{tradeoff.category}' not directly matched; allocating to general.")

        # Check if action indicates guest count reduction
        guest_match = re.search(r"(\d+)\s*(?:→|->|to)\s*(\d+)", tradeoff.action)
        if guest_match and "guest" in tradeoff.action.lower():
            new_guests = int(guest_match.group(2))
            state.config.guest_count = new_guests
            logger.info(f"Updated guest_count to {new_guests} based on trade-off action.")

        # Add an actionable task to implement this trade-off
        task_id = f"task-tradeoff-{uuid.uuid4().hex[:6]}"
        state.tasks.tasks.append(
            TaskItem(
                id=task_id,
                title=f"Execute Trade-off: {tradeoff.action[:60]}",
                description=(
                    f"Category: {tradeoff.category}. "
                    f"Target Savings: ₹{tradeoff.savings_inr:,.2f}. "
                    f"Impact details: {tradeoff.impact_description}"
                ),
                milestone="1_month",
                due_date=state.config.event_date,
                depends_on=[],
                status="pending",
                estimated_cost=0.0,
            )
        )

    # Recalculate budget breakdown metrics
    state.budget = recalculate_budget(state.budget)
    state.tasks.last_updated = datetime.now(timezone.utc)

    # Record applied trade-off
    state.applied_tradeoffs.append(option)
    state.updated_at = datetime.now(timezone.utc)

    return state
