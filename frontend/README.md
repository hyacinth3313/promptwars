# Gather · GenAI Event Planner frontend

React 18, Vite, TypeScript, Tailwind CSS, React Router, Axios, and Lucide React.

```sh
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Run the FastAPI backend separately on port 8000 using the root README instructions. `VITE_API_URL` optionally overrides `http://localhost:8000/api`; copy `.env.example` to `.env.local` to configure it. No backend secrets belong in frontend environment variables.

`npm run build` checks TypeScript and produces `dist/`. `npm run preview` serves the production build. Production hosting must rewrite client routes to `index.html`.

`npm test` verifies priority allocation, budget calculations, timeline grouping and progress, local date shifts, vendor comparison and question parsing, scenario input validation and comparison, isolated sample previews, and API request contracts. Run `python -m unittest test_scenarios -q` from the repository root for isolated backend preview/commit and planning regression tests; these use temporary storage and mocked AI.

The controlled event setup modal includes five priority sliders with a live 100% total and a reset action. Moving one slider proportionally redistributes the other four using whole percentage points. Submit validates the date, location, positive budget, whole guest count, and priority total, then converts percentages to backend weights (0–1). Loading disables edits and duplicate submissions; failures preserve entered details and reuse the session on retry. Escape and the close button dismiss the modal when no submission is pending.

- `/`: landing page and event setup dialog. Start Planning creates a backend session, then initializes its budget and tasks via `/intake`.
- `/planner/:sessionId`: dashboard with Overview, Budget, Timeline, Vendors, and What-If navigation. Live session fetches and task completion use the backend.
- `/planner/demo`: clearly labeled sample event with temporary task interactions. It never writes to the backend.

The Budget tab shows total budget, remaining funds, any overage, and category cards with allocations, estimates, confirmed costs, notes, and progress bars. “Recalculate budget” posts to `/recalculate-budget`; “Generate Trade-off Options” posts to `/tradeoffs` with `force_refresh=true`. Applying a selected package posts its full reviewed option to `/apply-tradeoff`, uses the returned state immediately, and then fetches the saved session to synchronize all tabs. Applied packages remain visible in history. Alternatives from an applied batch are retired until fresh suggestions are generated. If an apply response is lost, the UI reconciles saved state before allowing a retry.

The sample Budget tab includes an over-budget example, temporary local trade-off actions, and a reset button. Sample actions never call the backend. Currency on budget cards follows the event configuration; trade-off savings explicitly use INR to match the backend’s `savings_inr` fields.

The Timeline tab groups tasks into 3 Months Out, 1 Month Out, 1 Week Out, and Day Of, sorted by due date. It includes progress statistics, status badges, dependency names and statuses, and actions for Pending, In Progress, Completed, and Late. Completed tasks can be explicitly reopened. Date changes post `new_date` to `/shift-timeline`; the response updates the board immediately, then a session fetch synchronizes the saved date and tasks across all tabs. Reasoning and critical risk warnings appear after a shift.

Marking a task Late posts to the task status endpoint, which already cascades a five-day delay to unfinished downstream tasks. The board immediately reflects the returned task list and offers a full timeline review. That review sends an empty `late_task_ids` list to `/shift-timeline`, avoiding a second delay for the same task. A failed or uncertain update asks for a saved-state refresh before further changes. Sample timeline interactions are deterministic, local, and preserve completed tasks during shifts; live sessions use the backend's adaptive timeline engine.

The Vendors tab accepts pasted quote text and a service category, posts to `/analyze-vendor` with `add_to_state=true`, and refreshes the session after showing the returned quote. The endpoint already persists the quote, so the frontend does not append it through a second write. Detailed cards preserve arbitrary line-item metadata, highlight flagged fees, and show inclusions, exclusions, payment terms, capacity, and notes. Quotes remain under review unless the backend marks them verified; analysis does not change the event budget.

With two or more quotes, the comparison view offers two distinct vendor selectors and highlights price differences, flagged fees, and inclusions listed only in each quote by normalized wording. Different service categories are explicitly called out. Vendor amounts display INR, matching the backend parsing contract. Lower headline prices are not treated as lower final costs.

“Questions to Ask This Vendor” uses the existing `/chat` endpoint with the exact selected VendorQuote and asks for a JSON question list. Questions are parsed into a clean list, with support for code-fenced JSON and numbered responses. Malformed or failed replies show a per-vendor retry; questions are cached in the current view, not persisted as VendorQuote fields. Sample mode offers two fixed example quotes and clearly labeled local question lists; it does not pretend to analyze arbitrary pasted text or call the backend.

The What-If tab accepts signed budget and guest-count deltas plus an optional event date. `POST /what-if` returns a stored preview with the committed baseline, proposed config/budget/tasks, reasoning, and recommendations. The side-by-side comparison highlights projected costs, remaining money, overage, category changes, and affected tasks. Running or discarding a preview does not write proposed values into the committed event. Editing controls requires a fresh run before committing.

“Commit This Scenario” posts only `scenario_id` to `/commit-scenario` and refreshes the full saved event. The backend commits the exact server-stored candidate, preserves verified costs and completed tasks, and rejects expired previews or previews based on an older event revision. Commit retries are idempotent using `last_committed_scenario_id`. Preview records live in ignored `state/scenarios/` files and expire after 24 hours. The file-backed server serializes event mutations per session within one process. Restart the FastAPI backend to load the added endpoint; live simulations require configured AI credentials as before.

The sample What-If tab uses an explicitly labeled local estimate: catering and logistics scale with the guest count, other costs remain fixed, allocations follow the total budget, and date changes use the local dependency-aware timeline. Committing updates only the temporary sample state. Setup failures keep the event dialog open with a retryable error, reusing its created session ID.

Backend model names and snake_case fields are preserved in `src/types/index.ts`. Theme colors and shared clay shadows live in `tailwind.config.js`; reusable UI elements are in `src/components/ui.tsx`. Fonts load from Google Fonts with local sans-serif fallbacks. The hero illustration uses CSS and requires no remote image assets.
