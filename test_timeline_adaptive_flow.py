import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_adaptive_timeline_and_dependencies():
    print("=" * 65)
    print("TEST: Adaptive Timeline & Task Dependency System")
    print("=" * 65)

    # 1. Create session
    res = client.post("/api/sessions")
    assert res.status_code == 200
    session_id = res.json()["session_id"]
    print(f"\n[1] Created Session: {session_id}")

    # 2. Intake Flow
    config = {
        "session_id": session_id,
        "event_type": "wedding",
        "date": "2026-12-20",
        "location": "Jaipur, Rajasthan",
        "total_budget": 2000000.0,
        "guest_count": 250,
        "priorities": {
            "catering": 0.40,
            "venue": 0.30,
            "decor": 0.15,
            "photography": 0.10,
            "logistics": 0.05,
        },
        "currency": "INR",
    }
    intake_res = client.post(f"/api/sessions/{session_id}/intake", json=config)
    assert intake_res.status_code == 200, intake_res.text
    intake_state = intake_res.json()
    all_tasks = intake_state["tasks"]["tasks"]
    print(f"[2] Intake complete. Generated {len(all_tasks)} tasks.")

    # 3. GET /tasks (Grouped by milestone + stats)
    get_tasks_res = client.get(f"/api/sessions/{session_id}/tasks")
    assert get_tasks_res.status_code == 200
    tasks_data = get_tasks_res.json()
    stats = tasks_data["stats"]
    milestones = tasks_data["milestones"]

    print(f"\n[3] GET /tasks grouped by milestone:")
    print(f"    - Total: {stats['total']}, Pending: {stats['pending']}, Late: {stats['late']}, Completed: {stats['completed']}")
    for m_name in ["3_months", "1_month", "1_week", "day_of"]:
        print(f"    - Milestone '{m_name}': {len(milestones[m_name])} tasks")
        assert len(milestones[m_name]) > 0, f"Milestone '{m_name}' must contain tasks"

    # Identify foundational root task (e.g. task-venue-book) and an early independent task
    venue_task = next((t for t in all_tasks if "venue" in t["id"].lower()), all_tasks[0])
    completed_candidate = next((t for t in all_tasks if t["id"] != venue_task["id"] and len(t["depends_on"]) == 0), all_tasks[1])

    # 4. Mark one early task as "completed"
    print(f"\n[4] Marking task '{completed_candidate['id']}' as COMPLETED...")
    orig_completed_due_date = completed_candidate["due_date"]
    orig_completed_milestone = completed_candidate["milestone"]

    complete_res = client.post(
        f"/api/sessions/{session_id}/tasks/{completed_candidate['id']}/status",
        json={"status": "completed"},
    )
    assert complete_res.status_code == 200
    comp_data = complete_res.json()
    assert comp_data["task"]["status"] == "completed"
    print(f"    - Task '{completed_candidate['id']}' is now COMPLETED (due: {orig_completed_due_date})")

    # 5. Mark foundational task as "late" -> Triggers automatic downstream cascade
    print(f"\n[5] Marking foundational task '{venue_task['id']}' as LATE...")
    late_res = client.post(
        f"/api/sessions/{session_id}/tasks/{venue_task['id']}/status",
        json={"status": "late"},
    )
    assert late_res.status_code == 200
    late_data = late_res.json()
    assert late_data["task"]["status"] == "late"
    assert late_data["timeline_shifted"] is True
    affected = late_data["downstream_affected_task_ids"]
    print(f"    - Automatically pushed {len(affected)} downstream dependent tasks forward!")
    print(f"    - Affected downstream IDs: {affected[:5]}...")

    # Verify downstream tasks moved forward
    updated_tasks_map = {t["id"]: t for t in late_data["tasks"]["tasks"]}
    for child_id in affected[:3]:
        orig_child = next(t for t in all_tasks if t["id"] == child_id)
        new_child = updated_tasks_map[child_id]
        print(f"      * {child_id}: {orig_child['due_date']} -> {new_child['due_date']}")
        assert new_child["due_date"] >= orig_child["due_date"]

    # 6. Call POST /shift-timeline with date postponement and late tasks
    print("\n[6] Calling POST /shift-timeline (postponing event date to 2027-01-15)...")
    shift_payload = {
        "new_event_date": "2027-01-15",
        "late_task_ids": [venue_task["id"]],
    }
    shift_res = client.post(
        f"/api/sessions/{session_id}/shift-timeline",
        json=shift_payload,
    )
    assert shift_res.status_code == 200, shift_res.text
    shift_data = shift_res.json()
    final_tasks = shift_data["updated_tasks"]["tasks"]
    final_map = {t["id"]: t for t in final_tasks}

    print(f"    - Shift analysis: {shift_data['reasoning'][:120]}...")
    print(f"    - Critical risks flagged: {len(shift_data['critical_risks'])}")
    for r in shift_data["critical_risks"]:
        print(f"      * Risk: {r}")

    # 7. Assertions:
    print("\n[7] Verifying System Invariants:")
    
    # 7a. Completed task stayed 100% untouched
    comp_task_final = final_map[completed_candidate["id"]]
    assert comp_task_final["status"] == "completed", "Completed status must remain completed!"
    assert comp_task_final["due_date"] == orig_completed_due_date, "Completed due_date must NOT be shifted!"
    assert comp_task_final["milestone"] == orig_completed_milestone, "Completed milestone must NOT be shifted!"
    print("    [PASS] Completed tasks stay 100% untouched and immutable.")

    # 7b. Dependent tasks have moved forward
    venue_task_final = final_map[venue_task["id"]]
    for child_id in affected:
        child_task_final = final_map[child_id]
        # Dependency check: child due date cannot be before parent due date
        assert child_task_final["due_date"] >= venue_task_final["due_date"], (
            f"Child {child_id} due ({child_task_final['due_date']}) cannot be before parent ({venue_task_final['due_date']})"
        )
    print("    [PASS] Dependent tasks have moved forward and respect prerequisite order.")

    # 7c. General dependency invariant check across all tasks
    for task in final_tasks:
        for parent_id in task["depends_on"]:
            if parent_id in final_map:
                parent = final_map[parent_id]
                assert task["due_date"] >= parent["due_date"], (
                    f"Task {task['id']} ({task['due_date']}) is due before parent {parent_id} ({parent['due_date']})"
                )
    print("    [PASS] Universal dependency order strictly verified across entire task DAG.")

    # 8. Clean up
    del_res = client.delete(f"/api/sessions/{session_id}")
    assert del_res.status_code == 200
    print(f"\n[8] Cleaned up session {session_id} successfully.")

    print("\n" + "=" * 65)
    print("SUCCESS: Adaptive Timeline & Task Dependency flow verified 100%!")
    print("=" * 65)

if __name__ == "__main__":
    test_adaptive_timeline_and_dependencies()

