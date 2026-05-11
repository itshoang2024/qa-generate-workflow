# Backend Stage Tasks

This checklist tracks backend work against the source-of-truth solution files. Each task includes a verification step so implementation can proceed stage by stage without relying on hidden assumptions.

Progress rule: when a task in this file is completed, update its checkbox from `[ ]` to `[x]` in the same implementation turn or commit, and keep the `Verify:` line directly below it.

## Status Snapshot (last reviewed 2026-05-11)

| Phase | Done / Total | Status |
|---|---|---|
| S0 Trigger + Mode Detection | 6 / 6 | Request model, rule-based mode detection, run/session init, demo compatibility shipped. |
| S1 Context Loader | 13 / 13 | GDD loading/versioning, Run source metadata, HIL-0 questions/resolutions including bulk resolution, DELTA scaffold, parser actionability shipped. |
| Stage Orchestration Endpoints | 6 / 6 | Agent A/B/C/finalize endpoints, wrong-stage checks, HIL gates, and tests shipped. |
| S2 Agent A | 4 / 4 | `AgentClient`, schema-validated Agent A output, fixture-backed mock default, and `AI_PROVIDER` factory with OpenAI Agent A adapter shipped. |
| S3 Validation A + Router A | 3 / 3 | Schema/source/confidence/coverage validation, Router A lanes, and bounded Agent A retry/rerun with stable HIL escalation shipped. |
| HIL-1 | 3 / 3 | `ReviewDecision` accepts feature/epic targets and cascades epic→feature/story; HIL-1 queues list pending items; approved feature IDs + epic candidates are snapshotted in session memory and passed to Agent B. |
| S4 Agent B | 4 / 4 | Agent B now has a Task 2 structured contract, OpenAI adapter path, rule-based assignee normalization, and DELTA skip/update/new/archive behavior in the mock. |
| S5 Validation B + Router B + HIL-2 | 2 / 3 | Validators (schema, traceability, dedup, assignee, confidence) + lane assignment + HIL-2 queue shipped. Explicit HIL-2 decision API surfaces (edit request, assignee override) still open beyond the generic `POST /review-decisions`. |
| S5b Notion Sync-A/B | 3 / 4 | `NotionSyncClient` interface + mock implementation shipped; Sync-A/B separated with mock page-id mappings. Real schema preflight / retry / dead-letter still open. |
| S6 Agent C | 1 / 3 | Mock Agent C is behind the shared `AgentClient` and generates 4 cases per task. Real adapter and "concrete test data + repeatability" rules still open. |
| S7 Validation C + HIL-3 | 1 / 2 | Category coverage + source traceability + low-confidence validators ship; HIL-3 queue exists. Forbidden-vague-phrase and one-assertion-expected-result validators still open. |
| S7b Notion Sync-C | 2 / 2 | Sync-C emits separate test-case sync events and transitions eligible parent tasks to `Test Cases Ready`. |
| Final Coverage / Risk / Sign-Off | 4 / 5 | Coverage report includes risk/sync/GDD/sign-off state; RiskEvent model, kill switch, and sign-off endpoint shipped. Learning-loop corrections still open. |
| Final Backend Verification | 4 / 6 | Backend pytest + ruff pass in the `qa-generator` env; mock fallback remains test-covered. Manual Swagger/Supabase checks still open. |

## Next Implementation Slice - Remaining Backend Polish

Backend is now feature-complete for the stepped mock-mode homework narrative. Every Task-1 stage (S0..S7 + HIL-0..HIL-3 + Final), every Task-2 contract for Agent A (with structured-output OpenAI adapter + bounded retry/repair), every Task-3 sync phase (A/B/C with eligibility gating + page-id mapping + parent-task status transition), and every Task-4 backbone (RiskEvent + kill switch + sign-off + risk_summary/sync_summary in the coverage report) ships and is test-covered.

The reviewer-facing stage UI is now wired. Backend work that can run in parallel with frontend polish:

1. **Real Agent C adapter** (`OpenAIAgentClient.generate_test_cases`): same shape as Agent A/B, plus forbidden-vague-phrase guard. Mock already emits the four categories deterministically — real adapter is incremental value.
2. **Real Notion `httpx` adapter** under `app/services/notion/notion.py`: wraps the `https://api.notion.com/v1` API, posts properties matching Task 3 schemas, retries with backoff on 429, and emits `SyncStatus.FAILED` events on persistent failures so `POST /api/v1/runs/{id}/sync-replay` has real targets to replay.
3. **Notion schema preflight**: before any upsert, `GET /v1/databases/{id}` and verify required properties exist; pause sync and emit a Task-4 risk event on mismatch.
4. **Forbidden-vague-phrase / one-assertion / repeatability validators** in `validate_test_cases`.
5. **Correction memory**: persist HIL decisions with patch payload as the Task 4 learning-loop store; expose `GET /api/v1/projects/{id}/corrections` so future runs can feed prior corrections to Agent A/B prompts.

Pick (3) if the homework grader wants to see real Notion working; pick (5)+(6)+(7) if you want demo realism without external dependencies; otherwise skip directly to the frontend and treat the rest as Phase 4 polish.

## Phase 0 Items From Root Plan

All Phase 0 items from root `TASKS.md` are complete. Backend config reads `backend/.env` after process env, `/api/v1/health` reflects the active provider, and default GDD path selection uses the canonical repo sample `data/GDD_Sample_Snake_Escape.docx`.

## Phase S0 - Trigger + Mode Detection

- [x] Task: Revise backend plan/tasks so S0 only owns trigger, mode detection, run creation, and session initialization.
  Verify: `rg -n "S0 does not|Input: GDD upload|mode=DELTA|mode=NEW_GAME|session memory" backend/PLAN.md backend/TASKS.md`.

- [x] Task: Add S0 request model for GDD upload reference plus project selection.
  Verify: Request can represent either existing `project_id` or new project name, plus `gdd_file`.

- [x] Task: Implement rule-based mode detection.
  Verify: Existing project selection produces `mode=DELTA`; new project creation produces `mode=NEW_GAME`.

- [x] Task: Create run ID and initialize session memory.
  Verify: S0 response includes `{run_id, project_id, gdd_file, mode}` and session memory exists for the run.

- [x] Task: Keep S0 free of parser/storage/versioning side effects.
  Verify: S0 test asserts no GDD sections and no `GDDDocument` record are created before S1.

- [x] Task: Preserve `/api/v1/demo-runs`.
  Verify: Existing demo run API still creates a completed Snake Escape run with a complete timeline in mock mode.

## Phase S1 - Context Loader

- [x] Task: Load raw GDD file handed off by S0.
  Verify: S1 receives `gdd_file`, reads the file, and reports a clear error for missing files.

- [x] Task: Add `GDDDocument` domain model.
  Verify: Model includes `project_id`, `version_id`, optional `description`, `description_status`, `parent_document_id`, file metadata, and `sha256`.

- [x] Task: Extend `Run` with GDD document and source version metadata after S1 registration.
  Verify: Run detail includes `gdd_document_id`, `source_version_id`, and source metadata after S1 completes.

- [x] Task: Add repository methods for project get/list.
  Verify: Memory and Supabase repositories can create, fetch, and list projects.

- [x] Task: Add repository methods for GDD document create/get/list/latest/next version.
  Verify: Tests show the first document for a project is `v1` and the second is `v2`.

- [x] Task: Add Supabase `gdd_documents` schema.
  Verify: `supabase/schema.sql` creates `gdd_documents`, unique `(project_id, version_id)`, and indexes for project/document lookup.

- [x] Task: Add upload/runtime storage settings.
  Verify: Config exposes `UPLOAD_DIR` and `MAX_UPLOAD_BYTES`, uploaded files go under `backend/.runtime/uploads/`, and runtime uploads are git-ignored.

- [x] Task: Add `python-multipart` for FastAPI upload handling when route implementation needs multipart.
  Verify: `pip install -r backend/requirements.txt` installs upload dependencies in `qa-generator`.

- [x] Task: Add S1 structural DOCX parse.
  Verify: Parser tests assert headings, tables, special blocks, and stable section order.

- [x] Task: Add QA-actionability filter.
  Verify: Tests show metadata/external-dependency sections are excluded and behavior/UI/data sections are actionable.

- [x] Task: Add HIL-0 preflight issue model/API.
  Verify: API tests can list one batch of clarification questions and resolve with provide-artifact, proceed-with-flag, or skip.

- [x] Task: Add HIL-0 bulk resolution API for dashboard batch actions.
  Verify: `POST /api/v1/runs/{run_id}/hil-0/resolutions/bulk` resolves the open batch in one request, rejects missing/duplicate question IDs, and is covered by `test_hil0_bulk_resolution_resolves_open_questions`.

- [x] Task: Add S1.4 DELTA diff scaffold.
  Verify: DELTA mode loads previous GDD version and emits `NEW`, `MODIFIED`, `UNCHANGED`, `REMOVED` buckets or a placeholder with stable shape.

## Phase Stage Orchestration Endpoints

- [x] Task: Extract reusable Agent A/B/C/finalize stage methods from the batch demo pipeline.
  Verify: `/api/v1/demo-runs` still produces the same Snake Escape counts while per-stage endpoints call the same stage helpers.

- [x] Task: Add `POST /api/v1/runs/{run_id}/agent-a`.
  Verify: After S0 + S1, posting Agent A advances to `S3_VALIDATION_A`, persists features, and records Agent A timeline events.

- [x] Task: Add `POST /api/v1/runs/{run_id}/agent-b`.
  Verify: The endpoint returns 409 `hil_gate_blocked` until HIL-1 is cleared, then advances to `S5_VALIDATION_B_SYNC` and emits Sync-A/B events.

- [x] Task: Add `POST /api/v1/runs/{run_id}/agent-c`.
  Verify: The endpoint returns 409 `wrong_stage` if called before Agent B and returns 409 `hil_gate_blocked` until HIL-2 is cleared.

- [x] Task: Add `POST /api/v1/runs/{run_id}/finalize`.
  Verify: After Agent C and HIL-3 clearance, the endpoint builds coverage, marks the run `COMPLETED`, and sets `current_stage=FINAL_COVERAGE`.

- [x] Task: Add shared stage-precondition errors.
  Verify: API tests cover `wrong_stage` and `hil_gate_blocked` structured error envelopes.

## Phase S2 - Agent A

- [x] Task: Introduce a shared `AgentClient` interface for agent calls.
  Verify: Abstract base at `app/services/agents/__init__.py`; `MockAgentClient` implements it. Covered by `test_mock_agent_client_implements_agent_client_contract`.

- [x] Task: Implement Task 2 Agent A structured JSON contract.
  Verify: `AgentAOutput` validates `features`, `coverage_report`, `ambiguities`, source sections, confidence, and optional DELTA status. Mock Agent A now validates through this contract before returning domain features.

- [x] Task: Keep fixture-backed mock Agent A as the default provider.
  Verify: Tests pass with no AI credentials configured.

- [x] Task: Add real AI provider selection behind `AI_PROVIDER`.
  Verify: `build_agent_client()` returns mock by default, constructs an OpenAI Agent A adapter when `AI_PROVIDER=openai` or `real`, requires `OPENAI_API_KEY`, and rejects unsupported providers with a clear request error.

## Phase S3 - Validation A + Router A

- [x] Task: Validate Agent A schema, source traceability, keyword overlap, coverage, and confidence.
  Verify: `validate_features` covers `missing_source_section`, `low_confidence_feature`, `uncovered_actionable_section`, `preflight_note`. Covered by `test_validate_features_flags_missing_source_and_low_confidence`. (Keyword-overlap heuristic is not explicit yet — current validator relies on source-section membership; revisit if real-LLM hallucination defense needs it.)

- [x] Task: Add Router A lanes.
  Verify: `derive_router_lane` in `domain/models.py` enforces `>=0.85` → AUTO, `[0.60, 0.85)` → BATCH, `<0.60` → BLOCK for features; `validate_features_with_routing` applies the lane to `review_status`. Covered by `test_validate_features_with_routing_assigns_hil1_lanes`.

- [x] Task: Add retry/rerun behavior for schema, traceability, and uncovered-section failures.
  Verify: `run_agent_a_with_retries()` retries schema failures, traceability failures, and uncovered-section reruns up to 3 attempts, merges uncovered-section rerun output, logs attempts in AgentRun/session memory, and emits `agent_a_retry_exhausted` after max attempts. Covered by `tests/test_agent_a_retry.py`.

## Phase HIL-1 - Epic-Level Review

- [x] Task: Extend review decisions for feature and epic targets.
  Verify: `POST /api/v1/review-decisions` accepts `feature`, `epic`, `story`, `task`, `test_case`; `InMemoryWorkflowRepository._apply_review_status` cascades epic decisions to features + stories. Covered by `test_review_decisions_endpoint_returns_hil_decisions`, `test_review_decision_approval_updates_lane_and_removes_item_from_queue`.

- [x] Task: Store approved feature list and epic structure in session memory.
  Verify: `pipeline.run_demo()` writes `Run.session_memory["hil_1"]` with approved feature IDs, held/review-queue feature IDs, approved feature snapshots, and deterministic epic candidates before Agent B. Agent B receives that context through `plan_qa_tasks(..., hil_context=...)`, and `MockAgentClient.plan_qa_tasks()` filters by `approved_feature_ids` when provided. Covered by `test_demo_pipeline_snapshots_hil1_context_for_agent_b` and `test_mock_agent_b_consumes_hil1_approved_feature_ids`.

- [x] Task: Add review listing endpoints if required by frontend queues.
  Verify: `GET /api/v1/runs/{run_id}/review-queues/HIL-1` returns features + epics in BATCH/BLOCK lanes grouped by reviewer/feature/epic. Covered by `test_review_queue_endpoint_groups_items_by_reviewer_feature_and_epic`.

## Phase S4 - Agent B

- [x] Task: Move Agent B behind the shared `AgentClient` interface.
  Verify: `MockAgentClient.plan_qa_tasks()` returns 5 epics / 5 stories / 11 tasks deterministically. Covered by `test_demo_pipeline_generates_complete_execution_plan`.

- [x] Task: Implement Task 2 Agent B structured JSON contract.
  Verify: `AgentBOutput` and `AGENT_B_RESPONSE_SCHEMA` define the Epic -> Story -> Task tree with `feature_id`, `source_sections`, `external_id`, `priority_justification`, estimate, confidence, and optional task DELTA status; `OpenAIAgentClient.plan_qa_tasks()` calls `/v1/responses` with strict schema output. Covered by `test_agent_b_response_schema_requires_task_contract_fields`, `test_agent_b_contract_normalizes_assignee_from_feature_mapping`, and `test_openai_agent_b_uses_structured_contract_and_normalized_assignee`.

- [x] Task: Enforce rule-based assignee mapping.
  Verify: `AgentBOutput.to_domain_plan()` normalizes every known task assignee from `QA_ASSIGNEE_BY_FEATURE_TYPE` before creating `QATask`, so a model-provided assignee cannot override the KB mapping. Covered by `test_agent_b_contract_normalizes_assignee_from_feature_mapping` and `test_openai_agent_b_uses_structured_contract_and_normalized_assignee`.

- [x] Task: Add DELTA task behavior.
  Verify: Mock Agent A maps S1 `delta_report.buckets` to feature `delta_status`; Mock Agent B skips `UNCHANGED`, marks `MODIFIED` as `UPDATE_RETEST`, marks `NEW` as `NEW`, and creates `ARCHIVE` confirmation tasks for `REMOVED`. Covered by `test_mock_agent_a_maps_delta_report_buckets_to_feature_statuses` and `test_mock_agent_b_applies_delta_task_behavior`.

## Phase S5 - Validation B + Router B + HIL-2

- [x] Task: Validate schema, traceability, cross-agent references, dedup, assignee sanity, confidence, and task count guardrails.
  Verify: `validate_tasks` emits `unknown_feature`, `invalid_assignee`, `task_missing_source_section`, `low_confidence_task`, `duplicate_task_candidate`; cross-cutting flag propagates from feature → task. Covered by `test_validate_tasks_flags_bad_assignee_duplicate_and_low_confidence`. (Explicit task-count guardrail by epic/assignee not yet emitted; revisit when real Agent B is wired.)

- [x] Task: Add Router B lanes.
  Verify: `validate_tasks_with_routing` + `QATask.lane` computed field. AUTO at confidence ≥0.85 with no dedup/cross-cutting; BATCH at [0.65, 0.85); BLOCK on dedup/cross-cutting or <0.65. Covered by `test_validate_tasks_with_routing_blocks_duplicate_candidates`, `test_demo_run_api_produces_enveloped_response`.

- [ ] Task: Add HIL-2 decisions for task approval, edit request, rejection, and assignee override.
  Verify: Generic `POST /api/v1/review-decisions` already accepts task targets and triggers cascade. Dedicated edit-request / assignee-override surfaces with structured `patch` semantics still open.

## Phase S5b - Notion Sync-A/B

- [x] Task: Introduce a `NotionSyncClient` interface with mock and real providers.
  Verify: `app/services/notion/__init__.py` defines the ABC; `MockNotionSyncClient` implements it and is covered by `test_mock_notion_sync_client_implements_notion_contract`.

- [x] Task: Implement Sync-A for Epic and Story after HIL-1.
  Verify: Sync events carry `payload.sync_phase = "Sync-A"` and the mock client records page-id mappings before task sync starts.

- [x] Task: Implement Sync-B for Task after HIL-2 or Router B auto-approval.
  Verify: Task upserts use `external_id`, relation page IDs, and only AUTO/APPROVED tasks are synced in Sync-B. Covered by `test_sync_events_endpoint_shows_sync_a_b_c_phases`.

- [ ] Task: Add Notion schema validation, throttling, retry, replay, and dead-letter behavior.
  Verify: Missing properties block sync; 429 retries; failed events are replayable.

## Phase S6 - Agent C

- [x] Task: Move Agent C behind the shared `AgentClient` interface.
  Verify: `MockAgentClient.generate_test_cases()` produces 44 cases (4 per task × 11 tasks). Covered by `test_demo_pipeline_generates_complete_execution_plan`.

- [ ] Task: Implement Task 2 Agent C structured JSON contract.
  Verify: Each approved task receives positive, negative, edge, and integration coverage where applicable. (Mock already emits the four categories deterministically; real LLM adapter with per-task triggering still missing — today all tasks are batched in one call regardless of approval state.)

- [ ] Task: Enforce concrete test data and repeatability rules.
  Verify: Vague phrases and RNG without seed create validation issues. Add `forbidden_vague_phrase` and `rng_without_seed` codes to `validate_test_cases`.

## Phase S7 - Validation C + HIL-3

- [ ] Task: Validate schema, source traceability, category coverage, one-assertion expected result, forbidden vague phrases, repeatability, and task links.
  Verify: `validate_test_cases` covers `unknown_related_task`, `test_case_missing_source_section`, `low_confidence_test_case`, `missing_test_case_category`. Covered by `test_validate_test_cases_requires_all_categories`. `one_assertion_expected_result`, `forbidden_vague_phrase`, and `rng_without_seed` codes still open.

- [x] Task: Add HIL-3 decisions for test case approval, edit request, and rejection.
  Verify: Generic `POST /api/v1/review-decisions` accepts `test_case` targets; `GET /api/v1/runs/{run_id}/review-queues/HIL-3` lists pending cases grouped by reviewer/feature/epic with each task's assignee as the reviewer for BATCH-lane items.

## Phase S7b - Notion Sync-C

- [x] Task: Implement Sync-C for test cases after HIL-3 or Router C auto-approval.
  Verify: Test cases link to task pages by page ID resolved from Sync-B task mappings. Covered by `test_sync_events_endpoint_shows_sync_a_b_c_phases`.

- [x] Task: Update task status to `Test Cases Ready` when test cases are approved and synced.
  Verify: AUTO/APPROVED parent tasks move to `Test Cases Ready`; HIL-held tasks stay `Ready for Test Cases`. Covered by `test_sync_events_endpoint_shows_sync_a_b_c_phases`.

## Phase Final - Coverage, Risk, And Sign-Off

- [x] Task: Expand coverage/report API for frontend summary screens.
  Verify: Coverage report includes risk summary, sync summary, GDD version metadata, and sign-off state. Covered by `test_sign_off_endpoint_updates_run_and_coverage_report`.

- [x] Task: Add risk event model and dashboard data.
  Verify: `RiskEvent` persists through memory/Supabase repositories and `GET /api/v1/runs/{run_id}/risk-events` returns validator escalations. Covered by `test_risk_events_endpoint_returns_validator_escalations`.

- [ ] Task: Add learning-loop correction records.
  Verify: HIL corrections can be stored and retrieved for future prompt context.

- [x] Task: Add kill-switch behavior.
  Verify: Session memory stores per-run kill-switch state and critical S1 risk counts trip before Agent C. Covered by `test_kill_switch_trips_at_critical_risk_threshold`.

- [x] Task: Add reviewer sign-off model and endpoint.
  Verify: `POST /api/v1/runs/{run_id}/sign-off` records reviewer/time on `Run` and coverage sign-off. Covered by `test_sign_off_endpoint_updates_run_and_coverage_report`.

## Final Backend Verification

- [x] Task: Run the backend test suite.
  Verify: `C:\Users\Hoang\miniconda3\envs\qa-generator\python.exe -m pytest -q` passes from `backend/`.

- [x] Task: Run backend linting.
  Verify: `conda run -n qa-generator python -m ruff check .` passes from `backend/`.

- [ ] Task: Run manual Swagger demo.
  Verify: `POST /api/v1/demo-runs` creates a run, and timeline, coverage, tasks, test cases, validation issues, and sync payloads are inspectable.

- [ ] Task: Run source-of-truth Stage 0/Stage 1 Swagger demo after implementation.
  Verify: Upload + new project creates `NEW_GAME`; upload + existing project creates `DELTA`; S1 registers/parses GDD and emits HIL-0/DELTA context.

- [ ] Task: Run Notion smoke test when credentials are configured.
  Verify: Sync-A/B/C upsert records by `external_id`, preserve page-id relations, and replay failed events without duplicates.

- [x] Task: Confirm mock fallback remains stable.
  Verify: Removing AI, Notion, and Supabase credentials still allows the complete demo run to finish.
