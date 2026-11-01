from __future__ import annotations

import logging
from collections import deque
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

from models import (
    GroupedTasksResponse,
    TaskItem,
    TaskList,
    TaskProgressStats,
)

logger = logging.getLogger("timeline_utils")


def build_dependency_graph(tasks: List[TaskItem]) -> Dict[str, List[str]]:
    """
    Construct a forward dependency adjacency graph (parent_id -> [child_ids]).
    """
    graph: Dict[str, List[str]] = {task.id: [] for task in tasks}
    for task in tasks:
        for parent_id in task.depends_on:
            if parent_id in graph:
                graph[parent_id].append(task.id)
            else:
                graph[parent_id] = [task.id]
    return graph


def get_downstream_dependencies(tasks: List[TaskItem], task_id: str) -> List[str]:
    """
    Traverse the dependency graph to find all downstream dependent task IDs (direct and transitive).
    """
    graph = build_dependency_graph(tasks)
    visited: Set[str] = set()
    queue = deque(graph.get(task_id, []))

    while queue:
        current = queue.popleft()
        if current not in visited:
            visited.add(current)
            for child in graph.get(current, []):
                if child not in visited:
                    queue.append(child)

    return list(visited)


def validate_and_enforce_dependency_order(
    tasks: List[TaskItem],
    event_date: Optional[date] = None,
) -> List[TaskItem]:
    """
    Validate and enforce chronological dependency ordering across all tasks:
    - Rule 1: A task cannot be due before any of its prerequisite parent tasks (due_date >= parent.due_date).
    - Rule 2: Tasks marked 'completed' are immutable and remain strictly unchanged.
    - Rule 3: Re-align milestone tags if due dates shift across milestone boundaries.
    """
    task_map: Dict[str, TaskItem] = {t.id: t for t in tasks}

    # Iterative forward relaxation over the DAG (up to N passes)
    changed = True
    iterations = 0
    max_iterations = len(tasks) + 1

    while changed and iterations < max_iterations:
        changed = False
        iterations += 1

        for task in tasks:
            # Completed tasks are protected and immutable
            if task.status == "completed":
                continue

            for parent_id in task.depends_on:
                parent = task_map.get(parent_id)
                if not parent:
                    continue

                # Child due date must be on or after parent due date + 1 day buffer
                required_due_date = parent.due_date + timedelta(days=1)
                if event_date and required_due_date > event_date:
                    required_due_date = event_date

                if task.due_date < required_due_date:
                    task.due_date = required_due_date
                    changed = True

                    # Recalibrate milestone tag based on distance to event_date if known
                    if event_date:
                        days_before = (event_date - task.due_date).days
                        if days_before > 60:
                            task.milestone = "3_months"
                        elif days_before > 14:
                            task.milestone = "1_month"
                        elif days_before > 1:
                            task.milestone = "1_week"
                        else:
                            task.milestone = "day_of"

    return tasks


def cascade_task_delay(
    tasks: List[TaskItem],
    delayed_task_id: str,
    delay_days: int = 5,
    event_date: Optional[date] = None,
) -> Tuple[List[TaskItem], List[str]]:
    """
    When a task is marked 'late' or delayed, push its downstream dependent tasks forward.
    - Completed tasks are never pushed or modified.
    - Dependent tasks are pushed forward by delay_days (clamped to event_date).
    - Returns (updated_tasks, list_of_affected_downstream_task_ids).
    """
    task_map = {t.id: t for t in tasks}
    delayed_task = task_map.get(delayed_task_id)

    if not delayed_task:
        return tasks, []

    # If the delayed task itself is not completed and pushed
    downstream_ids = get_downstream_dependencies(tasks, delayed_task_id)
    affected_ids: List[str] = []

    for child_id in downstream_ids:
        child_task = task_map.get(child_id)
        if child_task and child_task.status != "completed":
            new_date = child_task.due_date + timedelta(days=delay_days)
            if event_date and new_date > event_date:
                new_date = event_date

            if new_date != child_task.due_date:
                child_task.due_date = new_date
                affected_ids.append(child_id)

    # Re-enforce strict ordering across dependencies
    tasks = validate_and_enforce_dependency_order(tasks, event_date=event_date)
    return tasks, affected_ids


def recompute_timeline(
    tasks: List[TaskItem],
    original_event_date: date,
    new_event_date: Optional[date] = None,
    late_task_ids: Optional[List[str]] = None,
) -> Tuple[List[TaskItem], List[str]]:
    """
    Deterministic timeline recalibration:
    - Protects completed tasks (saves original state and restores them).
    - Rescales uncompleted tasks if the event date is moved.
    - Marks tasks in late_task_ids as 'late' and cascades delays downstream.
    - Enforces dependency constraints (task due_date >= parent due_date).
    - Generates concrete critical risk warnings.
    """
    if late_task_ids is None:
        late_task_ids = []

    # 1. Snapshot completed tasks to ensure 100% immutability
    completed_snapshots = {
        t.id: (t.status, t.due_date, t.milestone)
        for t in tasks
        if t.status == "completed"
    }

    target_event_date = new_event_date or original_event_date
    date_delta_days = (target_event_date - original_event_date).days

    # 2. Shift dates if event date changed
    if new_event_date and date_delta_days != 0:
        for task in tasks:
            if task.status != "completed":
                task.due_date = task.due_date + timedelta(days=date_delta_days)
                if task.due_date > target_event_date:
                    task.due_date = target_event_date

    # 3. Mark late tasks and cascade delays
    for task in tasks:
        if task.id in late_task_ids and task.status != "completed":
            task.status = "late"
            # Cascade delay of 5 days to downstream dependents
            tasks, _ = cascade_task_delay(
                tasks,
                delayed_task_id=task.id,
                delay_days=5,
                event_date=target_event_date,
            )

    # 4. Strict dependency enforcement
    tasks = validate_and_enforce_dependency_order(tasks, event_date=target_event_date)

    # 5. Restore completed tasks exactly
    for task in tasks:
        if task.id in completed_snapshots:
            orig_status, orig_due, orig_milestone = completed_snapshots[task.id]
            task.status = orig_status
            task.due_date = orig_due
            task.milestone = orig_milestone

    # 6. Formulate risk warnings
    risks: List[str] = []
    if new_event_date and date_delta_days > 0:
        risks.append(f"Event date postponed by {date_delta_days} days to {target_event_date}. Ensure vendor availability is re-confirmed.")
    elif new_event_date and date_delta_days < 0:
        risks.append(f"Event date advanced by {abs(date_delta_days)} days to {target_event_date}. Urgent: compressed prep time across invitations and decor.")

    late_count = sum(1 for t in tasks if t.status == "late")
    if late_count > 0:
        risks.append(f"{late_count} task(s) currently flagged late. Dependent vendor bookings and tastings have been pushed forward.")

    # Check tasks due within 3 days of event date
    crunched_tasks = [
        t.title for t in tasks
        if t.status != "completed" and (target_event_date - t.due_date).days <= 3 and t.milestone != "day_of"
    ]
    if crunched_tasks:
        risks.append(f"High risk of execution bottleneck: {len(crunched_tasks)} task(s) scheduled within 72 hours of the event date.")

    return tasks, risks


def calculate_task_stats(tasks: List[TaskItem]) -> TaskProgressStats:
    """Compute aggregated operational progress statistics."""
    total = len(tasks)
    completed = sum(1 for t in tasks if t.status == "completed")
    in_progress = sum(1 for t in tasks if t.status == "in_progress")
    late = sum(1 for t in tasks if t.status == "late")
    pending = sum(1 for t in tasks if t.status == "pending")

    percentage = round((completed / total) * 100.0, 1) if total > 0 else 0.0

    return TaskProgressStats(
        total=total,
        completed=completed,
        in_progress=in_progress,
        pending=pending,
        late=late,
        completion_percentage=percentage,
    )


def group_tasks_by_milestone(tasks: List[TaskItem]) -> Dict[str, List[TaskItem]]:
    """Group tasks into standard milestones in chronological sequence."""
    grouped: Dict[str, List[TaskItem]] = {
        "3_months": [],
        "1_month": [],
        "1_week": [],
        "day_of": [],
    }

    # Sort tasks by due date
    sorted_tasks = sorted(tasks, key=lambda t: t.due_date)

    for task in sorted_tasks:
        if task.milestone in grouped:
            grouped[task.milestone].append(task)
        else:
            grouped["day_of"].append(task)

    return grouped

