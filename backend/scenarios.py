"""Save isolated scenario previews and commit only the exact plan that was reviewed."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import re
import math
import unicodedata
import uuid

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from config import settings
from models import EventConfig, EventState, ScenarioPreviewResponse, TaskList, WhatIfResponse
from state_manager import get_state, recalculate_budget, save_state
from timeline_utils import recompute_timeline


class ScenarioChanges(BaseModel):
    model_config = ConfigDict(extra="ignore")
    budget_change: float = Field(default=0, allow_inf_nan=False)
    guest_count_delta: int = Field(default=0, strict=True)
    new_date: Optional[date] = None
    # Retain the previously documented absolute guest-count and budget inputs.
    guest_count: Optional[int] = Field(default=None, gt=0, strict=True)
    total_budget: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)


class ScenarioDraft(BaseModel):
    session_id: str
    candidate: EventState
    preview: ScenarioPreviewResponse


def target_config(state: EventState, delta: Dict[str, Any]) -> EventConfig:
    try:
        changes = ScenarioChanges.model_validate(delta)
        if "guest_count" in delta and "guest_count_delta" in delta:
            raise ValueError("Use either a guest count or a guest count delta, not both.")
        if "total_budget" in delta and "budget_change" in delta:
            raise ValueError("Use either a total budget or a budget change, not both.")
        values = state.config.model_dump()
        values["total_budget"] = round(changes.total_budget if changes.total_budget is not None else state.config.total_budget + changes.budget_change, 2)
        if not math.isfinite(values["total_budget"]):
            raise ValueError("The resulting budget must be finite.")
        values["guest_count"] = changes.guest_count if changes.guest_count is not None else state.config.guest_count + changes.guest_count_delta
        values["event_date"] = changes.new_date or state.config.event_date
        return EventConfig.model_validate(values)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Choose a valid date, a positive resulting budget, and a whole resulting guest count of at least one. Do not mix absolute values with deltas.") from exc


def _category(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", value) if not unicodedata.combining(char)).strip().casefold()


def _draft_directory() -> Path:
    directory = settings.state_dir / "scenarios"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _draft_path(scenario_id: str) -> Path:
    if not re.fullmatch(r"scenario_[a-f0-9]{32}", scenario_id):
        raise HTTPException(status_code=404, detail="This scenario could not be found. Run it again to create a fresh preview.")
    return _draft_directory() / f"{scenario_id}.json"


def save_preview(state: EventState, config: EventConfig, result: WhatIfResponse) -> ScenarioPreviewResponse:
    candidate = state.model_copy(deep=True)
    candidate.config = config
    budget = result.updated_budget.model_copy(deep=True)
    previous = {_category(item.category): item for item in state.budget.items}
    seen = set()
    for item in budget.items:
        key = _category(item.category)
        if key in seen:
            raise HTTPException(status_code=502, detail="The scenario returned duplicate budget categories. Please run it again.")
        seen.add(key)
        source = previous.get(key)
        # AI can estimate costs, but cannot create or alter a signed/verified cost.
        item.verified = source.verified if source else None
    budget.items.extend(item.model_copy(deep=True) for key, item in previous.items() if key not in seen)
    budget.total_budget = config.total_budget
    candidate.budget = recalculate_budget(budget)
    candidate.tradeoff_options = []
    risks = []
    affected = list(result.affected_tasks)
    if config.event_date != state.config.event_date:
        tasks, risks = recompute_timeline(candidate.tasks.tasks, state.config.event_date, config.event_date, late_task_ids=[])
        candidate.tasks = TaskList(tasks=tasks)
        original = {task.id: task for task in state.tasks.tasks}
        affected.extend(task.id for task in tasks if task.id in original and task.due_date != original[task.id].due_date)
    preview = ScenarioPreviewResponse(
        **{**result.model_dump(), "updated_budget": candidate.budget, "affected_tasks": list(dict.fromkeys(affected))},
        scenario_id=f"scenario_{uuid.uuid4().hex}", base_updated_at=state.updated_at,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24), committed_state=state,
        updated_config=config, updated_tasks=candidate.tasks, critical_risks=risks,
    )
    path = _draft_path(preview.scenario_id)
    draft = ScenarioDraft(session_id=state.config.session_id, candidate=candidate, preview=preview)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(draft.model_dump_json(), encoding="utf-8")
    temporary.replace(path)
    return preview


def commit_preview(session_id: str, scenario_id: str) -> EventState:
    path = _draft_path(scenario_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="This scenario could not be found. Run it again to create a fresh preview.")
    draft = ScenarioDraft.model_validate_json(path.read_text(encoding="utf-8"))
    if draft.session_id != session_id:
        raise HTTPException(status_code=404, detail="This scenario does not belong to this event.")
    current = get_state(session_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Your saved event could not be found.")
    # The marker and state are saved in the same atomic file write. A lost response
    # can be retried without reapplying deltas or replacing newer task updates.
    if current.last_committed_scenario_id == scenario_id:
        return current
    if datetime.now(timezone.utc) >= draft.preview.expires_at:
        raise HTTPException(status_code=410, detail="This preview has expired. Run the scenario again before committing.")
    if current.updated_at != draft.preview.base_updated_at:
        raise HTTPException(status_code=409, detail="Your saved plan has changed since this preview. Run the scenario again to compare with the latest plan.")
    candidate = draft.candidate
    candidate.last_committed_scenario_id = scenario_id
    save_state(session_id, candidate)
    return candidate
