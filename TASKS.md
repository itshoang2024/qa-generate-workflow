# End-to-End Prototype Tasks

Progress rule: when a task in this file is completed, update its checkbox from `[ ]` to `[x]` in the same implementation turn or commit, and keep the `Verify:` line directly below it.

## Status Snapshot (last reviewed 2026-05-12 - Phase 1.8 docs pass, awaiting implementation)

| Phase | Done / Total | Notes |
|---|---|---|
| Phase 0 - Repo And Docs | 5 / 5 | Repo docs, backend `.env`, and default GDD path behavior are aligned. |
| Phase 1 - Backend Stage Completion | 16 / 16 | S0/S1 split, Project/GDDDocument APIs, inspection endpoints, `/providers/status`, and router-lane fields all shipped and test-covered. |
| Phase 1.5 - Stage Orchestration Endpoints | 7 / 7 | Per-stage endpoints, blocking HIL gates, bulk HIL-0 resolution, and regression tests shipped. |
| Phase 1.6 - Agent B Coverage Guard | 5 / 5 | Real Agent B cannot persist/sync a partial plan that omits approved HIL-1 features or epic candidates. |
| **Phase 1.8 - Agent B Hierarchical Decomposition** | **9 / 9 docs, 0 / N implementation** | **Docs pass complete (2026-05-12); implementation pending.** Splits Agent B into B1 epic / B2 stories / B3 tasks with fan-out, EpicReviewPanel full-edit, AgentBJobBoard, Sync-A1/A2 split. Unblocks `run_fc5f488fe767` real-provider timeout. |
| Phase 2 - Real AI / Notion / Risk | 8 / 11 | NotionSyncClient interface, Sync-A/B/C phases, RiskEvent + kill switch + sign-off shipped; Agent A retry/repair plus OpenAI Agent A/B adapters shipped. Real Agent C, real Notion adapter, Notion schema preflight/rate limit/dead-letter still open. |
| Phase 3 - Frontend | 10 / 12 | Stage-aware dashboard CTA, stage mutation hooks, inline HIL approval, bulk HIL-0, and offline font build support shipped; deep-link HIL routes and sync/risk pages remain. |
| Phase 4 - Verification & Submission | 4 / 8 | Backend tests/lint and frontend lint/typecheck/build pass; screenshots, README polish, browser walkthrough capture, and real Notion smoke remain. |

## Current Focus - Verification, Deep Links, And Submission Polish

The previous E2E blocker is closed. The backend has per-stage endpoints, the frontend can advance through Agent A/B/C/finalize from `<NextStagePanel>`, HIL-1/2/3 are blocking gates, and HIL-0 bulk resolution prevents the Supabase/http2 disconnect caused by 19 parallel resolution requests.

The real-provider Agent B regression found in `run_1cefe76fe58c` is now covered by a backend guard: Agent B cannot advance to Sync-A/B when it returns only `Gameplay Logic Scope` while approved HIL-1 features / epic candidates remain uncovered.

Remaining implementation and polish should focus on:

1. **Manual browser walkthrough capture** - drive `Load Context -> HIL-0 bulk proceed -> Agent A -> HIL-1 -> Agent B -> HIL-2 -> Agent C -> HIL-3 -> Finalize -> Sign off` against the running stack and record screenshots.
2. **Frontend deep-link routes** - `/runs/[run_id]/hil/[tier]`, `/sync-log`, `/risk`, and `/sign-off` remain useful for screenshots and reviewer navigation, even though the inline dashboard flow can complete the pipeline.
3. **README/submission polish** - document both `/demo-runs` batch mode and the stepped UI walkthrough, plus offline `next/font/google` build behavior.
4. **Real providers** - real Agent C and real Notion remain follow-up work; mock mode is the stable local demo path.

Lower-priority follow-ups (do **after** the walkthrough works):

- Real Agent C OpenAI adapter analogous to `OpenAIAgentClient.analyze_gdd` / `plan_qa_tasks`.
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

## Phase 1.5 - Stage Orchestration Endpoints (new)

These tasks unblock the stepped E2E walkthrough. Each per-stage endpoint advances the run by exactly one stage block and refuses re-entry / out-of-order calls / unresolved HIL queues with HTTP 409.

- [x] Task: Extract `_stage_s2_agent_a(run, sections, *, auto_approve)`, `_stage_s4_agent_b(run, *, auto_approve)`, `_stage_s6_agent_c(run)`, `_stage_finalize(run)` methods on `PipelineService` so per-stage endpoints can reuse them. `run_demo()` becomes a thin wrapper calling them in order with `auto_approve=True`.
  Verify: `pytest -k pipeline` still asserts 8 features / 5 epics / 5 stories / 11 tasks / 44 test cases from `/demo-runs`.

- [x] Task: Add `POST /api/v1/runs/{run_id}/agent-a`. Preconditions: `current_stage == S1_CONTEXT_LOADER`. Effect: run Agent A with bounded retry, persist features, run Validation A, record risk events, advance to `S3_VALIDATION_A`. Errors: 404 run not found; 409 `wrong_stage` if already advanced; 409 `gdd_not_loaded` if S1 was never run.
  Verify: New `test_agent_a_endpoint_advances_run_to_s3` test posts to the endpoint after `/runs/trigger` + `/context` and asserts `current_stage`, feature count, and a `S2_AGENT_A` + `S3_VALIDATION_A` event pair on the timeline.

- [x] Task: Add `POST /api/v1/runs/{run_id}/agent-b`. Preconditions: `current_stage == S3_VALIDATION_A`, HIL-1 queue empty. Effect: build HIL-1 session snapshot from current feature approvals, run Agent B, validate tasks, run Sync-A + Sync-B, update kill switch, advance to `S5_VALIDATION_B_SYNC`. Errors: 409 `hil_gate_blocked` with `{ tier: "HIL-1", pending_count }` when queue has `NEEDS_REVIEW`/`BLOCKED` items.
  Verify: New `test_agent_b_endpoint_blocks_on_unresolved_hil1` test runs Agent A, leaves one feature in `NEEDS_REVIEW`, and asserts the call returns 409 with the right code. After resolving via `/review-decisions`, the call succeeds and produces Sync-A + Sync-B events.

- [x] Task: Add `POST /api/v1/runs/{run_id}/agent-c`. Preconditions: `current_stage == S5_VALIDATION_B_SYNC`, HIL-2 queue empty. Effect: run Agent C, validate test cases, run Sync-C, flip approved tasks to `Test Cases Ready`, advance to `S7_VALIDATION_C_SYNC`.
  Verify: Same shape as Agent B test; assert 44 test cases and `S6_AGENT_C` + `S7_VALIDATION_C_SYNC` events.

- [x] Task: Add `POST /api/v1/runs/{run_id}/finalize`. Preconditions: `current_stage == S7_VALIDATION_C_SYNC`, HIL-3 queue empty. Effect: build coverage report, mark run `COMPLETED`, advance to `FINAL_COVERAGE`.
  Verify: Stepped walkthrough test runs trigger → context → agent-a → agent-b → agent-c → finalize and asserts the run lands at `FINAL_COVERAGE` with the same coverage counts as `/demo-runs` (`auto_approve=True`).

- [x] Task: Centralise HIL precondition check (`_assert_hil_gate_clear(run_id, tier)`) and `wrong_stage` enforcement on `PipelineService`. Use it from all four endpoints.
  Verify: Posting `/agent-c` directly after `/context` returns 409 `wrong_stage`; posting `/agent-a` twice returns 409 `wrong_stage` on the second call.

- [x] Task: Add bulk HIL-0 resolution endpoint for the dashboard's `Proceed with flag (n)` action.
  Verify: `POST /api/v1/runs/{run_id}/hil-0/resolutions/bulk` validates the requested question IDs, rejects duplicates, inserts all resolutions in one repository call, marks the questions resolved, and is covered by `test_hil0_bulk_resolution_resolves_open_questions`.

## Phase 1.8 - Agent B Hierarchical Decomposition

Docs-only pass at this stage. Implementation tasks will be added once docs land; backend/frontend TASKS files own their detailed implementation checklists.

### Docs

- [x] Task: Update `Task-1-AI-workflow-design.md` to split S4 into S4.1 (Agent B1 Epic Planner), S4.2 (Agent B2 Story Planner, fan-out per epic), S4.3 (Agent B3 Task Planner, fan-out per story). Update mục 2 (7-component map), section 4 S4 detail, mục 5 (rule-vs-AI table), mục 6 (failure handling table), mục 7 (flowchart).
  Verify: `rg -n "S4\.1|S4\.2|S4\.3|EpicReviewPanel" Task-1-AI-workflow-design.md` finds the new sections.

- [x] Task: Update `Task-2-Agent-prompts-JSON.md` to split Agent B into B1/B2/B3 sub-agents with separate prompts and JSON schemas. Keep legacy bundled Agent B at bottom under "Legacy bundled mode" for mock fixture compatibility.
  Verify: `rg -n "Agent B1|Agent B2|Agent B3|QA-Planner-B[123]" Task-2-Agent-prompts-JSON.md` finds the three sub-agent sections and prompts.

- [x] Task: Update `Task-3-Sync-to-Notion.md` for Sync-A1 (epics post-S4.1) + Sync-A2 (stories post-S4.2 per epic). Update mục 1, mục 4, mục 5 external_id format, mục 10 orchestration flow.
  Verify: `rg -n "Sync-A1|Sync-A2" Task-3-Sync-to-Notion.md` finds 4+ occurrences.

- [x] Task: Update `Task-4-Risk-Failure-handling.md` adding section 7a (Agent B sub-stage timeout / partial fan-out) and 7b (cross-epic/cross-story task duplication). Update mục 4 cross-story dedup. Update kill switch threshold note. Update summary table.
  Verify: `rg -n "sub-stage timeout|cross-epic|cross-story|Agent B sub-stage" Task-4-Risk-Failure-handling.md` finds the new sections.

- [x] Task: Update root `PLAN.md` with Phase 1.8 description + diagnosis note for `run_fc5f488fe767`.
  Verify: `rg -n "Phase 1\.8|hierarchical decomposition|run_fc5f488fe767" PLAN.md`.

- [x] Task: Update root `TASKS.md` (this file) with Phase 1.8 status snapshot and docs checklist (this section).
  Verify: `rg -n "Phase 1\.8" TASKS.md` shows status row + section header.

- [x] Task: Update `backend/PLAN.md` and `backend/TASKS.md` with detailed Phase 1.8 implementation plan and checklist.
  Verify: `rg -n "S4_1_AGENT_B_EPICS|AgentBJob|plan_epics|plan_stories|plan_tasks" backend/PLAN.md backend/TASKS.md`.

- [x] Task: Update `frontend/PLAN.md` and `frontend/TASKS.md` with Screen 3.6 (AgentBJobBoard) + EpicReviewPanel (full-edit drag/merge/split) + NextStagePanel state machine updates.
  Verify: `rg -n "AgentBJobBoard|EpicReviewPanel|S4_1|S4_2|S4_3" frontend/PLAN.md frontend/TASKS.md`.

- [x] Task: Update `docs/architecture.md`, `docs/contracts/pipeline-contract.md`, and `docs/contracts/api-contract.md` for new stages, AgentBJob artifact, new endpoints, new validation/risk codes.
  Verify: `rg -n "agent-b/epics|agent-b/stories|agent-b/tasks|agent-b-jobs|S4_1_AGENT_B_EPICS" docs/`.

## Phase 1.6 - Agent B Coverage Guard

This bugfix slice prevents real Agent B from silently producing a partial plan like `run_1cefe76fe58c`, where only the gameplay epic was returned and all downstream tasks were assigned to the gameplay owner.

- [x] Task: Add a deterministic Agent B coverage validator.
  Verify: A unit test feeds approved features across multiple feature types plus a gameplay-only Agent B plan and receives `missing_agent_b_feature_coverage` and `missing_agent_b_epic_coverage` issues.

- [x] Task: Add coverage feedback to the Agent B input/prompt contract.
  Verify: Retry input includes missing feature IDs, missing epic candidate IDs/titles, and the rule that every approved feature must produce at least one story/task unless explicitly skipped.

- [x] Task: Add bounded Agent B retry on coverage gaps.
  Verify: A fake AgentClient that returns a partial plan first and a complete plan second produces two AgentRun attempts and completes `/agent-b` without duplicate artifacts.

- [x] Task: Block Sync-A/B when Agent B coverage remains incomplete after retries.
  Verify: `/api/v1/runs/{run_id}/agent-b` returns a structured `agent_b_coverage_exhausted` error, records validation/risk evidence, and creates no Sync-A/B events for the partial plan.

- [x] Task: Add a regression fixture for the `run_1cefe76fe58c` failure shape.
  Verify: The gameplay-only `Gameplay Logic Scope` output cannot advance to HIL-2; a complete multi-epic output still passes existing mock-mode counts.

## Phase 2 - Real AI, Notion, And Risk Handling

- [x] Task: Introduce `AgentClient` interface with methods for Agent A, Agent B, and Agent C.
  Verify: Abstract base is at `app/services/agents/__init__.py`; `MockAgentClient` + `OpenAIAgentClient` implement it. Covered by `test_mock_agent_client_implements_agent_client_contract`.

- [x] Task: Add real LLM adapter using Task 2 structured JSON contracts.
  Verify: `OpenAIAgentClient.analyze_gdd` and `OpenAIAgentClient.plan_qa_tasks` POST to `/v1/responses` with strict JSON schemas (`AGENT_A_RESPONSE_SCHEMA`, `AGENT_B_RESPONSE_SCHEMA`). Output validates via `AgentAOutput` / `AgentBOutput` Pydantic models before persistence. Agent C still falls back to mock — `provider_for(operation)` reflects this. `build_agent_client(settings)` in `agents/factory.py` selects mock/openai/real.

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

Per-screen task tracking now lives in `frontend/TASKS.md`. The high-level slices below mirror that file so a reader who only opens this document still sees Phase 3 status.

- [x] Task: Scaffold `frontend/` with Next.js + TypeScript.
  Verify: `npm run dev` starts and shows a basic app shell.

- [x] Task: Add API client wrapper for the backend response envelope, typed query / mutation layer.
  Verify: `frontend/src/lib/api.ts` + `queries.ts` + `mutations.ts` cover every `/api/v1` route; `npx tsc --noEmit` clean.

- [x] Task: Build project selection/create screen for S0 mode detection.
  Verify: New project creates `NEW_GAME`; existing project creates `DELTA`.

- [x] Task: Build GDD upload and version history flow for S1.
  Verify: `/projects/{id}` lists `v1`, `v2`, ... with `parent_document_id` and `description_status` badges.

- [x] Task: Build run dashboard with timeline + coverage cards + agent runs + artifact tabs.
  Verify: `/runs/{id}` shows the demo run timeline, coverage payload, agent retry log, and Features/Epics/Stories/Tasks/Test Cases/Validation tabs.

- [x] Task: Add typed `useRunAgentA` / `useRunAgentB` / `useRunAgentC` / `useFinalizeRun` mutation hooks. Each invalidates run / timeline / coverage / agent-runs / sync-events / risk-events / review-queue keys.
  Verify: Hooks compile against `frontend/src/lib/types.ts` and refresh the dashboard without a manual reload.

- [x] Task: Replace the `Load Context` button on the run dashboard with a stage-aware `<NextStagePanel>`. The panel reads `run.current_stage` + HIL queue size and renders one of: Load Context / Run Agent A / Approve HIL-1 / Run Agent B / Approve HIL-2 / Run Agent C / Approve HIL-3 / Finalize / Sign off.
  Verify: A reviewer can walk a NEW_GAME run from S0 → FINAL_COVERAGE → Sign-off by clicking the panel's primary button at each step, with no terminal calls.

- [x] Task: Add an inline HIL approve list under `<NextStagePanel>` for HIL-1/2/3 with per-item Approve / Reject buttons and an `Approve all in queue` bulk action.
  Verify: After Agent A completes, the dashboard shows the HIL-1 queue inline; clicking Approve all clears the queue and unblocks the Agent B CTA.

- [x] Task: Change HIL-0 `Proceed with flag (n)` from parallel single-question requests to one bulk mutation.
  Verify: The dashboard calls `useResolveHil0Questions()` once for the open HIL-0 batch, and frontend lint/typecheck pass.

- [x] Task: Restore `next/font/google` while keeping offline `npm run build` support.
  Verify: `layout.tsx` uses `Inter` and `JetBrains_Mono` from `next/font/google`; `NEXT_FONT_GOOGLE_MOCKED_RESPONSES` points at checked-in local font responses; `npm run build` passes offline with webpack.

- [ ] Task: Build HIL-0, feature review, task review, and test-case review deep-link views under `/runs/[run_id]/hil/[tier]` (re-uses the same inline component for the body).
  Verify: Sidebar links open `/runs/{id}/hil/HIL-0..HIL-3`; the page shows the same items as the inline panel and supports the same mutations.

- [ ] Task: Build sync-events and risk-events views.
  Verify: UI shows `external_id`, target type, action, status, payload summary, risk severity, and owner action.

## Phase 4 - End-to-End Verification And Submission Polish

- [x] Task: Run backend tests, including new Phase 1.5 per-stage / HIL-gating tests.
  Verify: `conda activate qa-generator; cd backend; pytest` passes.

- [x] Task: Run backend lint.
  Verify: `conda activate qa-generator; cd backend; python -m ruff check .` passes.

- [x] Task: Run frontend lint/build once stage CTAs land.
  Verify: `cd frontend; npm run lint; npm run build` passes.

- [x] Task: Run frontend typecheck after the stage/HIL mutation additions.
  Verify: `cd frontend; npx tsc --noEmit` passes.

- [ ] Task: Run full mock-mode stepped demo from frontend.
  Verify: One stepped run (`Load Context → Agent A → HIL-1 → Agent B → HIL-2 → Agent C → HIL-3 → Finalize → Sign-off`) displays GDD version metadata, sections, features, tasks, test cases, validation issues, sync events, risk events, and coverage at the corresponding moments — no terminal use.

- [ ] Task: Run real AI + real Notion smoke test when credentials are configured.
  Verify: Stepped run creates or updates Notion records and stores successful `SyncEvent` rows.

- [ ] Task: Write final demo script in README — both `/demo-runs` (batch) and the stepped walkthrough.
  Verify: A new user can follow README commands and reproduce both paths.

- [ ] Task: Capture final screenshots — Run Dashboard at each next-stage CTA (S1 / HIL-1 / HIL-2 / HIL-3 / FINAL), HIL queues, Sync-A / Sync-B / Sync-C events in the sync log, signed-off coverage.
  Verify: Submission package includes visual proof of the stepped flow plus the final coverage state.
