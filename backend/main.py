from __future__ import annotations

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from ai_client import (
    GroqClientError,
    GroqConfigurationError,
    ai_client,
)
from config import settings
from models import (
    AnalyzeVendorRequest,
    ApplyTradeoffRequest,
    BudgetBreakdown,
    ChatMessageRequest,
    ChatResponse,
    CommitScenarioRequest,
    CreateSessionResponse,
    EventConfig,
    EventState,
    GroupedTasksResponse,
    IntakePlanResponse,
    RecalculateBudgetResponse,
    ScenarioPreviewResponse,
    TaskItem,
    TaskList,
    TaskStatusUpdateRequest,
    TaskStatusUpdateResponse,
    TimelineShiftRequest,
    TimelineShiftResponse,
    TradeoffOption,
    TradeoffResponse,
    VendorQuote,
    WhatIfRequest,
    WhatIfResponse,
)
from prompts import (
    INTAKE_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    TIMELINE_SYSTEM_PROMPT,
    TRADEOFF_SYSTEM_PROMPT,
    VENDOR_SYSTEM_PROMPT,
    WHATIF_SYSTEM_PROMPT,
    budget_prompt,
    chat_user_prompt,
    intake_prompt,
    tasks_prompt,
    timeline_shift_prompt,
    tradeoff_prompt,
    vendor_parse_prompt,
    whatif_prompt,
)
from state_manager import (
    apply_tradeoff_to_state,
    build_default_state,
    create_session,
    delete_session,
    generate_default_tradeoffs,
    get_state,
    list_sessions,
    recalculate_budget,
    save_state,
    update_state,
)
from timeline_utils import (
    calculate_task_stats,
    cascade_task_delay,
    group_tasks_by_milestone,
    recompute_timeline,
    validate_and_enforce_dependency_order,
)
from scenarios import commit_preview, save_preview, target_config


# Setup logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("event_planner_api")


# ------------------------------------------------------------------------------
# FastAPI Application & Lifespan
# ------------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing GenAI Event Planner Backend...")
    logger.info(f"State storage directory: {settings.state_dir.resolve()}")
    logger.info(f"Configured Groq model: {settings.groq_model}")
    if not ai_client.is_configured:
        logger.warning(
            "GROQ_API_KEY is not set or using placeholder. "
            "Get a free key at https://console.groq.com/keys and set GROQ_API_KEY in .env"
        )
    else:
        logger.info("Groq API client configured and authenticated.")
    yield
    logger.info("Shutting down GenAI Event Planner Backend.")


app = FastAPI(
    title="GenAI Event Planner API",
    description=(
        "Production-grade, 100% free-tier backend for AI-assisted event planning, "
        "budget allocation, vendor contract audits, trade-off optimization, and milestone timeline tracking."
    ),
    version="1.2.0",
    lifespan=lifespan,
)

# Enable CORS for local development and the production frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://promptwars-pi-lime.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serialize writes for each session in the file-backed, single-process server.
# This makes a scenario's revision check and commit indivisible relative to other
# event mutations while allowing AI previews and chat to run without blocking edits.
_session_write_locks: Dict[str, asyncio.Lock] = {}


@app.middleware("http")
async def serialize_session_writes(request, call_next):
    match = re.fullmatch(r"/api/sessions/([^/]+)(?:/(.*))?", request.url.path)
    if match and request.method in {"POST", "PATCH", "DELETE"} and match.group(2) not in {"what-if", "chat"}:
        lock = _session_write_locks.setdefault(match.group(1), asyncio.Lock())
        async with lock:
            return await call_next(request)
    return await call_next(request)


# ------------------------------------------------------------------------------
# System & Health Endpoints
# ------------------------------------------------------------------------------

@app.get("/", tags=["System"])
def root():
    return {
        "name": "GenAI Event Planner API",
        "version": "1.2.0",
        "status": "online",
        "docs_url": "/docs",
        "cors_origins": settings.cors_origins,
    }


@app.get("/health", tags=["System"])
def health_check():
    sessions = list_sessions()
    return {
        "status": "healthy",
        "groq_api_configured": ai_client.is_configured,
        "groq_model": settings.groq_model,
        "active_sessions_count": len(sessions),
        "state_directory": str(settings.state_dir.resolve()),
    }


# ------------------------------------------------------------------------------
# Session & State Management Endpoints
# ------------------------------------------------------------------------------

@app.post("/api/sessions", response_model=CreateSessionResponse, tags=["Sessions"])
def create_new_session():
    """Create a new session ID for a new event."""
    session_id = create_session()
    return CreateSessionResponse(
        session_id=session_id,
        message="New session created. Initialize with POST /api/sessions/{session_id}/init or /intake."
    )


@app.get("/api/sessions", response_model=List[str], tags=["Sessions"])
def get_all_sessions():
    """List all available stored session IDs."""
    return list_sessions()


@app.get("/api/sessions/{session_id}", response_model=EventState, tags=["Sessions"])
def read_event_state(session_id: str):
    """Retrieve full event state for a given session."""
    state = get_state(session_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return state


@app.post("/api/sessions/{session_id}", response_model=EventState, tags=["Sessions"])
def save_event_state(session_id: str, state: EventState):
    """Save or completely overwrite the EventState for a session."""
    if state.config.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"State session_id '{state.config.session_id}' does not match URL '{session_id}'.",
        )
    state.budget = recalculate_budget(state.budget)
    save_state(session_id, state)
    return state


@app.patch("/api/sessions/{session_id}", response_model=EventState, tags=["Sessions"])
def patch_event_state(session_id: str, partial_update: Dict[str, Any]):
    """Apply a partial update to an existing session's EventState with auto-recalculation."""
    try:
        updated = update_state(session_id, partial_update)
        return updated
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to update state: {str(exc)}",
        )


@app.delete("/api/sessions/{session_id}", tags=["Sessions"])
def remove_session(session_id: str):
    """Delete a session file from the state store."""
    deleted = delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return {"message": f"Session '{session_id}' removed successfully."}


# ------------------------------------------------------------------------------
# Core Intake & Planning Endpoints
# ------------------------------------------------------------------------------

async def _process_intake(session_id: str, config: EventConfig) -> EventState:
    """Core logic to initialize an event with budget and 12-18 milestone tasks."""
    if config.session_id != session_id:
        config.session_id = session_id

    # Fallback to deterministic default state if Groq is unconfigured
    if not ai_client.is_configured:
        logger.info("Groq API key not configured. Using deterministic fallback state with 15 tasks.")
        state = build_default_state(config)
        save_state(session_id, state)
        return state

    try:
        prompt_text = intake_prompt(config)
        plan: IntakePlanResponse = await ai_client.generate_structured(
            system=INTAKE_SYSTEM_PROMPT,
            user=prompt_text,
            schema=IntakePlanResponse,
            temperature=0.2,
        )

        # Enforce budget calculation accuracy
        plan.budget = recalculate_budget(plan.budget)

        now = datetime.now(timezone.utc)
        state = EventState(
            config=config,
            budget=plan.budget,
            tasks=plan.tasks,
            vendors=[],
            tradeoff_options=[],
            applied_tradeoffs=[],
            created_at=now,
            updated_at=now,
        )
        save_state(session_id, state)
        return state

    except Exception as exc:
        logger.error(
            f"AI initialization failed: {exc}. Falling back to deterministic default state.",
            exc_info=True,
        )
        state = build_default_state(config)
        save_state(session_id, state)
        return state


@app.post("/api/sessions/{session_id}/init", response_model=EventState, tags=["GenAI Planner"])
async def initialize_event_plan(session_id: str, config: EventConfig):
    """
    Initialize an event plan from EventConfig.
    Generates structured BudgetBreakdown + 12-18 TaskItems in Indian market context.
    Falls back to deterministic calculations if Groq is unconfigured or fails.
    """
    return await _process_intake(session_id, config)


@app.post("/api/sessions/{session_id}/intake", response_model=EventState, tags=["GenAI Planner"])
async def intake_event_plan(session_id: str, config: EventConfig):
    """
    Alias endpoint for event intake (/intake).
    Initializes session state with realistic budget breakdown and 12-18 milestone tasks.
    """
    return await _process_intake(session_id, config)


# ------------------------------------------------------------------------------
# Budget Recalculation & Trade-off Optimization Endpoints
# ------------------------------------------------------------------------------

@app.post(
    "/api/sessions/{session_id}/recalculate-budget",
    response_model=RecalculateBudgetResponse,
    tags=["Budget & Tradeoffs"],
)
async def recalculate_session_budget(session_id: str):
    """
    Solid budget recalculation endpoint:
    - Recomputes total spend, remaining, overage, and is_over_budget.
    - If is_over_budget == true, automatically prepares 2-3 concrete trade-off options.
    - Persists updated state.
    """
    state = get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    state.budget = recalculate_budget(state.budget)
    tradeoff_response = None

    if state.budget.is_over_budget:
        target_overage = state.budget.overage
        logger.info(f"Session '{session_id}' is over budget by ₹{target_overage:,.2f}. Preparing trade-offs...")

        if ai_client.is_configured:
            try:
                prompt_text = tradeoff_prompt(state=state, overage=target_overage)
                tradeoff_response = await ai_client.generate_structured(
                    system=TRADEOFF_SYSTEM_PROMPT,
                    user=prompt_text,
                    schema=TradeoffResponse,
                    temperature=0.2,
                )
            except Exception as exc:
                logger.warning(f"AI trade-off generation encountered error: {exc}. Using deterministic trade-offs.")
                tradeoff_response = generate_default_tradeoffs(state, target_overage)
        else:
            tradeoff_response = generate_default_tradeoffs(state, target_overage)

        state.tradeoff_options = tradeoff_response.options
        msg = f"Event is over budget by ₹{target_overage:,.2f}. 2-3 concrete trade-off packages have been prepared."
    else:
        msg = f"Budget is balanced and within allocated limits (Remaining surplus: ₹{state.budget.remaining:,.2f})."

    save_state(session_id, state)

    return RecalculateBudgetResponse(
        budget=state.budget,
        is_over_budget=state.budget.is_over_budget,
        overage=state.budget.overage,
        tradeoffs=tradeoff_response,
        message=msg,
    )


@app.post("/api/sessions/{session_id}/tradeoffs", response_model=TradeoffResponse, tags=["Budget & Tradeoffs"])
async def get_budget_tradeoffs(
    session_id: str,
    overage: Optional[float] = Query(None, description="Budget deficit to offset (defaults to current state overage)"),
    force_refresh: bool = Query(False, description="Whether to force AI re-generation or return cached options"),
):
    """
    Generate 2-3 concrete, numbered trade-off options with specific changes, exact ₹ savings,
    and impact on other categories. Saves options into session state.
    """
    state = get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    target_overage = overage if overage is not None and overage > 0 else state.budget.overage
    if target_overage <= 0:
        target_overage = max(state.budget.total_budget * 0.1, 50000.0)

    # Reuse active trade-off options if already prepared and not forced refresh
    if not force_refresh and state.tradeoff_options:
        return TradeoffResponse(
            overage_amount=round(target_overage, 2),
            options=state.tradeoff_options,
            guidance_notes="Displaying active trade-off recommendations for current overage.",
        )

    # Use AI if configured, otherwise deterministic fallback
    if ai_client.is_configured:
        try:
            prompt_text = tradeoff_prompt(state=state, overage=target_overage)
            tradeoff_response: TradeoffResponse = await ai_client.generate_structured(
                system=TRADEOFF_SYSTEM_PROMPT,
                user=prompt_text,
                schema=TradeoffResponse,
                temperature=0.2,
            )
        except Exception as exc:
            logger.warning(f"AI tradeoff generation failed: {exc}. Falling back to default trade-offs.")
            tradeoff_response = generate_default_tradeoffs(state, target_overage)
    else:
        tradeoff_response = generate_default_tradeoffs(state, target_overage)

    # Store latest trade-off options in state so user can apply by index
    state.tradeoff_options = tradeoff_response.options
    save_state(session_id, state)

    return tradeoff_response



@app.post("/api/sessions/{session_id}/apply-tradeoff", response_model=EventState, tags=["Budget & Tradeoffs"])
def apply_tradeoff_option(session_id: str, request: ApplyTradeoffRequest):
    """
    Apply a selected trade-off option to the event:
    - Accepts option_index (e.g. 0) from active trade-offs OR the full TradeoffOption object.
    - Lowers estimated budget items and records audit notes.
    - Adds an execution TaskItem to the checklist.
    - Automatically recalculates remaining, overage, and is_over_budget.
    - Saves and returns the updated EventState.
    """
    state = get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    selected_option: Optional[TradeoffOption] = None

    if request.option is not None:
        selected_option = request.option
    elif request.option_index is not None:
        if not state.tradeoff_options:
            # Generate deterministic trade-offs if none currently cached
            default_resp = generate_default_tradeoffs(state, state.budget.overage or 50000.0)
            state.tradeoff_options = default_resp.options

        if 0 <= request.option_index < len(state.tradeoff_options):
            selected_option = state.tradeoff_options[request.option_index]
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Option index {request.option_index} out of range (0 to {len(state.tradeoff_options) - 1}).",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either 'option_index' or 'option' in request body.",
        )

    # Apply changes to budget & task items
    updated_state = apply_tradeoff_to_state(state, selected_option)
    save_state(session_id, updated_state)

    logger.info(f"Applied trade-off '{selected_option.title}' to session '{session_id}'.")
    return updated_state


# ------------------------------------------------------------------------------
# Generation & Simulation Endpoints
# ------------------------------------------------------------------------------

@app.post("/api/sessions/{session_id}/generate-budget", response_model=BudgetBreakdown, tags=["GenAI Planner"])
async def generate_budget_breakdown(session_id: str):
    """
    Generate or recalculate the event budget breakdown using GroqClient and budget_prompt.
    """
    state = get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    if not ai_client.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Groq API key not configured. Obtain a free key at https://console.groq.com/keys and set GROQ_API_KEY in .env.",
        )

    try:
        prompt_text = budget_prompt(state)
        budget: BudgetBreakdown = await ai_client.generate_structured(
            system=PLANNER_SYSTEM_PROMPT,
            user=prompt_text,
            schema=BudgetBreakdown,
            temperature=0.2,
        )
        state.budget = recalculate_budget(budget)
        save_state(session_id, state)
        return state.budget

    except GroqConfigurationError as cfg_err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(cfg_err))
    except GroqClientError as client_err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(client_err))


@app.post("/api/sessions/{session_id}/generate-tasks", response_model=TaskList, tags=["GenAI Planner"])
async def generate_milestone_tasks(session_id: str):
    """
    Generate chronological milestone action items using GroqClient and tasks_prompt.
    """
    state = get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    if not ai_client.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Groq API key not configured. Obtain a free key at https://console.groq.com/keys and set GROQ_API_KEY in .env.",
        )

    try:
        prompt_text = tasks_prompt(state)
        task_list: TaskList = await ai_client.generate_structured(
            system=PLANNER_SYSTEM_PROMPT,
            user=prompt_text,
            schema=TaskList,
            temperature=0.2,
        )
        state.tasks = task_list
        save_state(session_id, state)
        return task_list

    except GroqConfigurationError as cfg_err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(cfg_err))
    except GroqClientError as client_err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(client_err))


@app.post("/api/sessions/{session_id}/analyze-vendor", response_model=VendorQuote, tags=["GenAI Planner"])
async def analyze_vendor_quote(session_id: str, request: AnalyzeVendorRequest, add_to_state: bool = True):
    """
    Parse a raw vendor quote or email text into a structured VendorQuote using GroqClient and vendor_parse_prompt.
    Uncovers hidden fees (GST, generator, corkage, overtime), inclusions, exclusions, and payment terms.
    """
    state = get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    if not ai_client.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Groq API key not configured. Obtain a free key at https://console.groq.com/keys and set GROQ_API_KEY in .env.",
        )

    try:
        prompt_text = vendor_parse_prompt(
            raw_text=request.quote_text,
            category=request.category or "unspecified",
            state=state,
        )
        vendor_quote: VendorQuote = await ai_client.generate_structured(
            system=VENDOR_SYSTEM_PROMPT,
            user=prompt_text,
            schema=VendorQuote,
            temperature=0.2,
        )

        if add_to_state:
            state.vendors.append(vendor_quote)
            save_state(session_id, state)

        return vendor_quote

    except GroqConfigurationError as cfg_err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(cfg_err))
    except GroqClientError as client_err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(client_err))


# ------------------------------------------------------------------------------
# Adaptive Timeline & Task Dependency Endpoints
# ------------------------------------------------------------------------------

@app.get("/api/sessions/{session_id}/tasks", response_model=GroupedTasksResponse, tags=["Timeline & Tasks"])
def get_grouped_tasks(session_id: str):
    """
    Retrieve all tasks grouped by milestone ('3_months', '1_month', '1_week', 'day_of')
    along with operational progress statistics (total, completed, in_progress, late, pending).
    """
    state = get_state(session_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    stats = calculate_task_stats(state.tasks.tasks)
    milestones = group_tasks_by_milestone(state.tasks.tasks)

    return GroupedTasksResponse(
        session_id=session_id,
        stats=stats,
        milestones=milestones,
        last_updated=state.tasks.last_updated,
    )


@app.post(
    "/api/sessions/{session_id}/tasks/{task_id}/status",
    response_model=TaskStatusUpdateResponse,
    tags=["Timeline & Tasks"],
)
def update_task_status(session_id: str, task_id: str, request: TaskStatusUpdateRequest):
    """
    Update the execution status of a specific task:
    - If status is set to 'late', automatically triggers downstream dependency recalculation
      and pushes dependent tasks forward by a reasonable amount.
    - Completed tasks remain completely untouched and immutable.
    - Re-enforces chronological dependency order across all tasks.
    """
    state = get_state(session_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )

    target_task: Optional[TaskItem] = None
    for task in state.tasks.tasks:
        if task.id == task_id:
            target_task = task
            break

    if not target_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found in session '{session_id}'.",
        )

    target_task.status = request.status
    affected_ids: List[str] = []
    timeline_shifted = False

    if request.status == "late":
        # Cascade delay of 5 days to all uncompleted downstream dependent tasks
        state.tasks.tasks, affected_ids = cascade_task_delay(
            tasks=state.tasks.tasks,
            delayed_task_id=task_id,
            delay_days=5,
            event_date=state.config.event_date,
        )
        timeline_shifted = len(affected_ids) > 0
        msg = (
            f"Task '{target_task.title}' marked as 'late'. "
            f"Pushed {len(affected_ids)} downstream dependent task(s) forward."
            if timeline_shifted
            else f"Task '{target_task.title}' marked as 'late'. No uncompleted downstream tasks needed shifting."
        )
    else:
        msg = f"Task '{target_task.title}' status successfully updated to '{request.status}'."

    state.tasks.last_updated = datetime.now(timezone.utc)
    state.updated_at = datetime.now(timezone.utc)
    save_state(session_id, state)

    return TaskStatusUpdateResponse(
        task=target_task,
        downstream_affected_task_ids=affected_ids,
        timeline_shifted=timeline_shifted,
        message=msg,
        tasks=state.tasks,
    )


@app.post("/api/sessions/{session_id}/shift-timeline", response_model=TimelineShiftResponse, tags=["Timeline & Tasks"])
async def shift_timeline(session_id: str, request: TimelineShiftRequest):
    """
    Adaptive timeline recalibration endpoint:
    - Recalculates due_dates for all non-completed tasks based on new event date or late tasks.
    - Respects dependencies: a task cannot be due before its depends_on prerequisite tasks.
    - Keeps completed tasks completely unchanged and immutable.
    - Returns updated TaskList + critical bottleneck risk warnings.
    """
    state = get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    target_event_date = request.new_date or state.config.event_date

    # 1. Snapshot completed tasks to strictly guarantee immutability
    completed_snapshots = {
        t.id: (t.status, t.due_date, t.milestone)
        for t in state.tasks.tasks
        if t.status == "completed"
    }

    response: Optional[TimelineShiftResponse] = None

    # 2. Try AI recalibration if Groq client is configured
    if ai_client.is_configured:
        try:
            prompt_text = timeline_shift_prompt(
                state=state,
                new_date=request.new_date,
                late_task_ids=request.late_task_ids,
            )
            response = await ai_client.generate_structured(
                system=TIMELINE_SYSTEM_PROMPT,
                user=prompt_text,
                schema=TimelineShiftResponse,
                temperature=0.2,
            )

            # Strictly restore completed tasks
            for task in response.updated_tasks.tasks:
                if task.id in completed_snapshots:
                    orig_status, orig_due, orig_milestone = completed_snapshots[task.id]
                    task.status = orig_status
                    task.due_date = orig_due
                    task.milestone = orig_milestone

            # Strict dependency validation and enforcement
            response.updated_tasks.tasks = validate_and_enforce_dependency_order(
                response.updated_tasks.tasks, event_date=target_event_date
            )

        except Exception as exc:
            logger.warning(
                f"AI timeline shift failed: {exc}. Falling back to deterministic recalibration engine."
            )
            response = None

    # 3. Deterministic timeline engine fallback
    if response is None:
        recalc_tasks, risks = recompute_timeline(
            tasks=state.tasks.tasks,
            original_event_date=state.config.event_date,
            new_event_date=request.new_date,
            late_task_ids=request.late_task_ids,
        )
        date_note = f" (Postponed/advanced to {request.new_date})" if request.new_date else ""
        response = TimelineShiftResponse(
            reasoning=f"Timeline schedule realigned to maintain valid prerequisite sequences{date_note}.",
            critical_risks=risks,
            updated_tasks=TaskList(tasks=recalc_tasks, last_updated=datetime.now(timezone.utc)),
        )

    # 4. Save updated timeline to session state
    if request.new_date:
        state.config.event_date = request.new_date
    state.tasks = response.updated_tasks
    state.tasks.last_updated = datetime.now(timezone.utc)
    state.updated_at = datetime.now(timezone.utc)
    save_state(session_id, state)

    return response


@app.post("/api/sessions/{session_id}/what-if", response_model=ScenarioPreviewResponse, tags=["GenAI Planner"])

async def simulate_what_if_scenario(session_id: str, request: WhatIfRequest):
    """
    Simulate hypothetical budget, headcount, or vendor adjustments in Indian market context.
    """
    state = get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    proposed_config = target_config(state, request.delta)

    if not ai_client.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Groq API key not configured. Obtain a free key at https://console.groq.com/keys and set GROQ_API_KEY in .env.",
        )

    try:
        prompt_text = whatif_prompt(state=state, delta=request.delta)
        response: WhatIfResponse = await ai_client.generate_structured(
            system=WHATIF_SYSTEM_PROMPT,
            user=prompt_text,
            schema=WhatIfResponse,
            temperature=0.2,
        )
        return save_preview(state, proposed_config, response)

    except GroqConfigurationError as cfg_err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(cfg_err))
    except GroqClientError as client_err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(client_err))


@app.post("/api/sessions/{session_id}/commit-scenario", response_model=EventState, tags=["GenAI Planner"])
def commit_what_if_scenario(session_id: str, request: CommitScenarioRequest):
    return commit_preview(session_id, request.scenario_id)


@app.post("/api/sessions/{session_id}/chat", response_model=ChatResponse, tags=["GenAI Planner"])
async def chat_with_planner(session_id: str, request: ChatMessageRequest):
    """
    Context-aware conversational event planning advisor.
    Injects current session state into prompt and returns guidance.
    """
    state = get_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    if not ai_client.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Groq API key not configured. Obtain a free key at https://console.groq.com/keys and set GROQ_API_KEY in .env.",
        )

    try:
        user_prompt = chat_user_prompt(state, request.message)
        reply = await ai_client.generate_text(
            system=PLANNER_SYSTEM_PROMPT,
            user=user_prompt,
            temperature=0.4,
        )
        return ChatResponse(
            reply=reply or "I have reviewed your event details and am ready to assist.",
            session_id=session_id,
            suggested_actions=["Review updated budget", "Verify vendor quotes", "Check pending tasks"],
        )
    except GroqConfigurationError as cfg_err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(cfg_err))
    except GroqClientError as client_err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(client_err))


# ------------------------------------------------------------------------------
# Direct Execution Entry Point
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
