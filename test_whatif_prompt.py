"""Prompt payload isolation and size checks; run with backend on the Python path."""
import json
import unittest
from datetime import date
from types import SimpleNamespace

from models import WhatIfResponse
from prompts.whatif import WHATIF_SYSTEM_PROMPT, whatif_prompt


class WhatIfPromptTests(unittest.TestCase):
    def test_only_minimal_fields_reach_prompt_even_for_large_sessions(self):
        omitted = "PRIVATE_SESSION_DETAIL" * 10000
        state = SimpleNamespace(
            config=SimpleNamespace(total_budget=500000, guest_count=100,
                                   event_date=date(2027, 7, 10), location=omitted,
                                   event_type="wedding", priorities={"venue": .5}),
            budget=SimpleNamespace(items=[SimpleNamespace(
                category=category, allocated=100000, estimated=120000,
                verified=110000, notes=omitted,
            ) for category in ["venue", "catering", "decor", "photography", "logistics"]]),
            tasks=omitted, vendors=omitted, applied_tradeoffs=omitted,
        )
        delta = {"budget_change": -20000, "guest_count_delta": 20, "new_date": "2027-08-10"}
        prompt = whatif_prompt(state, {**delta, "target_config": {"location": omitted}, "tasks": omitted})
        context, _ = json.JSONDecoder().raw_decode(prompt.split("SCENARIO CONTEXT:\n", 1)[1])
        self.assertEqual(context, {
            "total_budget": 500000, "guest_count": 100, "event_date": "2027-07-10",
            "budget_items": [{"category": item.category, "allocated": 100000} for item in state.budget.items],
            "delta": delta,
        })
        self.assertNotIn("PRIVATE_SESSION_DETAIL", prompt)
        # Count bytes conservatively, including the schema appended by the AI client.
        full_prompt = WHATIF_SYSTEM_PROMPT + prompt + json.dumps(WhatIfResponse.model_json_schema(), indent=2)
        size = len(full_prompt.encode("utf-8"))
        self.assertLess(size + 400, 6000)  # Room for the client's formatting instructions.
        self.assertEqual(delta["budget_change"], -20000)


if __name__ == "__main__":
    unittest.main()
