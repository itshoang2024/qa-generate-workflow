# End-to-End Prototype Tasks

Progress rule: when a task in this file is completed, update its checkbox from `[ ]` to `[x]` in the same implementation turn or commit, and keep the `Verify:` line directly below it.

## Status Snapshot (last reviewed 2026-05-11 — post Sync/Risk slice)

| Phase | Done / Total | Notes |
|---|---|---|
| Phase 0 - Repo And Docs | 5 / 5 | Repo docs, backend `.env`, and default GDD path behavior are aligned. |
| Phase 1 - Backend Stage Completion | 16 / 16 | S0/S1 split, Project/GDDDocument APIs, inspection endpoints, `/providers/status`, and router-lane fields all shipped and test-covered. |
| Phase 2 - Real AI / Notion / Risk | 8 / 11 | NotionSyncClient interface, Sync-A/B/C phases, RiskEvent + kill switch + sign-off shipped; Agent A retry/repair + OpenAI Agent A adapter shipped. Real Agent B/C, real Notion adapter, Notion schema preflight/rate limit/dead-letter still open. |
| Phase 3 - Frontend | 0 / 8 | `frontend/` not scaffolded. |
| Phase 4 - Verification & Submission | 0 / 6 | Final pass; depends on Phase 2-3. |

## Current Focus — Frontend Demo App (Phase 3)

Backend is now feature-complete for the homework's core narrative: every stage from Task 1 (S0..S7 + HIL-0..HIL-3 + Final Coverage) is implemented; Task 2 contracts (`AgentAOutput` + JSON schema + structured-output OpenAI adapter) are wired with bounded retry/repair; Task 3 Sync-A/B/C separation with `external_id` → `notion_page_id` mapping is verified by tests (10 / 9 / 36 events per demo run); Task 4 RiskEvent model + kill switch + sign-off endpoint + risk/sync summary in the coverage report all ship and are test-covered.

The remaining backend work (real Agent B/C LLM adapter, real Notion `httpx` adapter with retry/rate-limit/dead-letter) gives marginal demo value compared to a frontend that finally shows the workflow to a reviewer. The submission is a homework deliverable — visual proof of the run dashboard, GDD version history, HIL queues, sync log, and coverage report is what makes the design tangible.

Recommended order in the frontend slice:

1. Scaffold `frontend/` with Next.js 14 + TypeScript + Tailwind. Add an API client wrapper around the `{ data, meta, error }` envelope so every page can reuse `useEnvelope()`.
2. **Project + GDD screen** — `POST /api/v1/projects` and `POST /api/v1/runs/trigger`. New project → `NEW_GAME`, existing project picker → `DELTA`. Show GDD version history from `GET /api/v1/projects/{id}/gdd-documents` with `parent_document_id` links and `delta_report` summary.
3. **Run dashboard + timeline** — `POST /api/v1/demo-runs` button plus a list from `GET /api/v1/runs`; per-run timeline from `GET /api/v1/runs/{id}/timeline` showing every `StageEvent` from S0 through `FINAL_COVERAGE`.
4. **HIL review screens** — wire `GET /api/v1/runs/{id}/review-queues/HIL-0..HIL-3` plus `POST /api/v1/runs/{id}/hil-0/resolutions` and `POST /api/v1/review-decisions`. Show lane badges (AUTO / BATCH / BLOCK), group by reviewer / feature / epic exactly like the API returns.
5. **Inspection panels** — features, epics, stories, tasks, test cases, validation issues, agent runs (with `attempt_count` / `retry_exhausted` for Agent A). Display `delta_status` on features and `sync_phase` on sync events.
6. **Risk + sync log + coverage report** — `risk-events`, `sync-events` (filter by `sync_phase`), and the extended coverage payload including `risk_summary`, `sync_summary`, `gdd_version_metadata`, `sign_off`. Add a `POST /api/v1/runs/{id}/sign-off` button gated to QA Lead role.
7. **Provider status badge** in the global header from `GET /api/v1/providers/status` so a reviewer instantly sees `mock` / `openai` / `supabase` state.

Parallelizable backend follow-ups (lower priority, can ship after a working frontend MVP):

- Real Agent B/C OpenAI adapters analogous to `OpenAIAgentClient.analyze_gdd`.
- Real Notion adapter (`NotionSyncClient` httpx implementation) with schema preflight, rate-limit/backoff, dead-letter queue, and a `POST /sync-replay` producer that actually moves `SyncStatus.FAILED` → `REPLAYED`.
- Per-task Agent C triggering (Task 1 says C should fire per approved task as parallel jobs; today C is one batch call).
- Final English-only pass over `Task-1..4.md` for the submission package.

## Known Conventions Not Yet Documented

- Assignee values in code (`qa_roster.py`) are ASCII-stripped (`Ngoc Anh`, `Quan`) for parser/JSON safety; Task-2 design uses diacritic forms (`Ngọc Anh`, `Quân`). When real Agent B is wired, the structured-output adapter must normalize between the two.
- Final submission must be translated fully to English (homework requires English deliverable). Vietnamese explanatory prose in `Task-1..4.md` will need a final pass before submission.

## Phase 0 - Repo Hygiene And Documentation Alignment

- [x] Task: Add root `PLAN.md` and `TASKS.md`, plus backend-specific `backend/PLAN.md` and `backend/TASKS.md`.
  Verify: `Test-Path PLAN.md; Test-Path TASKS.md; Test-Path backend\PLAN.md; Test-Path backend\TASKS.md` returns `True` for all.

- [x] Task: Update `README.md` documentation map to include the four planning files.
  Verify: `rg -n "PLAN.md|TASKS.md|backend/PLAN.md|backend/TASKS.md" README.md`.

- [x] Task: Audit and revise docs against the four root source-of-truth solution files.
  Verify: `rg -n "source of truth|S0 does not parse|Sync-A|structured JSON|risk" PLAN.md backend/PLAN.md docs AGENTS.md README.md`.

- [x] Task: Normalize GDD path behavior so default local runs use a tracked or clearly documented sample file path.
  Verify: `POST /api/v1/demo-runs` completes from a clean shell using documented commands.

- [x] Task: Decide and implement `.env` handling: either explicit dotenv loading or shell-only env usage documented in every runbook.
  Verify: Provider mode and GDD path behavior are predictable from `/api/v1/health`.

## Phase 1 - Backend Completion By Source-Of-Truth Stages

- [x] Task: Implement S0 trigger API for GDD upload reference plus project selection.
  Verify: New project selection returns `mode=NEW_GAME`; existing project selection returns `mode=DELTA`.

- [x] Task: Initialize run and session memory in S0.
  Verify: S0 response includes `{run_id, project_id, gdd_file, mode}` and a run timeline event without parsing the GDD.

- [x] Task: Add project APIs for game creation, listing, and detail.
  Verify: `POST /api/v1/projects`, `GET /api/v1/projects`, and `GET /api/v1/projects/{project_id}` return enveloped responses.

- [x] Task: Add S1 GDD raw loading and runtime file handling.
  Verify: Context loader receives the `gdd_file` from S0 and can load DOCX content for parsing.

- [x] Task: Add `GDDDocument` knowledge-base model and Supabase `gdd_documents` table in S1.
  Verify: Schema includes `gdd_documents` with unique `(project_id, version_id)`.

- [x] Task: Add GDD document repository methods for create, get, list, latest, and next version.
  Verify: Tests show two S1 loads for one project produce `version_id` values `v1` and `v2`.

- [x] Task: Store optional GDD version `description` and `description_status`.
  Verify: New documents default to `description=null` and `description_status=PENDING`; user-provided descriptions set `description_status=USER_PROVIDED`.

- [x] Task: Add S1 structural parse, QA-actionability filter, HIL-0 questions, and DELTA diff stubs.
  Verify: Parser/actionability tests pass and DELTA mode creates a `delta_report` placeholder without calling AI.

- [x] Task: Add `GET /api/v1/projects/{project_id}/gdd-documents`.
  Verify: Load two documents, call endpoint, and see both versions in latest-first order.

- [x] Task: Preserve `POST /api/v1/demo-runs` as the stable mock demo path.
  Verify: Existing API and pipeline tests for `/demo-runs` still pass unchanged.

- [x] Task: Add `GET /api/v1/runs/{run_id}/epics`.
  Verify: Run demo, call endpoint, and receive five epics in the response envelope. Covered by `test_epics_endpoint_returns_generated_epics`.

- [x] Task: Add `GET /api/v1/runs/{run_id}/stories`.
  Verify: Run demo, call endpoint, and receive five stories in the response envelope. Covered by `test_stories_endpoint_returns_generated_stories`.

- [x] Task: Add `GET /api/v1/runs/{run_id}/agent-runs`.
  Verify: Run demo, call endpoint, and receive Agent A, Agent B, and Agent C snapshots. Covered by `test_agent_runs_endpoint_returns_agent_snapshots`.

- [x] Task: Add `GET /api/v1/runs/{run_id}/review-decisions`.
  Verify: Create a review decision, call endpoint, and see the stored decision. Covered by `test_review_decisions_endpoint_returns_hil_decisions`.

- [x] Task: Add provider readiness details to `/api/v1/health` or `GET /api/v1/providers/status`.
  Verify: Response shows AI provider, Notion provider, repository provider, and whether required credentials are present. Covered by `test_provider_status_endpoint_reports_credential_readiness`.

- [x] Task: Add router lane fields or derived API output for auto, needs-review, and blocked items.
  Verify: Low-confidence fixture features/tasks appear in the needs-review lane. `Feature`, `QATask`, `TestCase` expose computed `lane`; `validate_*_with_routing` sets `review_status` per Task 1 thresholds. Covered by `test_demo_run_api_produces_enveloped_response`, `test_review_queue_endpoint_groups_items_by_reviewer_feature_and_epic`, `test_review_decision_approval_updates_lane_and_removes_item_from_queue`.

## Phase 2 - Real AI, Notion, And Risk Handling

- [x] Task: Introduce `AgentClient` interface with methods for Agent A, Agent B, and Agent C.
  Verify: Abstract base is at `app/services/agents/__init__.py`; `MockAgentClient` + `OpenAIAgentClient` implement it. Covered by `test_mock_agent_client_implements_agent_client_contract`.

- [x] Task: Add real LLM adapter using Task 2 structured JSON contracts.
  Verify: `OpenAIAgentClient.analyze_gdd` POSTs to `/v1/responses` with `AGENT_A_RESPONSE_SCHEMA` (strict JSON schema). Output validates via `AgentAOutput` Pydantic model before persistence. Agent B/C still fall back to mock — `provider_for(operation)` reflects this. `build_agent_client(settings)` in `agents/factory.py` selects mock/openai/real.

- [x] Task: Add JSON repair/retry policy for invalid AI output.
  Verify: `run_agent_a_with_retries` in `app/services/agent_a_retry.py` retries on schema failure + traceability gap + uncovered actionable sections up to `MAX_AGENT_A_ATTEMPTS=3`, then emits `agent_a_retry_exhausted` and blocks suspect features. Covered by `test_agent_a_retry_*` (5 tests).

- [x] Task: Preserve mock fallback as `AI_PROVIDER=mock`.
  Verify: Without AI credentials, `POST /api/v1/demo-runs` still completes. `MockAgentClient` is selected when `AI_PROVIDER=mock`. Bogus provider returns clear 422 — covered by `test_demo_run_reports_clear_error_for_unsupported_ai_provider`.

- [ ] Task: Add future LLM-generated GDD version descriptions.
  Verify: `v1` can receive an AI summary and later DELTA versions can receive change summaries without changing the `GDDDocument` API shape. (`description_status` enum already supports `AI_GENERATED` — only the producer is missing.)

- [x] Task: Introduce `NotionSyncClient` interface with mock and real implementations.
  Verify: Abstract base at `app/services/notion/__init__.py`; `MockNotionSyncClient` at `app/services/notion/mock.py` implements it and tracks `epic_page_id_by_epic_id` / `story_page_id_by_story_id` / `task_page_id_by_task_id` for relation resolution. Real provider still pending.

- [x] Task: Implement Task 3 Sync-A/B/C semantics.
  Verify: `pipeline.run_demo()` calls `_sync_a_epics_stories()` (after Agent B + Validation B), `_sync_b_tasks()` (filtered to `AUTO_APPROVED`/`APPROVED`), and `_sync_c_test_cases()` (per approved task, flips task `status` → `Test Cases Ready`). Demo emits 10 Sync-A + 9 Sync-B + 36 Sync-C events. Covered by `test_sync_events_endpoint_shows_sync_a_b_c_phases`.

- [ ] Task: Add real Notion upsert by `external_id` for epics, stories, tasks, and test cases.
  Verify: Running demo with Notion credentials creates or updates Notion records without duplicates. Provider hook is in place (`NotionSyncClient` interface + `notion_sync_client` injection on `PipelineService`); the httpx adapter itself is not implemented.

- [ ] Task: Add Notion schema preflight, rate limiting, replay, and dead-letter handling.
  Verify: Schema mismatch pauses sync; 429 retries with backoff; failed records are replayable. (`replay_failed_sync_events` + `POST /api/v1/runs/{id}/sync-replay` exist on the repository/API; need a producer of `SyncStatus.FAILED` events inside a real Notion adapter.)

- [x] Task: Add Task 4 risk events, dashboard data, and kill-switch thresholds.
  Verify: `RiskEvent` model + `RiskSeverity` enum + repository `add_risk_events`/`list_risk_events` + `GET /api/v1/runs/{run_id}/risk-events`. `risk_events_from_validation_issues` maps validator codes → risk events. `kill_switch_state` trips when S1 count ≥ 3 and aborts the run before Agent C with a stored `kill_switch_tripped` risk event. Covered by `test_risk_events_*`, `test_risk_events_endpoint_returns_validator_escalations`.

- [x] Task: Add reviewer sign-off endpoint and surface in coverage report.
  Verify: `POST /api/v1/runs/{run_id}/sign-off` records `signed_off_by` + `signed_off_at` on the `Run` and updates `coverage_report["sign_off"]`. Coverage report also includes `risk_summary`, `sync_summary` (by phase + status), and `gdd_version_metadata`. Covered by `test_sign_off_endpoint_updates_run_and_coverage_report`.

## Phase 3 - Frontend Demo App

- [ ] Task: Scaffold `frontend/` with Next.js + TypeScript.
  Verify: `npm run dev` starts and shows a basic app shell.

- [ ] Task: Add API client wrapper for the backend response envelope.
  Verify: Frontend can call `/api/v1/health` and render provider mode.

- [ ] Task: Build project selection/create screen for S0 mode detection.
  Verify: New project creates `NEW_GAME`; existing project creates `DELTA`.

- [ ] Task: Build GDD upload and version history flow for S1.
  Verify: Uploading a GDD registers the next `version_id` and displays parse status.

- [ ] Task: Build run dashboard with create demo run button and run list.
  Verify: Clicking create run starts a backend run and displays `COMPLETED`.

- [ ] Task: Build timeline and coverage views.
  Verify: UI shows S0 through Final and coverage counts after a demo run.

- [ ] Task: Build HIL-0, feature review, task review, and test-case review views.
  Verify: UI shows clarification questions, low-confidence items, blocked tasks, and test-case gaps.

- [ ] Task: Build sync-events and risk-events views.
  Verify: UI shows `external_id`, target type, action, status, payload summary, risk severity, and owner action.

## Phase 4 - End-to-End Verification And Submission Polish

- [ ] Task: Run backend tests.
  Verify: `conda activate qa-generator; cd backend; pytest` passes.

- [ ] Task: Run backend lint.
  Verify: `conda activate qa-generator; cd backend; python -m ruff check .` passes.

- [ ] Task: Run frontend lint/build once frontend exists.
  Verify: `cd frontend; npm run lint; npm run build` passes.

- [ ] Task: Run full mock-mode demo from frontend.
  Verify: One run displays GDD version metadata, sections, features, tasks, test cases, validation issues, sync events, risk events, and coverage.

- [ ] Task: Run real AI + real Notion smoke test when credentials are configured.
  Verify: Demo run creates or updates Notion records and stores successful `SyncEvent` rows.

- [ ] Task: Write final demo script in README.
  Verify: A new user can follow README commands and reproduce the happy path.

- [ ] Task: Capture final screenshots or short demo walkthrough notes.
  Verify: Submission package includes visual proof of dashboard, HIL, GDD versions, coverage, risk handling, and Notion sync.
