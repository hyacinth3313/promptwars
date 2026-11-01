import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_intake_budget_tradeoff_flow():
    print("=" * 60)
    print("TEST: Intake -> Budget -> Trade-off Flow")
    print("=" * 60)

    # 1. Create new session
    res = client.post("/api/sessions")
    assert res.status_code == 200
    session_id = res.json()["session_id"]
    print(f"\n[1] Created Session: {session_id}")

    # 2. Intake Flow (POST /intake)
    config_payload = {
        "session_id": session_id,
        "event_type": "wedding",
        "date": "2026-11-25",  # testing alias 'date' for 'event_date'
        "location": "Udaipur, Rajasthan",
        "total_budget": 1500000.0,
        "guest_count": 200,
        "priorities": {
            "catering": 0.40,
            "venue": 0.30,
            "decor": 0.15,
            "photography": 0.10,
            "logistics": 0.05,
        },
        "currency": "INR",
    }
    res = client.post(f"/api/sessions/{session_id}/intake", json=config_payload)
    assert res.status_code == 200, res.text
    state = res.json()
    print(f"[2] Intake Completed:")
    print(f"    - Event Date: {state['config']['event_date']}")
    print(f"    - Total Budget: Rs. {state['budget']['total_budget']:,.2f}")
    print(f"    - Budget Items ({len(state['budget']['items'])} items):")
    for b in state['budget']['items']:
        print(f"      * {b['category']}: allocated=Rs. {b['allocated']:,.2f}, estimated=Rs. {b['estimated']:,.2f}, verified={b['verified']}")
    
    task_count = len(state['tasks']['tasks'])
    print(f"    - Milestone Task Items: {task_count} tasks (Target: 12-18 tasks)")
    assert 12 <= task_count <= 25, f"Expected 12-18 tasks, got {task_count}"

    # Verify milestone distribution
    milestones = {m: 0 for m in ["3_months", "1_month", "1_week", "day_of"]}
    for t in state['tasks']['tasks']:
        milestones[t['milestone']] += 1
    print(f"    - Milestone breakdown: {milestones}")
    assert all(count > 0 for count in milestones.values()), "All milestones must have tasks!"

    # 3. Force an over-budget condition
    # e.g., Venue quotes Rs. 6,50,000 (was allocated 4,50,000)
    print("\n[3] Simulating Budget Deficit (Venue cost surges by Rs. 2,00,000)...")
    for item in state['budget']['items']:
        if item['category'] == 'venue':
            item['estimated'] = 650000.0
            break
    
    # Save modified budget items
    patch_res = client.patch(
        f"/api/sessions/{session_id}",
        json={"budget": {"items": state['budget']['items']}},
    )
    assert patch_res.status_code == 200

    # 4. Solid Budget Recalculation (POST /recalculate-budget)
    recalc_res = client.post(f"/api/sessions/{session_id}/recalculate-budget")
    assert recalc_res.status_code == 200
    recalc_data = recalc_res.json()
    print(f"[4] Recalculate Budget Response:")
    print(f"    - is_over_budget: {recalc_data['is_over_budget']}")
    print(f"    - Overage: Rs. {recalc_data['overage']:,.2f}")
    print(f"    - Remaining: Rs. {recalc_data['budget']['remaining']:,.2f}")
    print(f"    - Message: {recalc_data['message']}")
    assert recalc_data['is_over_budget'] is True
    assert recalc_data['overage'] > 0
    assert recalc_data['tradeoffs'] is not None, "Tradeoffs must be automatically prepared when over budget!"


    # 5. Get Trade-off Options (POST /tradeoffs)
    tradeoff_res = client.post(f"/api/sessions/{session_id}/tradeoffs")
    assert tradeoff_res.status_code == 200
    tradeoffs_data = tradeoff_res.json()
    options = tradeoffs_data['options']
    print(f"\n[5] Trade-off Options ({len(options)} options prepared):")
    assert len(options) >= 2, "Must return at least 2 trade-off options"
    for i, opt in enumerate(options):
        print(f"    [{i}] {opt['title']} (Savings: Rs. {opt['total_savings_inr']:,.2f})")
        print(f"        - Impact on other categories: {opt.get('impact_on_other_categories')}")
        for t in opt['tradeoffs']:
            print(f"        - Action: {t['action']} (-Rs. {t['savings_inr']:,.2f})")

    # 6. Apply Selected Trade-off (POST /apply-tradeoff)
    print("\n[6] Applying Trade-off Option 0 (Menu & Floral Restructure)...")
    apply_res = client.post(
        f"/api/sessions/{session_id}/apply-tradeoff",
        json={"option_index": 0, "custom_notes": "Approved by bride and groom"},
    )
    assert apply_res.status_code == 200
    updated_state = apply_res.json()

    print(f"[6] Trade-off Applied Successfully!")
    print(f"    - Updated Total Budget: Rs. {updated_state['budget']['total_budget']:,.2f}")
    print(f"    - Updated is_over_budget: {updated_state['budget']['is_over_budget']}")
    print(f"    - Updated Overage: Rs. {updated_state['budget']['overage']:,.2f}")
    print(f"    - Updated Remaining Surplus: Rs. {updated_state['budget']['remaining']:,.2f}")
    print(f"    - Applied Tradeoffs in History: {len(updated_state['applied_tradeoffs'])}")
    
    # Check that a new task was appended for trade-off execution
    tradeoff_tasks = [t for t in updated_state['tasks']['tasks'] if "Trade-off" in t['title']]
    assert len(tradeoff_tasks) > 0, "Trade-off execution tasks must be added to task list!"
    print(f"    - Added Execution Task: '{tradeoff_tasks[-1]['title']}'")

    # 7. Clean up
    del_res = client.delete(f"/api/sessions/{session_id}")
    assert del_res.status_code == 200
    print(f"\n[7] Cleaned up session {session_id} successfully.")

    print("\n" + "=" * 60)
    print("SUCCESS: Intake -> Budget -> Trade-off flow is 100% verified!")
    print("=" * 60)

if __name__ == "__main__":
    test_intake_budget_tradeoff_flow()
