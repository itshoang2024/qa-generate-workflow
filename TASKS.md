# End-to-End Prototype Tasks

## Phase 0 - Repo Hygiene And Planning

- [ ] Task: Add root `PLAN.md` and `TASKS.md`, plus backend-specific `backend/PLAN.md` and `backend/TASKS.md`.
  Verify: `Test-Path PLAN.md; Test-Path TASKS.md; Test-Path backend\PLAN.md; Test-Path backend\TASKS.md` returns `True` for all.

- [ ] Task: Update `README.md` documentation map to include the four planning files.
  Verify: `rg -n "PLAN.md|TASKS.md|backend/PLAN.md|backend/TASKS.md" README.md`.

- [ ] Task: Normalize GDD path behavior so default local runs use a tracked or clearly documented sample file path.
  Verify: `POST /api/v1/demo-runs` completes from a clean shell using documented commands.

- [ ] Task: Decide and implement `.env` handling: either explicit dotenv loading or shell-only env usage documented in every runbook.
  Verify: Provider mode and GDD path behavior are predictable from `/api/v1/health`.

## Phase 1 - Backend API Completeness

- [ ] Task: Add `GET /api/v1/runs/{run_id}/epics`.
  Verify: Run demo, call endpoint, and receive five epics in the response envelope.

- [ ] Task: Add `GET /api/v1/runs/{run_id}/stories`.
  Verify: Run demo, call endpoint, and receive five stories in the response envelope.

- [ ] Task: Add `GET /api/v1/runs/{run_id}/agent-runs`.
  Verify: Run demo, call endpoint, and receive Agent A, Agent B, and Agent C snapshots.

- [ ] Task: Add `GET /api/v1/runs/{run_id}/review-decisions`.
  Verify: Create a review decision, call endpoint, and see the stored decision.

- [ ] Task: Add provider readiness details to `/api/v1/health` or `GET /api/v1/providers/status`.
  Verify: Response shows AI provider, Notion provider, repository provider, and whether required credentials are present.

- [ ] Task: Add router lane fields or derived API output for auto, needs-review, and blocked items.
  Verify: Low-confidence fixture features/tasks appear in the needs-review lane.

## Phase 2 - Real AI And Notion Integrations

- [ ] Task: Introduce `AgentClient` interface with methods for Agent A, Agent B, and Agent C.
  Verify: Mock agent still passes `pytest tests/test_pipeline.py`.

- [ ] Task: Add real LLM adapter behind `AI_PROVIDER=real`.
  Verify: With credentials configured, Agent A/B/C outputs validate against Pydantic models and schema checks.

- [ ] Task: Preserve mock fallback as `AI_PROVIDER=mock`.
  Verify: Without AI credentials, `POST /api/v1/demo-runs` still completes.

- [ ] Task: Introduce `NotionSyncClient` interface with mock and real implementations.
  Verify: Mock sync events still match existing API response shape.

- [ ] Task: Add real Notion upsert by `external_id` for epics, stories, tasks, and test cases.
  Verify: Running demo with Notion credentials creates or updates Notion records without duplicates.

- [ ] Task: Add Notion schema preflight check.
  Verify: Missing required Notion fields produce a clear validation/sync issue before partial sync.

- [ ] Task: Add sync replay coverage for failed real Notion events.
  Verify: Manually create or simulate failed `SyncEvent`, call `POST /api/v1/runs/{run_id}/sync-replay`, and see retry count increment.

## Phase 3 - Frontend Demo App

- [ ] Task: Scaffold `frontend/` with Next.js + TypeScript.
  Verify: `npm run dev` starts and shows a basic app shell.

- [ ] Task: Add API client wrapper for the backend response envelope.
  Verify: Frontend can call `/api/v1/health` and render provider mode.

- [ ] Task: Build run dashboard with create demo run button and run list.
  Verify: Clicking create run starts a backend run and displays `COMPLETED`.

- [ ] Task: Build timeline and coverage views.
  Verify: UI shows S0 through Final and coverage counts after a demo run.

- [ ] Task: Build GDD section and feature review views.
  Verify: UI shows actionable/skipped/ambiguous sections and low-confidence features.

- [ ] Task: Build task board grouped by epic/story/assignee.
  Verify: UI shows all 11 demo tasks grouped and highlights needs-review tasks.

- [ ] Task: Build test-case view with category grouping.
  Verify: UI shows four categories per task.

- [ ] Task: Build review action UI using `POST /api/v1/review-decisions`.
  Verify: Approving a task from UI creates a review decision visible through the API.

- [ ] Task: Build sync-events view for mock and real Notion events.
  Verify: UI shows `external_id`, target type, action, status, and payload summary.

## Phase 4 - End-to-End Verification And Submission Polish

- [ ] Task: Run backend tests.
  Verify: `conda activate qa-generator; cd backend; pytest` passes.

- [ ] Task: Run backend lint.
  Verify: `conda activate qa-generator; cd backend; python -m ruff check .` passes.

- [ ] Task: Run frontend lint/build once frontend exists.
  Verify: `cd frontend; npm run lint; npm run build` passes.

- [ ] Task: Run full mock-mode demo from frontend.
  Verify: One run displays sections, features, tasks, test cases, validation issues, sync events, and coverage.

- [ ] Task: Run real AI + real Notion smoke test when credentials are configured.
  Verify: Demo run creates or updates Notion records and stores successful `SyncEvent` rows.

- [ ] Task: Write final demo script in README.
  Verify: A new user can follow README commands and reproduce the happy path.

- [ ] Task: Capture final screenshots or short demo walkthrough notes.
  Verify: Submission package includes visual proof of dashboard, coverage, and Notion sync.

