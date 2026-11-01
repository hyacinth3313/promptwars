"""Isolated HTTP tests for preview and commit; AI is mocked and real sessions are untouched."""
import json
import tempfile
import unittest
import uuid
import io
from contextlib import redirect_stdout
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from main import app, ai_client
from config import settings
from models import BudgetBreakdown, BudgetItem, EventConfig, EventState, TaskItem, TaskList, WhatIfResponse
from state_manager import get_state, save_state


class ScenarioApiTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="planner-scenario-tests-")
        self.addCleanup(directory.cleanup)
        directory_patch = patch.object(settings, "state_dir", Path(directory.name))
        directory_patch.start()
        self.addCleanup(directory_patch.stop)
        key_patch = patch.object(ai_client, "api_key", "test-only-no-network")
        key_patch.start()
        self.addCleanup(key_patch.stop)
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        self.addCleanup(self.client_context.__exit__, None, None, None)
        self.session_id = f"sess_test_{uuid.uuid4().hex}"
        self.url = f"/api/sessions/{self.session_id}"
        state = EventState(
            config=EventConfig(session_id=self.session_id, event_type="wedding", event_date=date(2027, 7, 10), location="Bengaluru", total_budget=1000, guest_count=100, priorities={"venue": .3, "catering": .7}),
            budget=BudgetBreakdown(total_budget=1000, remaining=300, overage=0, is_over_budget=False, items=[
                BudgetItem(category="venue", allocated=300, estimated=300, verified=200),
                BudgetItem(category="catering", allocated=700, estimated=500),
                BudgetItem(category="logistics", allocated=0, estimated=10, verified=0),
            ]),
            tasks=TaskList(tasks=[
                TaskItem(id="done", title="Book venue", description="Completed booking", milestone="1_month", due_date=date(2027, 6, 1), status="completed"),
                TaskItem(id="menu", title="Confirm menu", description="Arrange tasting", milestone="1_month", due_date=date(2027, 6, 10), depends_on=["done"]),
            ]),
        )
        save_state(self.session_id, state)
        self.original = self.client.get(self.url).json()
        self.ai_response = WhatIfResponse(
            scenario_summary="A smaller budget and a few more guests.", financial_impact="Adjust the catering estimate.", affected_tasks=["menu"], recommendations=["Confirm a revised catering quote."],
            updated_budget=BudgetBreakdown(total_budget=9999, remaining=9999, overage=0, is_over_budget=False, items=[
                BudgetItem(category="Venue", allocated=240, estimated=100, verified=50),
                BudgetItem(category="catering", allocated=560, estimated=650, verified=900),
            ]),
        )

    def simulate(self, delta=None):
        with patch.object(ai_client, "generate_structured", new=AsyncMock(return_value=self.ai_response)) as ai:
            response = self.client.post(f"{self.url}/what-if", json={"delta": delta or {"budget_change": -200, "guest_count_delta": 20, "new_date": "2027-07-20"}})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn('"delta"', ai.call_args.kwargs["user"])
            self.assertNotIn('"target_config"', ai.call_args.kwargs["user"])
            return response.json()

    def test_preview_is_isolated_and_preserves_verified_costs_and_completed_tasks(self):
        preview = self.simulate()
        self.assertEqual(self.client.get(self.url).json(), self.original)
        self.assertEqual(preview["committed_state"], self.original)
        self.assertEqual(preview["updated_config"]["total_budget"], 800)
        self.assertEqual(preview["updated_config"]["guest_count"], 120)
        self.assertEqual(preview["updated_config"]["event_date"], "2027-07-20")
        items = {item["category"].lower(): item for item in preview["updated_budget"]["items"]}
        self.assertEqual(items["venue"]["verified"], 200)
        self.assertIsNone(items["catering"]["verified"])
        self.assertEqual(items["logistics"]["verified"], 0)
        self.assertEqual(preview["updated_budget"]["overage"], 50)
        self.assertTrue(preview["updated_budget"]["is_over_budget"])
        tasks = {task["id"]: task for task in preview["updated_tasks"]["tasks"]}
        self.assertEqual(tasks["done"], self.original["tasks"]["tasks"][0])
        self.assertEqual(tasks["menu"]["due_date"], "2027-06-20")

    def test_commit_persists_exact_preview_and_retries_do_not_reapply_deltas(self):
        preview = self.simulate()
        body = {"scenario_id": preview["scenario_id"]}
        first = self.client.post(f"{self.url}/commit-scenario", json=body)
        self.assertEqual(first.status_code, 200, first.text)
        committed = first.json()
        self.assertEqual(committed["budget"], preview["updated_budget"])
        self.assertEqual(committed["config"], preview["updated_config"])
        self.assertEqual(committed["tasks"], preview["updated_tasks"])
        self.assertEqual(committed["last_committed_scenario_id"], preview["scenario_id"])
        self.assertEqual(self.client.get(self.url).json(), committed)
        repeated = self.client.post(f"{self.url}/commit-scenario", json=body)
        self.assertEqual(repeated.json(), committed)
        self.client.post(f"{self.url}/tasks/menu/status", json={"status": "completed"})
        newer = self.client.get(self.url).json()
        self.assertEqual(self.client.post(f"{self.url}/commit-scenario", json=body).json(), newer)

    def test_stale_preview_is_rejected_without_overwriting_newer_plan(self):
        preview = self.simulate()
        response = self.client.patch(self.url, json={"config": {"guest_count": 90}})
        self.assertEqual(response.status_code, 200)
        before = self.client.get(self.url).json()
        response = self.client.post(f"{self.url}/commit-scenario", json={"scenario_id": preview["scenario_id"]})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get(self.url).json(), before)

    def test_expired_preview_is_rejected(self):
        preview = self.simulate()
        path = settings.state_dir / "scenarios" / f"{preview['scenario_id']}.json"
        draft = json.loads(path.read_text(encoding="utf-8"))
        draft["preview"]["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        path.write_text(json.dumps(draft), encoding="utf-8")
        response = self.client.post(f"{self.url}/commit-scenario", json={"scenario_id": preview["scenario_id"]})
        self.assertEqual(response.status_code, 410)
        self.assertEqual(self.client.get(self.url).json(), self.original)

    def test_scenarios_are_session_bound_and_commit_accepts_only_a_saved_id(self):
        preview = self.simulate()
        response = self.client.post("/api/sessions/sess_other/commit-scenario", json={"scenario_id": preview["scenario_id"]})
        self.assertEqual(response.status_code, 404)
        response = self.client.post(f"{self.url}/commit-scenario", json={"scenario_id": "../../arbitrary"})
        self.assertEqual(response.status_code, 422)
        response = self.client.post(f"{self.url}/commit-scenario", json={"scenario_id": preview["scenario_id"], "updated_budget": {"total_budget": 1}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get(self.url).json(), self.original)

    def test_invalid_controls_are_rejected_before_ai_is_called(self):
        with patch.object(ai_client, "generate_structured", new=AsyncMock()) as ai:
            for delta in [{"budget_change": -1000}, {"budget_change": "Infinity"}, {"guest_count_delta": -100}, {"guest_count_delta": 1.5}, {"new_date": "2027-02-31"}, {"guest_count": 120, "guest_count_delta": 20}]:
                response = self.client.post(f"{self.url}/what-if", json={"delta": delta})
                self.assertEqual(response.status_code, 422, response.text)
            ai.assert_not_called()

    def test_legacy_absolute_controls_still_work(self):
        preview = self.simulate({"guest_count": 150, "total_budget": 2000})
        self.assertEqual(preview["updated_config"]["guest_count"], 150)
        self.assertEqual(preview["updated_config"]["total_budget"], 2000)

    def test_a_plan_changed_during_ai_generation_cannot_be_overwritten(self):
        async def change_plan(**kwargs):
            changed = get_state(self.session_id)
            changed.config.location = "New venue"
            save_state(self.session_id, changed)
            return self.ai_response
        with patch.object(ai_client, "generate_structured", new=AsyncMock(side_effect=change_plan)):
            preview = self.client.post(f"{self.url}/what-if", json={"delta": {"budget_change": 100}}).json()
        response = self.client.post(f"{self.url}/commit-scenario", json={"scenario_id": preview["scenario_id"]})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get(self.url).json()["config"]["location"], "New venue")

    def test_concurrent_previews_cannot_both_replace_the_same_revision(self):
        first = self.simulate({"budget_change": -200})
        second = self.simulate({"budget_change": -100})
        def commit(preview):
            return self.client.post(f"{self.url}/commit-scenario", json={"scenario_id": preview["scenario_id"]})
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(commit, [first, second]))
        self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
        winner = next(response.json() for response in responses if response.status_code == 200)
        self.assertEqual(self.client.get(self.url).json(), winner)

    def test_existing_budget_flow_under_session_write_serialization(self):
        import test_intake_budget_tradeoff_flow as flow
        with patch.object(flow, "client", self.client), patch.object(ai_client, "api_key", ""), redirect_stdout(io.StringIO()):
            flow.test_intake_budget_tradeoff_flow()

    def test_existing_adaptive_timeline_flow_under_session_write_serialization(self):
        import test_timeline_adaptive_flow as flow
        with patch.object(flow, "client", self.client), patch.object(ai_client, "api_key", ""), redirect_stdout(io.StringIO()):
            flow.test_adaptive_timeline_and_dependencies()


if __name__ == "__main__":
    unittest.main()
