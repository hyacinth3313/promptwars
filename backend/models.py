from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


# ------------------------------------------------------------------------------
# Core Event Configuration Models
# ------------------------------------------------------------------------------

class EventConfig(BaseModel):
    """Configuration and constraints for an event."""

    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(
        ...,
        description="Unique identifier for the planning session",
        examples=["sess_a1b2c3d4e5f6"],
    )
    event_type: Literal["wedding", "birthday", "corporate", "community", "other"] = Field(
        ...,
        description="The primary classification of the event",
    )
    event_date: date = Field(
        ...,
        validation_alias=AliasChoices("event_date", "date"),
        description="Scheduled calendar date of the event (YYYY-MM-DD)",
        examples=["2026-12-15"],
    )
    location: str = Field(
        ...,
        description="City, venue, or geographical region where the event takes place",
        examples=["Bengaluru, Karnataka"],
    )
    total_budget: float = Field(
        ...,
        gt=0,
        description="Total allocated financial budget in specified currency (INR default)",
        examples=[1500000.0],
    )
    guest_count: int = Field(
        ...,
        gt=0,
        description="Expected total headcount of attendees/guests",
        examples=[250],
    )
    priorities: Dict[str, float] = Field(
        ...,
        description=(
            "Relative budgetary weights assigned to expense categories "
            "(e.g., {'catering': 0.4, 'venue': 0.3, 'decor': 0.15, 'photography': 0.1, 'logistics': 0.05}). "
            "Must sum to 1.0 (within ±0.01 tolerance)."
        ),
        examples=[{"catering": 0.40, "venue": 0.30, "decor": 0.15, "photography": 0.10, "logistics": 0.05}],
    )
    currency: str = Field(
        default="INR",
        description="ISO 4217 currency code for all financial figures",
        examples=["INR"],
    )

    @field_validator("priorities")
    @classmethod
    def validate_priorities_sum(cls, priorities: Dict[str, float]) -> Dict[str, float]:
        if not priorities:
            raise ValueError("Priorities dictionary cannot be empty.")
        for k, v in priorities.items():
            if v < 0:
                raise ValueError(f"Priority weight for '{k}' cannot be negative.")
        total = sum(priorities.values())
        if not (0.99 <= total <= 1.01):
            raise ValueError(
                f"Priorities must sum to 1.0 (current sum: {total:.4f}). "
                "Please adjust the weights to sum to 100%."
            )
        return priorities


# ------------------------------------------------------------------------------
# Budget Models
# ------------------------------------------------------------------------------

class BudgetItem(BaseModel):
    """Line item detailing budget allocation, estimate, and actual cost."""

    category: str = Field(
        ...,
        description="Expense vertical (e.g., 'venue', 'catering', 'decor', 'photography')",
        examples=["catering"],
    )
    allocated: float = Field(
        ...,
        ge=0,
        description="Planned amount allocated from the total budget (INR)",
        examples=[600000.0],
    )
    estimated: float = Field(
        ...,
        ge=0,
        description="Estimated actual expenditure based on preliminary quotes or market rates",
        examples=[580000.0],
    )
    verified: Optional[float] = Field(
        default=None,
        ge=0,
        description="Confirmed cost verified from signed vendor contract/invoices (None if unverified)",
        examples=[575000.0],
    )
    notes: str = Field(
        default="",
        description="Additional context, vendor remarks, or cost reduction opportunities",
        examples=["Buffet package includes welcome drinks and dessert spread"],
    )


class BudgetBreakdown(BaseModel):
    """Aggregated financial overview across all expense categories."""

    total_budget: float = Field(
        ...,
        ge=0,
        description="Overall budget limit for the entire event",
        examples=[1500000.0],
    )
    items: List[BudgetItem] = Field(
        default_factory=list,
        description="Breakdown of individual budget items across categories",
    )
    remaining: float = Field(
        ...,
        description="Unallocated or surplus funds (total_budget - effective expenditure)",
        examples=[50000.0],
    )
    overage: float = Field(
        ...,
        ge=0,
        description="Deficit amount if estimated/verified costs exceed the total budget (0 if within budget)",
        examples=[0.0],
    )
    is_over_budget: bool = Field(
        ...,
        description="Flag indicating whether total projected expenditure exceeds the budget",
        examples=[False],
    )


# ------------------------------------------------------------------------------
# Task & Milestone Models
# ------------------------------------------------------------------------------

class TaskItem(BaseModel):
    """Discrete planning action item with milestone tag and dependencies."""

    id: str = Field(
        ...,
        description="Unique slug or identifier for this task (e.g., 'task-venue-book')",
        examples=["task-venue-book"],
    )
    title: str = Field(
        ...,
        description="Concise action-oriented headline of the task",
        examples=["Finalize and book banquet venue"],
    )
    description: str = Field(
        ...,
        description="Detailed execution instructions and criteria for completion",
        examples=["Review capacity for 250 guests, confirm audio-visual support, and pay deposit"],
    )
    milestone: Literal["3_months", "1_month", "1_week", "day_of"] = Field(
        ...,
        description="Target completion timeline milestone relative to event date",
    )
    due_date: date = Field(
        ...,
        description="Hard deadline date for the task (YYYY-MM-DD)",
        examples=["2026-09-15"],
    )
    depends_on: List[str] = Field(
        default_factory=list,
        description="List of prerequisite task IDs that must be completed first",
        examples=[["task-budget-approval"]],
    )
    status: Literal["pending", "in_progress", "completed", "late"] = Field(
        default="pending",
        description="Current operational progress status of the task",
    )
    estimated_cost: Optional[float] = Field(
        default=None,
        ge=0,
        description="Estimated monetary cost associated with this action item (if applicable)",
        examples=[450000.0],
    )


class TaskList(BaseModel):
    """Collection of event execution tasks and the latest update timestamp."""

    tasks: List[TaskItem] = Field(
        default_factory=list,
        description="All planning and execution tasks for the event",
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp of the most recent task list modification",
    )


# ------------------------------------------------------------------------------
# Vendor Models
# ------------------------------------------------------------------------------

class VendorQuote(BaseModel):
    """Extracted and analyzed vendor quotation with risk flags."""

    vendor_name: str = Field(
        ...,
        description="Business name or contact title of the vendor",
        examples=["Royal Feast Caterers"],
    )
    category: str = Field(
        ...,
        description="Service domain (e.g., 'catering', 'photography', 'decor', 'venue')",
        examples=["catering"],
    )
    total_quoted: float = Field(
        ...,
        ge=0,
        description="Total quoted price including taxes where specified",
        examples=[480000.0],
    )
    line_items: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Itemized services or goods with individual descriptions and amounts",
        examples=[[{"item": "Buffet Dinner (250 pax)", "cost": 420000.0}, {"item": "Welcome mocktails", "cost": 60000.0}]],
    )
    hidden_fees: List[str] = Field(
        default_factory=list,
        description="Detected covert charges (e.g., corkage fee, generator diesel, service charge, extra hour surcharge)",
        examples=["10% service charge omitted from main total", "Overtime billed at 5,000 INR/hour"],
    )
    inclusions: List[str] = Field(
        default_factory=list,
        description="Explicitly guaranteed deliverables and equipment provided by vendor",
        examples=["Cutlery, crockery, serving staff, cleanup, chafing dishes"],
    )
    exclusions: List[str] = Field(
        default_factory=list,
        description="Items specifically omitted that require external arrangements",
        examples=["Mineral water bottles", "Cocktail bar glassware"],
    )
    payment_schedule: str = Field(
        ...,
        description="Payment milestones (e.g., '25% advance, 50% week before, 25% post event')",
        examples=["30% advance on signing, 70% morning of event"],
    )
    capacity: Optional[int] = Field(
        default=None,
        ge=0,
        description="Maximum guest or unit capacity supported by this vendor quote",
        examples=[300],
    )
    notes: str = Field(
        default="",
        description="General analyst remarks, quality ratings, or negotiation leverage points",
        examples=["Highly recommended, but request waiver on overtime fee"],
    )
    is_verified: bool = Field(
        default=False,
        description="True if quote has been accepted and verified by the event organizer",
    )


# ------------------------------------------------------------------------------
# Root Session State Model
# ------------------------------------------------------------------------------

class EventState(BaseModel):
    """Root event state stored per session in the state/ folder."""

    config: EventConfig = Field(
        ...,
        description="High-level event parameters and initial constraints",
    )
    last_committed_scenario_id: Optional[str] = Field(default=None, description="Last accepted scenario, used to make commit retries idempotent")
    budget: BudgetBreakdown = Field(
        ...,
        description="Current budget allocation, expenditures, and remaining balances",
    )
    tasks: TaskList = Field(
        ...,
        description="Action plan milestones, deadlines, and dependencies",
    )
    vendors: List[VendorQuote] = Field(
        default_factory=list,
        description="Collection of received, reviewed, and verified vendor proposals",
    )
    tradeoff_options: List[TradeoffOption] = Field(
        default_factory=list,
        description="Latest available trade-off options generated for overage",
    )
    applied_tradeoffs: List[TradeoffOption] = Field(
        default_factory=list,
        description="Historical record of trade-off packages applied to this event",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the session was created",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the session state was last modified",
    )


# ------------------------------------------------------------------------------
# API Request / Response Support Models
# ------------------------------------------------------------------------------

class CreateSessionResponse(BaseModel):
    session_id: str = Field(..., description="Newly generated session identifier")
    message: str = Field(default="Session initialized successfully")


class IntakePlanResponse(BaseModel):
    """Structured output for initial event intake (budget + tasks)."""
    budget: BudgetBreakdown = Field(..., description="Initial calculated budget breakdown")
    tasks: TaskList = Field(..., description="Initial milestone-driven task checklist")


class TradeoffItem(BaseModel):
    """A concrete cost reduction adjustment in an expense category."""
    category: str = Field(..., description="Expense category being adjusted (e.g. decor, venue, catering)")
    action: str = Field(..., description="Concrete, actionable cost reduction step (e.g. 'Reduce guest count from 150 → 130')")
    savings_inr: float = Field(..., ge=0, description="Estimated monetary savings in INR (₹)")
    impact_description: str = Field(..., description="Consequence on guest experience, aesthetic, or logistics")


class TradeoffOption(BaseModel):
    """A bundled trade-off recommendation package to resolve budget overage."""
    title: str = Field(..., description="Descriptive numbered headline (e.g. 'Option 1: Menu & Guest Count Rationalization')")
    description: str = Field(..., description="Overall strategic rationale")
    total_savings_inr: float = Field(..., ge=0, description="Total estimated cost reduction in INR (₹)")
    tradeoffs: List[TradeoffItem] = Field(default_factory=list, description="Specific line-item adjustments and actions")
    impact_on_other_categories: str = Field(
        default="",
        description="Downstream cost, logistical, or vendor ripple effects across other categories",
    )
    recommended: bool = Field(default=False, description="Whether this is the planner's recommended choice")


class TradeoffResponse(BaseModel):
    """Structured response containing 2-3 trade-off options for budget deficit."""
    overage_amount: float = Field(..., description="The budget deficit in INR (₹) being addressed")
    options: List[TradeoffOption] = Field(..., description="2-3 concrete, realistic numbered trade-off packages")
    guidance_notes: str = Field(default="", description="Strategic commentary and next steps")


class ApplyTradeoffRequest(BaseModel):
    """Payload to apply a chosen trade-off package to the event state."""
    option_index: Optional[int] = Field(
        default=None,
        ge=0,
        description="Zero-based index of the trade-off option to apply (from latest generated trade-offs)",
    )
    option: Optional[TradeoffOption] = Field(
        default=None,
        description="Full TradeoffOption object to apply directly",
    )
    custom_notes: Optional[str] = Field(
        default="",
        description="Optional organizer notes regarding why this trade-off was selected",
    )


class RecalculateBudgetResponse(BaseModel):
    """Response from budget recalculation, with auto-prepared trade-offs if over budget."""
    budget: BudgetBreakdown = Field(..., description="Recalculated budget breakdown")
    is_over_budget: bool = Field(..., description="Flag indicating if expenses exceed total budget")
    overage: float = Field(..., description="Deficit amount in INR (0 if within budget)")
    tradeoffs: Optional[TradeoffResponse] = Field(
        default=None,
        description="Automatically generated trade-off options if the event is over budget",
    )
    message: str = Field(default="", description="Status or advisory message")



class TimelineShiftRequest(BaseModel):
    """Input payload to simulate a postponed/advanced event date or delayed tasks."""

    model_config = ConfigDict(populate_by_name=True)

    new_date: Optional[date] = Field(
        default=None,
        validation_alias=AliasChoices("new_event_date", "new_date"),
        description="New event target date if postponed or advanced (YYYY-MM-DD)",
    )
    late_task_ids: List[str] = Field(
        default_factory=list,
        description="IDs of tasks currently flagged as late or blocked",
    )


class TimelineShiftResponse(BaseModel):
    """Recalculated task schedule and dependency risk analysis."""
    reasoning: str = Field(..., description="Analysis of the schedule adjustment and ripple effects")
    critical_risks: List[str] = Field(default_factory=list, description="Identified bottleneck dependencies or urgent risks")
    updated_tasks: TaskList = Field(..., description="Re-sequenced task list with adjusted milestones and due dates")


class TaskProgressStats(BaseModel):
    """Operational progress statistics across all planning tasks."""
    total: int = Field(..., description="Total count of tasks")
    completed: int = Field(..., description="Tasks marked as completed")
    in_progress: int = Field(..., description="Tasks currently in progress")
    pending: int = Field(..., description="Tasks pending execution")
    late: int = Field(..., description="Tasks flagged as late or overdue")
    completion_percentage: float = Field(..., description="Percentage of tasks completed (0.0 - 100.0)")


class GroupedTasksResponse(BaseModel):
    """Tasks organized by milestone phase alongside aggregated progress statistics."""
    session_id: str = Field(..., description="Active session ID")
    stats: TaskProgressStats = Field(..., description="Aggregated progress statistics")
    milestones: Dict[str, List[TaskItem]] = Field(
        ...,
        description="Tasks grouped by milestone (3_months, 1_month, 1_week, day_of)",
    )
    last_updated: datetime = Field(..., description="Timestamp of most recent task modification")


class TaskStatusUpdateRequest(BaseModel):
    """Payload to update the execution status of a task."""
    status: Literal["pending", "in_progress", "completed", "late"] = Field(
        ...,
        description="New execution status for the task",
    )


class TaskStatusUpdateResponse(BaseModel):
    """Response returned upon updating task status, including ripple effects."""
    task: TaskItem = Field(..., description="The modified task object")
    downstream_affected_task_ids: List[str] = Field(
        default_factory=list,
        description="IDs of dependent tasks pushed forward due to delay",
    )
    timeline_shifted: bool = Field(
        ...,
        description="Whether cascading date shifts were triggered",
    )
    message: str = Field(..., description="Status summary message")
    tasks: TaskList = Field(..., description="Updated full task list")



class WhatIfRequest(BaseModel):
    """Input payload for what-if scenario simulation."""
    delta: Dict[str, Any] = Field(
        ...,
        description="Hypothetical modifications, e.g. {'guest_count': 350} or {'venue_cost_increase': 150000}",
    )


class WhatIfResponse(BaseModel):
    """Simulation results detailing budget changes and affected tasks."""
    scenario_summary: str = Field(..., description="Executive summary of the simulated scenario")
    financial_impact: str = Field(..., description="Direct budget and cost implications in ₹")
    updated_budget: BudgetBreakdown = Field(..., description="Recalculated budget breakdown reflecting the change")
    affected_tasks: List[str] = Field(default_factory=list, description="Task titles or IDs requiring modification")
    recommendations: List[str] = Field(default_factory=list, description="Actionable mitigation recommendations")


class ScenarioPreviewResponse(WhatIfResponse):
    scenario_id: str
    base_updated_at: datetime
    expires_at: datetime
    committed_state: EventState
    updated_config: EventConfig
    updated_tasks: TaskList
    critical_risks: List[str] = Field(default_factory=list)


class CommitScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: str = Field(..., pattern=r"^scenario_[a-f0-9]{32}$")


class AnalyzeVendorRequest(BaseModel):

    quote_text: str = Field(
        ...,
        min_length=10,
        description="Raw text, email, or invoice snippet received from the vendor",
    )
    category: Optional[str] = Field(
        default=None,
        description="Optional category hint (e.g. 'catering', 'venue', 'decor')",
    )


class ChatMessageRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        description="User question or instruction for the GenAI event assistant",
    )


# Alias for backwards compatibility / shorthand
ChatRequest = ChatMessageRequest



class ChatResponse(BaseModel):
    reply: str = Field(..., description="Assistant's advice or analysis")
    session_id: str = Field(..., description="Session identifier")
    suggested_actions: List[str] = Field(
        default_factory=list,
        description="Actionable next steps recommended by the assistant",
    )
