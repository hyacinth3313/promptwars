# GenAI Event Planner Backend

A clean, production-grade FastAPI backend for an AI-assisted Event Planner built with **FastAPI**, **Pydantic v2**, and **Groq API** (100% Free Tier).

## 🚀 Key Features

- **100% Free Tier AI Inference**:
  - Powered by **Groq Cloud** using high-speed free models like `llama-3.3-70b-versatile` (configurable via `GROQ_MODEL`).
  - Strict structured JSON outputs matching Pydantic v2 schemas with automated validation and 1-attempt retry.
  - Markdown fence cleaner (`clean_json_response`) ensuring valid JSON parsing.
- **Dedicated Prompt Engineering (`backend/prompts/`)**:
  - `intake_prompt`: Initial event setup generating `BudgetBreakdown` + `TaskList` tailored to Indian market rates in ₹.
  - `tradeoff_prompt`: 2-3 concrete trade-off packages with specific line-item savings to eliminate budget deficits.
  - `timeline_shift_prompt`: Dependency-aware milestone rescheduling for postponed events or late tasks.
  - `vendor_parse_prompt`: Contract auditing detecting hidden charges (GST, diesel generator, corkage, overtime).
  - `whatif_prompt`: Predictive simulation for changes in guest count, budget cuts, or vendor shifts.
- **JSON File-Based State Persistence**:
  - Saved in `state/{session_id}.json` with atomic file writes to prevent corruption.
  - Recursive partial patching (`update_state`).
- **Graceful Degradation**:
  - If `GROQ_API_KEY` is not yet configured, session initialization automatically falls back to deterministic state calculations without crashing.
- **CORS Configured**:
  - Ready out-of-the-box for frontend running on `http://localhost:5173`.

---

## 🔑 Getting a Free Groq API Key

Groq provides a generous free tier with fast inference and no credit card required:

1. Go to [https://console.groq.com/keys](https://console.groq.com/keys).
2. Sign in with Google or GitHub.
3. Click **"Create API Key"**, give it a name, and copy the key (starts with `gsk_...`).
4. Paste the key into your `.env` file as `GROQ_API_KEY`.

Supported free models:
- `llama-3.3-70b-versatile` (Recommended: Default, high intelligence)
- `llama-3.1-8b-instant` (Ultra low latency)
- `qwen/qwen3.8-27b`
- `openai/gpt-oss-120b`

---

## 🛠️ Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```
Update `.env` with your Groq API key:
```env
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### 3. Start the Server
```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
- Interactive OpenAPI Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

---

## 📂 Project Architecture

```
├── backend/
│   ├── ai_client.py       # GroqClient wrapper with retry, schema validation & cleaning
│   ├── config.py          # App settings, environment variables & paths
│   ├── models.py          # Type-safe Pydantic v2 models with field descriptions
│   ├── state_manager.py   # Atomic state persistence & deep update functions
│   ├── main.py            # FastAPI routes & integration
│   └── prompts/           # Specialized prompt functions
│       ├── __init__.py    # Unified prompt exports & system prompts
│       ├── intake.py      # Initial plan generation (budget + tasks)
│       ├── tradeoff.py    # 2-3 trade-off packages for budget deficits
│       ├── timeline.py    # Date shifts & late task dependency recalculation
│       ├── vendor.py      # Forensic quotation audit & hidden fee detection
│       ├── whatif.py      # Scenario modeling (headcount/cost swings)
│       └── planner.py     # Budget, tasks, and conversational prompts
├── state/                 # JSON session storage (keyed by session_id)
├── .env.example           # Environment configuration template
├── requirements.txt       # Python dependencies
└── README.md
```

---

## 🔌 API Endpoints Reference

### Session State CRUD
- `POST /api/sessions`: Create a new session.
- `GET /api/sessions`: List active session IDs.
- `GET /api/sessions/{session_id}`: Retrieve the full `EventState`.
- `POST /api/sessions/{session_id}`: Overwrite `EventState`.
- `PATCH /api/sessions/{session_id}`: Partial update via `update_state`.
- `DELETE /api/sessions/{session_id}`: Delete session.

### GenAI Planner & Budget Optimization (Groq Cloud)
- `POST /api/sessions/{session_id}/intake` (or `/init`): Initialize event from `EventConfig`. Generates balanced `BudgetBreakdown` and 12–18 milestone `TaskItems` using Groq (or deterministic 15-task fallback if unconfigured).
- `POST /api/sessions/{session_id}/recalculate-budget`: Recalculates remaining surplus, overage, and over-budget status. If over-budget, automatically pre-computes 2–3 trade-off options.
- `POST /api/sessions/{session_id}/tradeoffs`: Returns 2–3 concrete, numbered trade-off packages with specific changes (e.g., guest count reduction, floral substitutions), exact ₹ savings, and impact on other categories.
- `POST /api/sessions/{session_id}/apply-tradeoff`: Applies a selected trade-off option by `option_index` or full option object to adjust budget items, adds an execution task to the checklist, and updates state.
- `POST /api/sessions/{session_id}/generate-budget`: AI-optimized budget allocation based on category priorities and Indian market rates.
- `POST /api/sessions/{session_id}/generate-tasks`: Chronological milestone checklist (`3_months`, `1_month`, `1_week`, `day_of`) with dependencies.
### Adaptive Timeline & Task Dependencies
- `GET /api/sessions/{session_id}/tasks`: Returns all tasks grouped by milestone (`3_months`, `1_month`, `1_week`, `day_of`) alongside live progress statistics (`total`, `completed`, `in_progress`, `pending`, `late`, `completion_percentage`).
- `POST /api/sessions/{session_id}/tasks/{task_id}/status`: Updates task execution status (`pending`, `in_progress`, `completed`, `late`). When marked `late`, automatically triggers a downstream dependency cascade pushing child tasks forward.
- `POST /api/sessions/{session_id}/shift-timeline`: Intelligently recalculates due dates when the event date changes or tasks fall late. Enforces prerequisite ordering (`due_date >= parent.due_date`), keeps completed tasks 100% immutable, and reports critical risk warnings.

### GenAI Consultative Advisor & Quotation Audits
- `POST /api/sessions/{session_id}/analyze-vendor`: Audits quotes for hidden charges (GST, generator fuel, corkage, overtime), inclusions, exclusions, and payment terms.
- `POST /api/sessions/{session_id}/what-if`: Simulates changes and saves an isolated, 24-hour scenario preview. Core controls are supplied as `{"delta":{"budget_change":-100000,"guest_count_delta":40,"new_date":"2027-03-14"}}`; the date is optional. Existing absolute `guest_count` and `total_budget` inputs are also supported, without mixing an absolute value with its delta. The response includes `scenario_id`, `committed_state`, `updated_config`, `updated_budget`, `updated_tasks`, and analysis/recommendations. Previewing never changes the saved event.
- `POST /api/sessions/{session_id}/commit-scenario`: Accepts `{"scenario_id":"scenario_<32 hexadecimal characters>"}` and commits the exact stored candidate. Returns the full updated `EventState`. Stale revisions return 409, expired previews return 410, and repeated commits of the accepted scenario return the current saved state without reapplying changes. Verified costs and completed task dates are preserved. Drafts are stored separately under `state/scenarios/` and are ignored by Git.
- `POST /api/sessions/{session_id}/chat`: Context-aware conversational advisor.


