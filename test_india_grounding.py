import sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date, timedelta
from backend.models import EventConfig
from backend.state_manager import build_default_state

# ── Birthday (1-year-old) ───────────────────────────────────────────────
bday_cfg = EventConfig(
    session_id="test-bday",
    event_type="birthday",
    event_date=date.today() + timedelta(days=90),
    location="Bangalore",
    total_budget=50000.0,
    guest_count=50,
    priorities={
        "venue": 0.25,
        "catering": 0.35,
        "birthday_cake": 0.05,
        "decoration": 0.10,
        "photography": 0.10,
        "return_gifts": 0.05,
        "invitations": 0.05,  # bumped from 0.02 to make sum = 1.0
        "sound_system": 0.05,  # bumped from 0.03
    },
)
bday_state = build_default_state(bday_cfg)
print(f"Birthday tasks ({len(bday_state.tasks.tasks)}):")
for t in bday_state.tasks.tasks:
    print(f"  [{t.milestone:8}] {t.id:30} | {t.title}")

# Budget check
allocated_total = sum(i.allocated for i in bday_state.budget.items)
print(f"\n  Budget allocated total: Rs.{allocated_total:,.2f} (should be Rs.50,000.00)")
print(f"  Is over budget: {bday_state.budget.is_over_budget}")

# ── Wedding ─────────────────────────────────────────────────────────────
wed_cfg = EventConfig(
    session_id="test-wed",
    event_type="wedding",
    event_date=date.today() + timedelta(days=120),
    location="Bangalore",
    total_budget=1500000.0,
    guest_count=300,
    priorities={
        "venue": 0.25,
        "catering": 0.35,
        "decor": 0.15,
        "photography": 0.10,
        "logistics": 0.05,
        "invitations": 0.02,
        "other": 0.08,
    },
)
wed_state = build_default_state(wed_cfg)
print(f"\nWedding tasks ({len(wed_state.tasks.tasks)}):")
for t in wed_state.tasks.tasks:
    print(f"  [{t.milestone:8}] {t.id:30} | {t.title}")

# ── Forbidden term check ─────────────────────────────────────────────────
all_bday_text = " ".join(
    t.title + " " + t.description for t in bday_state.tasks.tasks
)
forbidden = ["airport pickup", "valet", "makeup artist", "DJ package", "cocktail", "shuttle fleet"]
failures = [f for f in forbidden if f.lower() in all_bday_text.lower()]
if failures:
    print(f"\n[FAIL] Forbidden terms found in birthday tasks: {failures}")
    sys.exit(1)
else:
    print("\n[PASS] No forbidden Western-only terms in birthday fallback tasks")

# ── Prompt grounding spot-check ─────────────────────────────────────────
from backend.prompts.intake import intake_prompt, INTAKE_SYSTEM_PROMPT
prompt = intake_prompt(bday_cfg)
assert "MANDATORY INDIAN EVENT CONTEXT" in prompt, "FAIL: INDIA_CONTEXT missing from intake prompt"
assert "birthday_cake" in prompt or "Birthday" in prompt, "FAIL: birthday task menu missing"
# "airport pickups" must appear only inside the prohibition rule, not as a suggested task
assert "DO NOT add" in prompt or "DO NOT suggest" in prompt or "Never suggest" in prompt, \
    "FAIL: prohibition rules missing from birthday intake prompt"
print("[PASS] intake_prompt contains INDIA_CONTEXT and birthday task menu")

from backend.prompts.tradeoff import tradeoff_prompt, TRADEOFF_SYSTEM_PROMPT
from backend.state_manager import generate_default_tradeoffs
fallback_tr = generate_default_tradeoffs(bday_state, overage=8000.0)
print(f"[PASS] Fallback tradeoffs generated: {len(fallback_tr.options)} options")
for opt in fallback_tr.options:
    print(f"       - {opt.title[:70]}")

print("\nAll checks passed.")
