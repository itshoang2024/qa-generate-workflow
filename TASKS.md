# End-to-End Prototype Tasks

Progress rule: when a task in this file is completed, update its checkbox from `[ ]` to `[x]` in the same implementation turn or commit, and keep the `Verify:` line directly below it.

## Status Snapshot (last reviewed 2026-05-11)

| Phase | Done / Total | Notes |
|---|---|---|
| Phase 0 - Repo And Docs | 5 / 5 | Repo docs, backend `.env`, and default GDD path behavior are aligned. |
| Phase 1 - Backend Stage Completion | 16 / 16 | S0/S1 split, Project/GDDDocument APIs, inspection endpoints, `/providers/status`, and router-lane fields all shipped and test-covered. |
| Phase 2 - Real AI / Notion / Risk | 2 / 11 | `AgentClient` abstract interface + mock implementation done; Sync interface, real adapters, and risk events still open. |
| Phase 3 - Frontend | 0 / 8 | `frontend/` not scaffolded. |
| Phase 4 - Verification & Submission | 0 / 6 | Final pass; depends on Phase 2-3. |

## Current Focus — NotionSyncClient Interface + Sync-A/B/C Semantics + Risk Event Model

Phase 1 is complete. The pipeline runs end-to-end in mock mode, lane routing is wired through validators / models / review queues, and HIL-0..HIL-3 queue endpoints work. The next credibility slice is to mirror the `AgentClient` extraction pattern on the Notion side and introduce the Task 4 risk event model so the prototype can demonstrate Task 3 + Task 4 behavior without real credentials.

Recommended order in one implementation slice:

1. Extract `NotionSyncClient` abstract base under `app/services/notion/` (or `app/services/notion_sync_client.py`). Move the current `MockNotionSyncClient` to implement it; keep method signatures stable.
2. Split sync into Sync-A (epic + story, fires after HIL-1 approval / Router A AUTO), Sync-B (task, fires after HIL-2 / Router B AUTO), Sync-C (test case, fires after HIL-3 / Router C AUTO). Today `pipeline.run_demo()` fires all three in one block after S5 and S7 — separate them so a future real adapter can throttle / batch independently.
3. Persist `external_id` → simulated `notion_page_id` mapping on the mock so tasks can reference epics/stories by page id (Task 3 contract).
4. Add `RiskEvent` domain model + repository methods + `GET /api/v1/runs/{run_id}/risk-events`. Wire deterministic risk emission from validators: hallucination-suspect (missing_source_section), scope-drift (low coverage), assignee-invalid, sync-failure simulation, dedup duplicate.
5. Add `POST /api/v1/runs/{run_id}/sign-off` and surface sign-off state in the coverage report.
6. Add a `KillSwitchState` boolean / counter in session memory and a sentinel that pauses Agent C if hallucination/rejection thresholds are breached during a single run.

The corresponding open tasks below are the first three items of Phase S5b (NotionSyncClient interface, Sync-A separation, Sync-B separation) plus the Phase Final risk/kill-switch/sign-off items.

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
  Verify: Abstract base is at `app/services/agents/__init__.py`; `MockAgentClient` implements it. Covered by `test_mock_agent_client_implements_agent_client_contract`.

- [ ] Task: Add real LLM adapter using Task 2 structured JSON contracts.
  Verify: Agent A/B/C outputs validate against JSON schema/Pydantic before persistence.

- [ ] Task: Add JSON repair/retry policy for invalid AI output.
  Verify: A simulated malformed JSON output is repaired or retried, then escalated after the configured max attempts.

- [x] Task: Preserve mock fallback as `AI_PROVIDER=mock`.
  Verify: Without AI credentials, `POST /api/v1/demo-runs` still completes. `MockAgentClient` is selected when no real adapter is wired.

- [ ] Task: Add future LLM-generated GDD version descriptions.
  Verify: `v1` can receive an AI summary and later DELTA versions can receive change summaries without changing the `GDDDocument` API shape. (`description_status` enum already supports `AI_GENERATED` — only the producer is missing.)

- [ ] Task: Introduce `NotionSyncClient` interface with mock and real implementations.
  Verify: Mock sync events still match existing API response shape. (Today `MockNotionSyncClient` exists as a concrete class with no abstract base — mirror the `AgentClient` pattern.)

- [ ] Task: Implement Task 3 Sync-A/B/C semantics.
  Verify: Epic/story sync (Sync-A) is its own pipeline step after HIL-1, task sync (Sync-B) fires after HIL-2 or Router B AUTO, and test-case sync (Sync-C) fires per approved task. Today all four upserts run in one block at S5 and S7.

- [ ] Task: Add real Notion upsert by `external_id` for epics, stories, tasks, and test cases.
  Verify: Running demo with Notion credentials creates or updates Notion records without duplicates.

- [ ] Task: Add Notion schema preflight, rate limiting, replay, and dead-letter handling.
  Verify: Schema mismatch pauses sync; 429 retries with backoff; failed records are replayable. (`replay_failed_sync_events` exists on the repository; needs a producer of `SyncStatus.FAILED` events.)

- [ ] Task: Add Task 4 risk events, dashboard data, and kill-switch thresholds.
  Verify: Simulated hallucination/scope/sync risk creates a stored risk event and routes to the expected HIL or stop state. Add `RiskEvent` model + repository + `GET /api/v1/runs/{run_id}/risk-events`.

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
