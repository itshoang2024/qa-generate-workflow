# Backend Stage Tasks

This checklist tracks backend work against the source-of-truth solution files. Each task includes a verification step so implementation can proceed stage by stage without relying on hidden assumptions.

Progress rule: when a task in this file is completed, update its checkbox from `[ ]` to `[x]` in the same implementation turn or commit, and keep the `Verify:` line directly below it.

## Status Snapshot (last reviewed 2026-05-12 - Phase 1.8 implementation landed)

| Phase | Done / Total | Status |
|---|---|---|
| S0 Trigger + Mode Detection | 6 / 6 | Request model, rule-based mode detection, run/session init, demo compatibility shipped. |
| S1 Context Loader | 13 / 13 | GDD loading/versioning, Run source metadata, HIL-0 questions/resolutions including bulk resolution, DELTA scaffold, parser actionability shipped. |
| Stage Orchestration Endpoints | 6 / 6 | Agent A/B/C/finalize endpoints, wrong-stage checks, HIL gates, and tests shipped. |
| S2 Agent A | 4 / 4 | `AgentClient`, schema-validated Agent A output, fixture-backed mock default, and `AI_PROVIDER` factory with OpenAI Agent A adapter shipped. |
| S3 Validation A + Router A | 3 / 3 | Schema/source/confidence/coverage validation, Router A lanes, and bounded Agent A retry/rerun with stable HIL escalation shipped. |
| HIL-1 | 3 / 3 | `ReviewDecision` accepts feature/epic targets and cascades epic→feature/story; HIL-1 queues list pending items; approved feature IDs + epic candidates are snapshotted in session memory and passed to Agent B. |
| S4 Agent B (legacy bundled) | 6 / 6 | Agent B has the Task 2 contract/OpenAI path, assignee normalization, DELTA behavior, and coverage-feedback retry for partial real-provider output. |
| **Phase 1.8 — Agent B Hierarchical Decomposition** | **21 / 24 implementation** | Domain stages, AgentBJob persistence, B1/B2/B3 contracts/adapters, functional sub-stages, endpoints, validators, Sync-A1/A2, settings, and streaming response handling shipped. Remaining: transactional external-id allocator, legacy wrapper refactor, per-call timing/token usage. |
| S5 Validation B + Router B + HIL-2 | 6 / 6 | Validators, lanes, HIL-2 decisions, approved-feature coverage, HIL-1 epic coverage, and Sync-A/B blocking on exhausted coverage retry shipped. |
| S5b Notion Sync-A/B | 7 / 8 | `NotionSyncClient` interface + mock implementation shipped; real factory/adapter, schema preflight, retry/dead-letter, relation hydration, and replay are test-covered. |
| S6 Agent C | 3 / 3 | Agent C has mock + OpenAI structured-output adapters; concrete test data and repeatability guardrails ship. |
| S7 Validation C + HIL-3 | 2 / 2 | Category coverage, source traceability, low-confidence, forbidden-vague-phrase, RNG repeatability, one-assertion expected-result validators, and HIL-3 queue ship. |
| S7b Notion Sync-C | 2 / 2 | Sync-C emits separate test-case sync events and transitions eligible parent tasks to `Test Cases Ready`. |
| Final Coverage / Risk / Sign-Off | 4 / 5 | Coverage report includes risk/sync/GDD/sign-off state; RiskEvent model, kill switch, and sign-off endpoint shipped. Learning-loop corrections still open. |
| Final Backend Verification | 4 / 6 | Backend pytest + ruff pass in the `qa-generator` env; mock fallback remains test-covered. Manual Swagger/Supabase checks still open. |

## Next Implementation Slice - Remaining Backend Polish

Backend is feature-complete for the stepped mock-mode homework narrative. The real-provider S4/S5 guardrail from `run_1cefe76fe58c` is fixed: Agent B now retries with coverage feedback and blocks Sync-A/B if approved HIL-1 features or epic candidates remain uncovered.

Recently completed:

1. **Agent B coverage validator** - compare Agent B epics/stories/tasks to `session_memory.hil_1.approved_feature_ids` and `session_memory.hil_1.epic_structure`.
2. **Agent B retry loop** - retry with validation feedback that names missing feature IDs / epic candidates, bounded like Agent A retry.
3. **Sync safety** - do not persist/sync a partial plan when coverage remains incomplete; return `agent_b_coverage_exhausted` with validation/risk evidence.

Every Task-1 stage (S0..S7 + HIL-0..HIL-3 + Final), every Task-2 contract for Agent A/B/C (with structured-output OpenAI adapter + bounded validation retry where needed), every Task-3 sync phase (A/B/C with eligibility gating + page-id mapping + parent-task status transition), and every Task-4 backbone (RiskEvent + kill switch + sign-off + risk_summary/sync_summary in the coverage report) ships and is test-covered.

The reviewer-facing stage UI is now wired. Current backend focus:

1. **Real Notion `httpx` adapter** under `app/services/notion/notion.py`: wraps `https://api.notion.com/v1`, posts Task 3 properties, retries with backoff on 429/5xx, and emits `SyncStatus.FAILED` on persistent failures.
2. **Notion factory/config**: `NOTION_PROVIDER=real` constructs the adapter only when token + Epic/Story/Task/Test Case DB IDs are present; `/providers/status` reports readiness.
3. **Notion schema preflight**: before any upsert, `GET /v1/databases/{id}` verifies required properties and emits failed sync/risk evidence on mismatch.
4. **Relation hydration + replay**: parent page IDs are loaded from persisted successful sync events across staged requests; `POST /api/v1/runs/{id}/sync-replay` reconstructs artifacts and calls Notion again.
5. **Correction memory**: persist HIL decisions with patch payload as the Task 4 learning-loop store; expose `GET /api/v1/projects/{id}/corrections` so future runs can feed prior corrections to Agent A/B prompts.

Pick real Notion first if the homework grader needs external-provider proof; correction memory remains Phase 4 polish.

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

- [x] Task: Add Agent B validation-feedback input for missing approved-feature and epic coverage.
  Verify: `build_agent_b_input()` can include retry feedback listing missing feature IDs, missing HIL-1 epic candidate IDs/titles, and explicit coverage rules without breaking the strict Agent B response schema.

- [x] Task: Add bounded Agent B retry for coverage gaps before persistence/sync.
  Verify: A fake AgentClient returns a gameplay-only partial plan on attempt 1 and a complete multi-epic plan on attempt 2; `/agent-b` records both attempts and completes with one final artifact set.

## Phase 1.8 - Agent B Hierarchical Decomposition (implemented, polish remaining)

This phase implements the design in `backend/PLAN.md` "Phase 1.8" section. Mock parity is non-negotiable: `/demo-runs` must keep 8/5/5/11/44 counts through the legacy `MockAgentClient.plan_qa_tasks()` bundled path. Real provider takes the new fan-out path.

### Domain + repository foundation

- [x] Task: Add `S4_1_AGENT_B_EPICS`, `S4_2_AGENT_B_STORIES`, `S4_3_AGENT_B_TASKS` to `PipelineStage` enum. Keep `S4_AGENT_B` for the legacy bundled path; treat it as an alias when comparing stages.
  Verify: `rg -n "S4_1_AGENT_B_EPICS|S4_2_AGENT_B_STORIES|S4_3_AGENT_B_TASKS" app/domain/models.py`; `pytest tests/test_pipeline.py` for `/demo-runs` still passes with bundled stage labels in its timeline.

- [x] Task: Add `AgentBJob`, `AgentBScope`, `AgentBJobStatus` Pydantic models in `app/domain/models.py`. Mirror with a Supabase `agent_b_jobs` table in `supabase/schema.sql`.
  Verify: `tests/test_supabase_schema.py` asserts the table exists; an in-memory repo test creates 5 jobs and lists them by run.

- [x] Task: Add repository methods `add_agent_b_jobs`, `update_agent_b_job`, `list_agent_b_jobs(run_id)`, `get_agent_b_job(job_id)` on `WorkflowRepository`. Implement in `InMemoryWorkflowRepository` and `SupabaseWorkflowRepository`.
  Verify: `tests/test_repositories.py` covers create/update/list parity between memory and Supabase.

- [ ] Task: Add task `external_id` seq allocator keyed on `(project_id, feature_id)` in the repository. The allocator must be transactional in Supabase (use `INSERT ... ON CONFLICT` against a `task_external_id_seq` table) and lock-protected in memory.
  Verify: Concurrent allocation test issues 10 concurrent requests for the same feature_id and asserts seq is 1..10 with no duplicates.

### AgentClient surface

- [x] Task: Add `plan_epics`, `plan_stories`, `plan_tasks` to `AgentClient` in `app/services/agents/__init__.py`. Keep existing methods intact.
  Verify: `python -c "from app.services.agents import AgentClient; import inspect; print([m for m in dir(AgentClient) if not m.startswith('_')])"` lists the new method names.

- [x] Task: Implement `MockAgentClient.plan_epics/plan_stories/plan_tasks` by slicing `data/snake_escape_fixture.json`. `plan_qa_tasks()` (legacy bundled) keeps returning the full 5/5/11 bundle for `/demo-runs`. New methods deliver epic/story/task subsets that compose into the same totals when called per epic / per story.
  Verify: A new pytest scenario calls `MockAgentClient` in three-stage fan-out mode (loop over epics calling `plan_stories`, loop over stories calling `plan_tasks`) and asserts the merged plan equals the bundled `plan_qa_tasks()` plan.

- [x] Task: Implement `OpenAIAgentClient.plan_epics`, `plan_stories`, `plan_tasks` with B1/B2/B3 system prompts + JSON schemas from `Task-2-Agent-prompts-JSON.md`. Add new contract dataclasses `AgentB1Output`, `AgentB2Output`, `AgentB3Output`, `AGENT_B1_RESPONSE_SCHEMA`, etc. in `app/services/agents/contracts.py`.
  Verify: A schema-level test asserts each new schema validates the sample outputs from Task 2 and rejects malformed ones.

- [x] Task: Add input builders `build_agent_b1_input`, `build_agent_b2_input(epic, features, sections)`, `build_agent_b3_input(story, feature, sections, ...)`. Each trims empty/None fields and caps summary at 200 chars.
  Verify: For a 25-feature Snake Escape run, `len(json.dumps(build_agent_b1_input(...)))` is < 8KB; `len(json.dumps(build_agent_b2_input(epic, features, ...)))` is < 6KB per call.

### Pipeline orchestration

- [x] Task: Add `_stage_s4_1_epics(run)` to `PipelineService`. Calls `plan_epics`, persists `Epic[]`, runs `validate_agent_b1_epic_coverage`, calls `_sync_a1_epics`, advances stage. Idempotent if called twice at same stage (returns same epics).
  Verify: Unit test runs S4.1 twice and asserts a single epic set persisted with one `AgentRun` snapshot.

- [x] Task: Add `_stage_s4_2_stories(run)` to `PipelineService`. For each epic, create an `AgentBJob`, call `plan_stories`, persist stories per epic, run `validate_agent_b2_story_coverage`, call `_sync_a2_stories(epic, stories)`, and track partial failures for retry.
  Verify: A fake AgentClient that returns success for 4 epics and timeout for 1 leaves the run at `S4_2_AGENT_B_STORIES` with `status=PARTIAL` (stored in `Run.session_memory.s4_2_status`) and 1 `AgentBJob` in `FAILED` state. After manually retrying the failed job, the run advances to `S4_3_AGENT_B_TASKS` precondition.

- [x] Task: Add `_stage_s4_3_tasks(run)` to `PipelineService`. Same job-tracked fan-out pattern for stories. After all jobs terminal, run `validate_agent_b3_full_plan` (schema + traceability + cross-story dedup + assignee + cross-epic dedup) and advance to `S5_VALIDATION_B_SYNC`.
  Verify: `pytest` scenario where 2/20 stories return duplicate task titles emits `duplicate_task_cross_story` validation issues and routes those tasks to BLOCK lane.

- [ ] Task: Keep legacy `_stage_s4_agent_b()` for `/demo-runs`. Update it to call the three new sub-stage helpers sequentially with `auto_approve=True`, so demo counts and timeline stage labels remain identical (still emitting `S4_AGENT_B` event in addition to the three sub-stage events for back-compat).
  Verify: `pytest tests/test_pipeline.py::test_demo_pipeline_generates_complete_execution_plan` still asserts 8/5/5/11/44.

### Validation B split

- [x] Task: Add `validate_agent_b1_epic_coverage(run_id, epics, hil1_context)` in `app/services/validators.py`. Emit `missing_b1_feature_coverage`, `extra_b1_feature_coverage`, `unknown_b1_feature_reference`.
  Verify: Unit test feeds 3 approved features with 1 epic missing 1 of them and asserts `missing_b1_feature_coverage` issue is emitted.

- [x] Task: Add `validate_agent_b2_story_coverage(run_id, epic, stories, features)`. Emit `missing_b2_story_for_feature`, `b2_story_count_out_of_range`.
  Verify: Unit test feeds an epic with 5 features and 1 story; asserts 4 `missing_b2_story_for_feature` issues.

- [x] Task: Add `validate_agent_b3_full_plan` to the new `_stage_s4_3_tasks` path. Add `duplicate_task_cross_story` and `duplicate_task_cross_epic` codes plus the existing task validation codes.
  Verify: Regression test asserts that for the bundled mock plan, no `duplicate_task_cross_story` issues appear; for an injected fan-out plan with deliberately duplicated titles, the issues are emitted and the duplicate tasks are routed to BLOCK.

### Notion Sync split

- [x] Task: Split `_sync_a_epics_stories` into `_sync_a1_epics(epics)` and `_sync_a2_stories(epic, stories)`. Emit sync events with `payload.sync_phase = "Sync-A1"` and `"Sync-A2"` respectively. `MockNotionSyncClient` should expose two new methods `upsert_epics_batch` (Sync-A1) and `upsert_stories_for_epic(epic, stories)` (Sync-A2) and keep its existing `upsert_epic` / `upsert_story` for the legacy bundled path.
  Verify: Stepped `/agent-b/epics` + `/agent-b/stories` produces 5 Sync-A1 events + 5 Sync-A2 events; legacy `/demo-runs` produces 10 Sync-A events (5 epics + 5 stories, all phase `Sync-A` for back-compat) unchanged.

### New API endpoints

- [x] Task: Add `POST /api/v1/runs/{run_id}/agent-b/epics`, `/agent-b/stories`, `/agent-b/tasks`. Each enforces stage precondition + HIL gate where applicable (HIL-1 only blocks `/epics`). Each returns the produced artifacts inside the standard envelope.
  Verify: API test walks NEW_GAME run from S0 → S1 → HIL-0 → Agent A → HIL-1 → `/agent-b/epics` → `/agent-b/stories` → `/agent-b/tasks` → HIL-2 → `/agent-c` → HIL-3 → `/finalize` and asserts the same final counts as `/demo-runs`.

- [x] Task: Add `GET /api/v1/runs/{run_id}/agent-b-jobs` returning `AgentBJob[]` ordered by `started_at`.
  Verify: API test runs `/agent-b/stories` against a fake client that fails 1/5 epic, then asserts the endpoint returns 5 jobs with 4 SUCCESS + 1 FAILED.

- [x] Task: Add `POST /api/v1/runs/{run_id}/agent-b/jobs/{job_id}/retry`. Retries only the named job. Stage advance happens once all jobs terminal.
  Verify: After the failure scenario above, retry the failed job (with a now-passing fake client) and assert the run advances to `S4_2_AGENT_B_STORIES`.

- [x] Task: Add `PATCH /api/v1/runs/{run_id}/epics/{epic_id}` accepting `{title?, description?, feature_ids?}`. Reject if `current_stage != S4_1_AGENT_B_EPICS`. Apply edit + record edit metadata in session memory.
  Verify: API test edits an epic title and asserts the patched epic is returned by `GET /epics`.

- [x] Task: Add `POST /api/v1/runs/{run_id}/epics/merge` and `/epics/split` endpoints. Merge body: `{source_epic_ids: [...], target_title, target_description}`. Split body: `{epic_id, splits: [{title, description, feature_ids}, ...]}`. Validate feature_ids exhaustively cover the source epic(s).
  Verify: API test merges two mock epics into one and asserts feature_ids unioned correctly; split test divides one epic's features into two new epics and asserts no feature is lost.

### Settings + latency mitigations

- [x] Task: Add settings `AI_MODEL_AGENT_B1` (default `gpt-4o`), `AI_MODEL_AGENT_B2` (default `gpt-4o-mini`), `AI_MODEL_AGENT_B3` (default `gpt-4o-mini`), `AGENT_B2_PARALLELISM` (default 3), `AGENT_B3_PARALLELISM` (default 5), `OPENAI_TIMEOUT_READ_SECONDS` (default 120).
  Verify: `/api/v1/health` reports the new settings; missing API key still blocks real provider.

- [x] Task: Switch `OpenAIAgentClient._post_response` to streaming consumption (`stream=true` in request, accumulate `text.delta` events). Total wall-time no longer triggers `ReadTimeout` unless inter-token gap exceeds configured threshold.
  Verify: Integration smoke test using `httpx_mock` simulates a 200s stream and asserts the client accumulates the full payload without raising `ReadTimeout`.

- [ ] Task: Log per-call timing + token usage into `AgentRun.output_snapshot.timing` (and `AgentBJob.output_summary.timing`).
  Verify: After a real-provider run, the snapshot includes `wall_time_ms`, `input_tokens`, `output_tokens` fields for each B1/B2/B3 call.

## Phase S5 - Validation B + Router B + HIL-2

- [x] Task: Validate schema, traceability, cross-agent references, dedup, assignee sanity, confidence, and task count guardrails.
  Verify: `validate_tasks` emits `unknown_feature`, `invalid_assignee`, `task_missing_source_section`, `low_confidence_task`, `duplicate_task_candidate`; cross-cutting flag propagates from feature → task. Covered by `test_validate_tasks_flags_bad_assignee_duplicate_and_low_confidence`. (Explicit task-count guardrail by epic/assignee not yet emitted; revisit when real Agent B is wired.)

- [x] Task: Add Router B lanes.
  Verify: `validate_tasks_with_routing` + `QATask.lane` computed field. AUTO at confidence ≥0.85 with no dedup/cross-cutting; BATCH at [0.65, 0.85); BLOCK on dedup/cross-cutting or <0.65. Covered by `test_validate_tasks_with_routing_blocks_duplicate_candidates`, `test_demo_run_api_produces_enveloped_response`.

- [x] Task: Add HIL-2 decisions for task approval, edit request, rejection, and assignee override.
  Verify: `POST /api/v1/runs/{run_id}/hil-2/tasks/{task_id}/decision` supports `approve`, `request_edit`, `reject`, and `override_assignee`; assignee overrides validate against the seeded QA roster, apply a controlled task patch, and move batch-lane items to the new reviewer. Covered by `test_hil2_task_decision_endpoint_applies_structured_actions` and `test_hil2_task_decision_endpoint_rejects_unknown_assignee_override`.

- [x] Task: Add Agent B approved-feature coverage validation.
  Verify: If HIL-1 approved `F-002`, `F-020`, and `F-021` but Agent B tasks reference only `F-002`, Validation B emits `missing_agent_b_feature_coverage` for the omitted feature IDs.

- [x] Task: Add Agent B HIL-1 epic coverage validation.
  Verify: If `session_memory.hil_1.epic_structure` has gameplay, UI, economy, and backend candidates but Agent B returns only `Gameplay Logic Scope`, Validation B emits `missing_agent_b_epic_coverage` for the omitted candidates.

- [x] Task: Block Sync-A/B on exhausted Agent B coverage retry.
  Verify: A regression test using the `run_1cefe76fe58c` failure shape returns `agent_b_coverage_exhausted`, records validation/risk evidence, leaves the run before `S5_VALIDATION_B_SYNC`, and creates no Sync-A/B events.

## Phase S5b - Notion Sync-A/B

- [x] Task: Introduce a `NotionSyncClient` interface with mock and real providers.
  Verify: `app/services/notion/__init__.py` defines the ABC; `MockNotionSyncClient` implements it and is covered by `test_mock_notion_sync_client_implements_notion_contract`.

- [x] Task: Implement Sync-A for Epic and Story after HIL-1.
  Verify: Sync events carry `payload.sync_phase = "Sync-A"` and the mock client records page-id mappings before task sync starts.

- [x] Task: Implement Sync-B for Task after HIL-2 or Router B auto-approval.
  Verify: Task upserts use `external_id`, relation page IDs, and only AUTO/APPROVED tasks are synced in Sync-B. Covered by `test_sync_events_endpoint_shows_sync_a_b_c_phases`.

- [x] Task: Add Notion factory/config and real `httpx` adapter.
  Verify: `build_notion_sync_client()` returns mock by default, requires token + DB IDs for `NOTION_PROVIDER=real`, and unit tests fake query/create/update by `external_id`.

- [x] Task: Add Notion schema validation, throttling, retry, and dead-letter behavior.
  Verify: Missing properties produce `SyncStatus.FAILED`; 429 retries respect `Retry-After`; persistent failures keep status `FAILED` with retry/error metadata.

- [x] Task: Hydrate Notion page-id relations from persisted sync events.
  Verify: Running S4.1 and S4.2/S4.3 in separate API requests still links Story -> Epic, Task -> Story/Epic, and Test Case -> Task.

- [x] Task: Implement real sync replay from pipeline state.
  Verify: `POST /api/v1/runs/{id}/sync-replay` reconstructs failed targets, calls the Notion adapter, and changes successful retries to `SyncStatus.REPLAYED`.

## Phase S6 - Agent C

- [x] Task: Move Agent C behind the shared `AgentClient` interface.
  Verify: `MockAgentClient.generate_test_cases()` produces 44 cases (4 per task × 11 tasks). Covered by `test_demo_pipeline_generates_complete_execution_plan`.

- [x] Task: Implement Task 2 Agent C structured JSON contract.
  Verify: Each approved task receives positive, negative, edge, and integration coverage where applicable. Covered by `test_openai_agent_c_uses_per_task_structured_contract` and `test_agent_c_response_schema_requires_concrete_case_fields`.

- [x] Task: Enforce concrete test data and repeatability rules.
  Verify: Vague phrases and RNG without seed create validation issues. Add `forbidden_vague_phrase` and `rng_without_seed` codes to `validate_test_cases`.

## Phase S7 - Validation C + HIL-3

- [x] Task: Validate schema, source traceability, category coverage, one-assertion expected result, forbidden vague phrases, repeatability, and task links.
  Verify: `validate_test_cases` covers `unknown_related_task`, `test_case_missing_source_section`, `low_confidence_test_case`, `missing_test_case_category`, `forbidden_vague_phrase`, `rng_without_seed`, and `one_assertion_expected_result`. Covered by `test_validate_test_cases_requires_all_categories`, `test_validate_test_cases_flags_vague_phrases_and_unseeded_rng`, and `test_validate_test_cases_flags_multi_assertion_expected_result`.

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
