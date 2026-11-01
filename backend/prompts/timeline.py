from __future__ import annotations

from datetime import date
from typing import List, Optional

from models import EventState
from prompts._context import INDIA_CONTEXT

TIMELINE_SYSTEM_PROMPT = (
    "You are a meticulous Indian event project manager based in Bangalore. "
    "You handle deadline recalibrations, vendor booking constraints, and dependency "
    "cascades when event timelines shift or tasks fall behind schedule. "
    "You are deeply familiar with Indian vendor booking lead times (e.g., popular "
    "Bangalore banquet halls require 2–3 months advance, photographers book fast "
    "for auspicious dates, cake bakeries need 1 week for custom orders). "
    "You always return strictly valid JSON — no markdown, no prose."
)


def timeline_shift_prompt(
    state: EventState,
    new_date: Optional[date] = None,
    late_task_ids: Optional[List[str]] = None,
) -> str:
    """
    Prompt for re-sequencing tasks when the event date changes or tasks run late.

    Sends only the task list (not full state) to avoid context overflow on Groq.
    Completed tasks are listed for reference but must NOT be modified.
    """
    if late_task_ids is None:
        late_task_ids = []

    config = state.config
    current_date = config.event_date

    # Send only the task list (not full state JSON) to stay within token limits
    tasks_json = state.tasks.model_dump_json(indent=2)

    shift_lines: List[str] = []
    if new_date and new_date != current_date:
        shift_lines.append(
            f"- Event date has shifted from {current_date} → {new_date}."
        )
    else:
        shift_lines.append(f"- Event date unchanged: {current_date}.")

    if late_task_ids:
        shift_lines.append(
            f"- Tasks flagged as LATE / BLOCKED: {late_task_ids}\n"
            f"  Mark these as 'late' and push all downstream dependent tasks forward."
        )
    else:
        shift_lines.append("- No specific tasks flagged late; general schedule realignment.")

    shift_context = "\n".join(shift_lines)

    final_date = new_date or current_date

    return f"""{INDIA_CONTEXT}

EVENT SUMMARY:
- Type     : {config.event_type}
- Location : {config.location}
- Guests   : {config.guest_count}

CURRENT TASK LIST (JSON):
{tasks_json}

TIMELINE CHANGE DETAILS:
{shift_context}

INSTRUCTIONS:

1. RISK ANALYSIS:
   Identify up to 3 critical risks caused by this timeline change in 'critical_risks'
   (e.g., "Popular Bangalore banquet halls require 90-day advance booking — the new
   timeline leaves only 45 days, risk of losing preferred venue").
   Keep risks India / Bangalore specific.

2. UPDATED TASK LIST ('updated_tasks'):
   STRICT RULES:
   a. Tasks with status "completed" → copy them EXACTLY unchanged (same due_date,
      milestone, status, description, everything).
   b. No task can have a due_date BEFORE any of its depends_on tasks.
   c. Recalculate due_date for all non-completed tasks relative to: {final_date}.
   d. Re-assign milestones ('3_months', '1_month', '1_week', 'day_of') appropriately.
   e. For tasks in late_task_ids → set status = "late".
   f. Push every downstream dependent task forward to maintain valid ordering.
   g. Preserve id, title, description, estimated_cost, and depends_on for all tasks.

Return ONLY valid JSON with exactly two top-level keys:
  "critical_risks"  → list of strings (max 3)
  "updated_tasks"   → list of TaskItem objects

No markdown. No explanation.
"""
