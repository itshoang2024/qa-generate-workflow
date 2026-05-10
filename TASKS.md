# End-to-End Prototype Tasks

Progress rule: when a task in this file is completed, update its checkbox from `[ ]` to `[x]` in the same implementation turn or commit, and keep the `Verify:` line directly below it.

## Status Snapshot (last reviewed 2026-05-10)

| Phase | Done / Total | Notes |
|---|---|---|
| Phase 0 - Repo And Docs | 3 / 5 | GDD path + `.env` handling still open; not blocking. |
| Phase 1 - Backend Stage Completion | 0 / 15 | MVP pipeline runs but S0/S1 split + Project/GDDDocument APIs not started. |
| Phase 2 - Real AI / Notion / Risk | 0 / 11 | Blocked on Phase 1 AgentClient + NotionSyncClient interfaces. |
| Phase 3 - Frontend | 0 / 8 | `frontend/` not scaffolded. |
| Phase 4 - Verification & Submission | 0 / 6 | Final pass; depends on Phase 1-3. |

## Current Focus — S0 / S1 Split + Project & GDDDocument Knowledge Base

This is the foundational slice. It unblocks the rest of Phase 1, the Phase 2 Agent/Notion adapters that consume S1 output, and the Phase 3 frontend project-selection / upload screens. It also resolves the current Task 1 violation where `run_demo()` collapses S0 and S1 into one method.

Recommended order in one implementation slice:

1. Add `S0TriggerRequest` (existing `project_id` OR new `project_name`, plus `gdd_file_ref`) and `POST /api/v1/runs/trigger`.
2. Add `GDDDocument` Pydantic model + repository methods (create, get, list-by-project, latest, next-version).
3. Add Project APIs (`POST /api/v1/projects`, `GET /api/v1/projects`, `GET /api/v1/projects/{project_id}`).
4. Refactor `PipelineService`: split `_stage_s0_trigger()` (mode detect only) from `_stage_s1_context_loader()` (GDDDocument register, parse, actionability, HIL-0 stub, DELTA diff stub).
5. Keep `POST /api/v1/demo-runs` working unchanged so existing tests stay green.

The corresponding open tasks below are the first 9 items of Phase 1 (S0 request model through `GET /projects/{project_id}/gdd-documents`).

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

- [ ] Task: Normalize GDD path behavior so default local runs use a tracked or clearly documented sample file path.
  Verify: `POST /api/v1/demo-runs` completes from a clean shell using documented commands.

- [ ] Task: Decide and implement `.env` handling: either explicit dotenv loading or shell-only env usage documented in every runbook.
  Verify: Provider mode and GDD path behavior are predictable from `/api/v1/health`.

## Phase 1 - Backend Completion By Source-Of-Truth Stages

- [ ] Task: Implement S0 trigger API for GDD upload reference plus project selection.
  Verify: New project selection returns `mode=NEW_GAME`; existing project selection returns `mode=DELTA`.

- [ ] Task: Initialize run and session memory in S0.
  Verify: S0 response includes `{run_id, project_id, gdd_file, mode}` and a run timeline event without parsing the GDD.

- [ ] Task: Add project APIs for game creation, listing, and detail.
  Verify: `POST /api/v1/projects`, `GET /api/v1/projects`, and `GET /api/v1/projects/{project_id}` return enveloped responses.

- [ ] Task: Add S1 GDD raw loading and runtime file handling.
  Verify: Context loader receives the `gdd_file` from S0 and can load DOCX content for parsing.

- [ ] Task: Add `GDDDocument` knowledge-base model and Supabase `gdd_documents` table in S1.
  Verify: Schema includes `gdd_documents` with unique `(project_id, version_id)`.

- [ ] Task: Add GDD document repository methods for create, get, list, latest, and next version.
  Verify: Tests show two S1 loads for one project produce `version_id` values `v1` and `v2`.

- [ ] Task: Store optional GDD version `description` and `description_status`.
  Verify: New documents default to `description=null` and `description_status=PENDING`; user-provided descriptions set `description_status=USER_PROVIDED`.

- [ ] Task: Add S1 structural parse, QA-actionability filter, HIL-0 questions, and DELTA diff stubs.
  Verify: Parser/actionability tests pass and DELTA mode creates a `delta_report` placeholder without calling AI.

- [ ] Task: Add `GET /api/v1/projects/{project_id}/gdd-documents`.
  Verify: Load two documents, call endpoint, and see both versions in latest-first order.

- [ ] Task: Preserve `POST /api/v1/demo-runs` as the stable mock demo path.
  Verify: Existing API and pipeline tests for `/demo-runs` still pass unchanged.

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

## Phase 2 - Real AI, Notion, And Risk Handling

- [ ] Task: Introduce `AgentClient` interface with methods for Agent A, Agent B, and Agent C.
  Verify: Mock agent still passes `pytest tests/test_pipeline.py`.

- [ ] Task: Add real LLM adapter using Task 2 structured JSON contracts.
  Verify: Agent A/B/C outputs validate against JSON schema/Pydantic before persistence.

- [ ] Task: Add JSON repair/retry policy for invalid AI output.
  Verify: A simulated malformed JSON output is repaired or retried, then escalated after the configured max attempts.

- [ ] Task: Preserve mock fallback as `AI_PROVIDER=mock`.
  Verify: Without AI credentials, `POST /api/v1/demo-runs` still completes.

- [ ] Task: Add future LLM-generated GDD version descriptions.
  Verify: `v1` can receive an AI summary and later DELTA versions can receive change summaries without changing the `GDDDocument` API shape.

- [ ] Task: Introduce `NotionSyncClient` interface with mock and real implementations.
  Verify: Mock sync events still match existing API response shape.

- [ ] Task: Implement Task 3 Sync-A/B/C semantics.
  Verify: Epic/story sync happens before task sync, and test case sync happens per approved task.

- [ ] Task: Add real Notion upsert by `external_id` for epics, stories, tasks, and test cases.
  Verify: Running demo with Notion credentials creates or updates Notion records without duplicates.

- [ ] Task: Add Notion schema preflight, rate limiting, replay, and dead-letter handling.
  Verify: Schema mismatch pauses sync; 429 retries with backoff; failed records are replayable.

- [ ] Task: Add Task 4 risk events, dashboard data, and kill-switch thresholds.
  Verify: Simulated hallucination/scope/sync risk creates a stored risk event and routes to the expected HIL or stop state.

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
